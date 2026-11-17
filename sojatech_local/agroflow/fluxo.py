"""Motor orientado a eventos compartilhado entre /prod e /press.

Observa `bucket/entrada/` (subpastas `notas/`, `imagens/` e raiz), processa um
arquivo por vez em fila única usando o pipeline local, salva mídia em
`results/fluxo/<id>/`, persiste itens finalizados no SQLite e expõe o estado
incremental para a API FastAPI.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import queue
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pymupdf as fitz
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import config, invoices, leaves, pipeline, storage
from .pipeline import ArquivoInvalido, CAMPOS_NOTA

log = logging.getLogger("agroflow.fluxo")

LIMITE_ITENS = 200
CMD_TREINO = "python scripts/train_leaf_classifier.py"

NOMES_CURTOS_NOTA = {
    "cnpj_emitente": "CNPJ do emitente",
    "numero": "número",
    "data_emissao": "data de emissão",
    "valor_total": "valor total",
}


class FluxoOcupado(RuntimeError):
    """Levantado ao tentar limpar enquanto há itens em andamento."""


def ler_limiares() -> tuple[float, float]:
    """Lê os limiares de nota e folha de `results/metricas.json` (com padrões)."""
    metricas_path = config.RESULTS / "metricas.json"
    lim_nota = None
    lim_folha = None
    if metricas_path.exists():
        try:
            m = json.loads(metricas_path.read_text(encoding="utf-8"))
            lim_nota = (m.get("notas_teste") or {}).get("limiar_escolhido")
            lim_folha = (m.get("classificador") or {}).get("limiar_escolhido")
        except (OSError, ValueError) as e:
            log.warning("não foi possível ler %s: %s", metricas_path, e)
    if lim_nota is None:
        lim_nota = 0.05
    if lim_folha is None:
        lim_folha = 0.90
    return float(lim_nota), float(lim_folha)


def decidir_nota(campos: list[dict], limiar: float) -> tuple[str, str]:
    """Atualiza `situacao` de cada campo e retorna `(estado, resumo)` da nota."""
    por_nome = {c["campo"]: c for c in campos}
    faltaram: list[str] = []
    baixas: list[str] = []

    for nome in CAMPOS_NOTA:
        c = por_nome.get(nome)
        rotulo_curto = NOMES_CURTOS_NOTA[nome]
        if c is None or c.get("valor") is None:
            if c is not None:
                c["situacao"] = "nao_encontrado"
            faltaram.append(rotulo_curto)
        elif float(c.get("confianca", 0.0)) < limiar:
            c["situacao"] = "baixa"
            baixas.append(rotulo_curto)
        else:
            c["situacao"] = "ok"

    if not faltaram and not baixas:
        return "aceito", "4 campos extraídos"

    partes: list[str] = []
    if len(faltaram) == 1:
        partes.append(f"{faltaram[0]} não encontrado")
    elif faltaram:
        partes.append(f"não encontrados: {', '.join(faltaram)}")
    if baixas:
        partes.append(f"confiança baixa em {', '.join(baixas)}")
    return "conferir", "; ".join(partes)


def decidir_folha(rotulo: str, confianca: float, limiar: float) -> tuple[str, str]:
    """Decide `(estado, resumo)` para uma folha classificada."""
    pct = f"{confianca * 100:.1f}%"
    if confianca >= limiar:
        return "aceito", f"{rotulo} ({pct})"
    return "conferir", f"{rotulo} ({pct} < {limiar * 100:.0f}%)"


def _tipo_por_extensao(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in config.PDF_EXT:
        return "nota"
    if ext in config.IMAGE_EXT:
        return "folha"
    return "outro"


def _resumo_processando(tipo: str) -> str:
    if tipo == "nota":
        return "lendo a nota"
    if tipo == "folha":
        return "classificando a folha"
    return "verificando arquivo"


class _ObservadorEntrada(FileSystemEventHandler):
    def __init__(self, fluxo: Fluxo):
        self.fluxo = fluxo

    def on_created(self, event):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if not p.name.startswith("."):
            self.fluxo._agendar_arquivo(p, esperar_estabilidade=True)

    def on_moved(self, event):
        if event.is_directory:
            return
        p = Path(event.dest_path)
        if not p.name.startswith("."):
            self.fluxo._agendar_arquivo(p, esperar_estabilidade=False)


class Fluxo:
    """Motor único do fluxo de entrada para /prod e /press."""

    def __init__(self, iniciar_observador: bool = True, aquecer: bool = True):
        self._usar_observador = iniciar_observador
        self._deve_aquecer = aquecer

        self._lock = threading.RLock()
        self._fila: queue.Queue[tuple[int, Path, Path] | None] = queue.Queue()
        self._parar = threading.Event()

        self._versao = 0
        self._limpo_em_versao = 0
        self._itens: dict[int, dict] = {}
        self._item_versao: dict[int, int] = {}
        self._pendentes: set[Path] = set()
        self._em_espera: set[Path] = set()
        self._exemplos_ativos = 0
        self._proximo_id = 1
        self._modelos = "carregando" if aquecer else (
            "prontos" if leaves.classificador_disponivel("produto") else "faltando"
        )

        self.limiar_nota, self.limiar_folha = ler_limiares()

        self._thread_worker: threading.Thread | None = None
        self._observer: Observer | None = None
        self._iniciado = False

        self._garantir_pastas()
        self._carregar_persistidos()

    @property
    def entrada_dir(self) -> Path:
        return config.BUCKET / "entrada"

    @property
    def processados_dir(self) -> Path:
        return config.BUCKET / "processados"

    @property
    def rejeitados_dir(self) -> Path:
        return config.BUCKET / "rejeitados"

    @property
    def midia_dir(self) -> Path:
        return config.RESULTS / "fluxo"

    def _garantir_pastas(self) -> None:
        for d in (
            self.entrada_dir / "notas",
            self.entrada_dir / "imagens",
            self.processados_dir,
            self.rejeitados_dir,
            self.midia_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def _carregar_persistidos(self) -> None:
        itens = storage.listar_itens(limite=LIMITE_ITENS)
        ids_validos = set()
        for it in itens:
            self._itens[it["id"]] = it
            self._item_versao[it["id"]] = 0
            ids_validos.add(it["id"])
        self._proximo_id = storage.proximo_item_id()
        # Remove mídias órfãs de execuções interrompidas antes da finalização
        if self.midia_dir.exists():
            for sub in self.midia_dir.iterdir():
                if sub.is_dir() and sub.name.isdigit() and int(sub.name) not in ids_validos:
                    shutil.rmtree(sub, ignore_errors=True)

    def iniciar(self) -> None:
        """Inicia a thread trabalhadora, lê pendentes na entrada e liga o watchdog."""
        with self._lock:
            if self._iniciado:
                return
            self._iniciado = True
            self._parar.clear()
            self._garantir_pastas()

            self._thread_worker = threading.Thread(
                target=self._loop_worker, name="agroflow-worker", daemon=True
            )
            self._thread_worker.start()

            if self._usar_observador:
                obs = Observer()
                obs.schedule(_ObservadorEntrada(self), str(self.entrada_dir), recursive=True)
                obs.start()
                self._observer = obs

        # Enfileira arquivos que já estavam na pasta de entrada ao subir
        for p in sorted(self.entrada_dir.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                self._enfileirar(p)

    def parar(self) -> None:
        """Encerra o observador e aguarda a thread trabalhadora parar."""
        with self._lock:
            if not self._iniciado:
                return
            self._iniciado = False
            self._parar.set()
            obs = self._observer
            self._observer = None
            worker = self._thread_worker
            self._thread_worker = None

        if obs is not None:
            obs.stop()
            obs.join(timeout=3.0)

        self._fila.put(None)
        if worker is not None:
            worker.join(timeout=5.0)

    def _esta_ocioso_locked(self) -> bool:
        if self._exemplos_ativos > 0:
            return False
        return not any(it["estado"] in ("chegou", "processando") for it in self._itens.values())

    def estado(self, desde: int | None = None) -> dict:
        """Devolve o snapshot completo ou incremental para `GET /api/estado`."""
        with self._lock:
            ocioso = self._esta_ocioso_locked()
            recentes = sorted(self._itens.values(), key=lambda it: it["id"], reverse=True)[:LIMITE_ITENS]
            completo = desde is None or desde < self._limpo_em_versao or desde > self._versao
            if completo:
                itens = [copy.deepcopy(it) for it in recentes]
            else:
                itens = [
                    copy.deepcopy(it)
                    for it in recentes
                    if self._item_versao.get(it["id"], 0) > desde
                ]
            return {
                "versao": self._versao,
                "completo": completo,
                "modelos": self._modelos,
                "limiares": {"nota": self.limiar_nota, "folha": self.limiar_folha},
                "ocioso": ocioso,
                "itens": itens,
            }

    def caminho_midia(self, item_id: int) -> Path | None:
        """Retorna o caminho do arquivo de mídia do item, ou None se indisponível."""
        with self._lock:
            it = self._itens.get(item_id)
            if not it or it["estado"] == "rejeitado" or not it.get("midia"):
                return None
        pasta = self.midia_dir / str(item_id)
        if not pasta.is_dir():
            return None
        for f in sorted(pasta.iterdir()):
            if f.is_file():
                return f
        return None

    def _destino_entrada(self, nome_base: str) -> Path:
        ext = Path(nome_base).suffix.lower()
        if ext in config.PDF_EXT:
            pasta = self.entrada_dir / "notas"
        elif ext in config.IMAGE_EXT:
            pasta = self.entrada_dir / "imagens"
        else:
            pasta = self.entrada_dir
        pasta.mkdir(parents=True, exist_ok=True)
        alvo = pasta / nome_base
        if alvo.exists():
            stem, suf = Path(nome_base).stem, Path(nome_base).suffix
            alvo = pasta / f"{stem}_{uuid.uuid4().hex[:6]}{suf}"
        return alvo

    def _gravar_atomico_entrada(self, nome_base: str, dados: bytes) -> Path:
        alvo = self._destino_entrada(nome_base)
        tmp = alvo.with_name(f".tmp_{uuid.uuid4().hex}_{alvo.name}")
        tmp.write_bytes(dados)
        os.replace(tmp, alvo)
        return alvo

    def enviar_arquivos(self, arquivos: list[tuple[str, bytes]]) -> int:
        """Grava arquivos na pasta de entrada usando arquivo temporário + rename."""
        recebidos = 0
        for nome, dados in arquivos:
            nome_base = Path(nome or "arquivo").name
            if not nome_base or nome_base.startswith("."):
                nome_base = f"arquivo_{uuid.uuid4().hex[:6]}"
            destino = self._gravar_atomico_entrada(nome_base, dados)
            recebidos += 1
            if not self._usar_observador:
                self._enfileirar(destino)
        return recebidos

    def enviar_exemplos(self) -> None:
        """Inicia uma thread que copia os exemplos da especificação a cada ~0,8 s."""
        with self._lock:
            self._exemplos_ativos += 1

        def _worker_exemplos():
            try:
                inv = config.INVOICES_TEST_DIR / "pdf"
                lv = config.LEAVES_DIR / "test"
                amostra: list[tuple[Path | None, str, bytes | None]] = [
                    (inv / "nota_002.pdf", "nota_002.pdf", None),
                    (lv / "ferrugem_comum" / "ferrugem_comum_000.jpg", "ferrugem_comum_000.jpg", None),
                    (inv / "nota_006.pdf", "nota_006.pdf", None),
                    (lv / "saudavel" / "saudavel_000.jpg", "saudavel_000.jpg", None),
                    (inv / "nota_001.pdf", "nota_001.pdf", None),
                    (lv / "helmintosporiose" / "helmintosporiose_000.jpg", "helmintosporiose_000.jpg", None),
                    (inv / "nota_005.pdf", "nota_005.pdf", None),
                    (lv / "cercosporiose" / "cercosporiose_000.jpg", "cercosporiose_000.jpg", None),
                    (lv / "cercosporiose" / "cercosporiose_012.jpg", "cercosporiose_012.jpg", None),
                    (lv / "ferrugem_comum" / "ferrugem_comum_001.jpg", "ferrugem_comum_001.jpg", None),
                    (None, "anotacoes.txt", b"Anotacoes de campo - arquivo nao suportado pelo fluxo.\n"),
                ]
                for idx, (origem, nome_base, conteudo) in enumerate(amostra):
                    if self._parar.is_set():
                        break
                    if origem is not None:
                        if not origem.exists():
                            log.warning("exemplo não encontrado: %s", origem)
                            continue
                        dados = origem.read_bytes()
                    else:
                        dados = conteudo or b""
                    destino = self._gravar_atomico_entrada(nome_base, dados)
                    if not self._usar_observador:
                        self._enfileirar(destino)
                    if idx < len(amostra) - 1 and self._parar.wait(0.8):
                        break
            finally:
                with self._lock:
                    self._exemplos_ativos = max(0, self._exemplos_ativos - 1)

        threading.Thread(target=_worker_exemplos, name="agroflow-exemplos", daemon=True).start()

    def limpar(self) -> None:
        """Limpa itens, resultados de origem 'fluxo' e mídia. Exige fluxo ocioso."""
        with self._lock:
            if not self._esta_ocioso_locked():
                raise FluxoOcupado("Fluxo em processamento; aguarde ficar ocioso.")
            storage.limpar_fluxo()
            if self.midia_dir.exists():
                for sub in self.midia_dir.iterdir():
                    if sub.is_dir():
                        shutil.rmtree(sub, ignore_errors=True)
                    else:
                        sub.unlink(missing_ok=True)
            self._itens.clear()
            self._item_versao.clear()
            self._versao += 1
            self._limpo_em_versao = self._versao

    def _agendar_arquivo(self, path: Path, esperar_estabilidade: bool) -> None:
        if not esperar_estabilidade:
            self._enfileirar(path)
            return

        resolved = path.resolve()
        with self._lock:
            if resolved in self._pendentes or resolved in self._em_espera:
                return
            self._em_espera.add(resolved)

        def _aguardar():
            try:
                anterior = -1
                for _ in range(10):
                    if self._parar.is_set() or not path.exists():
                        return
                    try:
                        atual = path.stat().st_size
                    except OSError:
                        return
                    if atual == anterior and atual > 0:
                        break
                    anterior = atual
                    if self._parar.wait(0.5):
                        return
                self._enfileirar(path)
            finally:
                with self._lock:
                    self._em_espera.discard(resolved)

        threading.Thread(target=_aguardar, name="agroflow-estabilidade", daemon=True).start()

    def _enfileirar(self, path: Path) -> int | None:
        if not path.is_file() or path.name.startswith("."):
            return None
        resolved = path.resolve()
        tipo = _tipo_por_extensao(path)

        with self._lock:
            if resolved in self._pendentes:
                return None
            self._pendentes.add(resolved)
            item_id = self._proximo_id
            self._proximo_id += 1

            tem_midia = False
            if tipo == "folha":
                tem_midia = self._copiar_midia_folha(item_id, path)

            item = {
                "id": item_id,
                "arquivo": path.name,
                "tipo": tipo,
                "estado": "chegou",
                "resumo": "na fila",
                "motivo": None,
                "recebido_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "duracao_ms": None,
                "midia": f"/api/midia/{item_id}" if tem_midia else None,
                "nota": None,
                "folha": None,
            }
            self._itens[item_id] = item
            self._versao += 1
            self._item_versao[item_id] = self._versao

        self._fila.put((item_id, path, resolved))
        return item_id

    def _copiar_midia_folha(self, item_id: int, path: Path) -> bool:
        try:
            pasta = self.midia_dir / str(item_id)
            pasta.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, pasta / f"midia{path.suffix.lower()}")
            return True
        except OSError:
            return False

    def _renderizar_midia_nota(self, item_id: int, path: Path) -> bool:
        try:
            pasta = self.midia_dir / str(item_id)
            pasta.mkdir(parents=True, exist_ok=True)
            with fitz.open(path) as doc:
                pix = doc[0].get_pixmap(dpi=110)
                pix.save(str(pasta / "pagina.png"))
            return True
        except Exception as e:
            log.warning("falha ao renderizar miniatura da nota %s: %s", path.name, e)
            return False

    def _mover_arquivo(self, path: Path, destino_base: Path, item_id: int) -> None:
        if not path.exists():
            return
        try:
            rel = path.relative_to(self.entrada_dir)
        except ValueError:
            rel = Path(path.name)
        alvo = destino_base / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if alvo.exists():
            alvo = alvo.with_name(f"{alvo.stem}_{item_id}{alvo.suffix}")
        shutil.move(str(path), str(alvo))

    def _aquecer_modelos(self) -> None:
        try:
            invoices.local_extractor._ocr_engine()
        except Exception as e:
            log.warning("falha no aquecimento do OCR: %s", e)

        disponivel = leaves.classificador_disponivel("produto")
        if disponivel:
            try:
                leaves.local_models._baseline_model()
                caminho = leaves.local_models._caminho("produto")
                leaves.local_models._classifier(str(caminho), caminho.stat().st_mtime_ns)
            except Exception as e:
                log.warning("falha no aquecimento dos modelos de folha: %s", e)
            novo_estado = "prontos"
        else:
            novo_estado = "faltando"

        with self._lock:
            if self._modelos != novo_estado:
                self._modelos = novo_estado
                self._versao += 1

    def _loop_worker(self) -> None:
        if self._deve_aquecer and not self._parar.is_set():
            self._aquecer_modelos()

        while not self._parar.is_set():
            try:
                tarefa = self._fila.get(timeout=0.5)
            except queue.Empty:
                continue
            if tarefa is None:
                break
            item_id, path, resolved = tarefa
            try:
                self._processar_item(item_id, path, resolved)
            except Exception:
                log.exception("erro inesperado no worker ao processar %s", path)

    def _processar_item(self, item_id: int, path: Path, resolved: Path) -> None:
        with self._lock:
            atual = self._itens.get(item_id)
            if atual is None:
                self._pendentes.discard(resolved)
                return
            tipo = atual["tipo"]
            atual["estado"] = "processando"
            atual["resumo"] = _resumo_processando(tipo)
            self._versao += 1
            self._item_versao[item_id] = self._versao

        t0 = time.perf_counter()
        try:
            if not path.is_file():
                raise ArquivoInvalido("arquivo removido antes do processamento")
            if tipo == "folha" and not leaves.classificador_disponivel("produto"):
                raise ArquivoInvalido(f"modelo não encontrado; treine com: {CMD_TREINO}")

            rows, detalhe = pipeline.processar_detalhado(path, nome=path.name, origem="fluxo")
            duracao_ms = float(detalhe.get("duracao_ms") or (time.perf_counter() - t0) * 1000)

            nota_det = detalhe.get("nota")
            folha_det = detalhe.get("folha")
            tem_midia = False

            if tipo == "nota" and nota_det is not None:
                estado_final, resumo = decidir_nota(nota_det["campos"], self.limiar_nota)
                tem_midia = self._renderizar_midia_nota(item_id, path)
            elif tipo == "folha" and folha_det is not None:
                folha_det["limiar"] = self.limiar_folha
                estado_final, resumo = decidir_folha(
                    folha_det["rotulo"], folha_det["confianca"], self.limiar_folha
                )
                with self._lock:
                    tem_midia = bool(self._itens.get(item_id, {}).get("midia"))
                if not tem_midia:
                    tem_midia = self._copiar_midia_folha(item_id, path)
            else:
                raise ArquivoInvalido("resultado inválido do pipeline")

            storage.save(rows)
            self._mover_arquivo(path, self.processados_dir, item_id)

            with self._lock:
                it = self._itens.get(item_id)
                if it is not None:
                    it["estado"] = estado_final
                    it["resumo"] = resumo
                    it["motivo"] = None
                    it["duracao_ms"] = round(duracao_ms, 1)
                    it["midia"] = f"/api/midia/{item_id}" if tem_midia else None
                    it["nota"] = nota_det
                    it["folha"] = folha_det
                    storage.salvar_item(it)
                    self._versao += 1
                    self._item_versao[item_id] = self._versao
        except Exception as e:
            duracao_ms = round((time.perf_counter() - t0) * 1000, 1)
            motivo = str(e) if isinstance(e, ArquivoInvalido) else f"erro inesperado: {e}"
            if not isinstance(e, ArquivoInvalido):
                log.exception("falha ao processar %s", path.name)

            config.BUCKET.mkdir(parents=True, exist_ok=True)
            with open(config.BUCKET / "rejeitados.log", "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{path.name}\t{motivo}\n")
            self._mover_arquivo(path, self.rejeitados_dir, item_id)
            shutil.rmtree(self.midia_dir / str(item_id), ignore_errors=True)

            with self._lock:
                it = self._itens.get(item_id)
                if it is not None:
                    it["estado"] = "rejeitado"
                    it["resumo"] = motivo
                    it["motivo"] = motivo
                    it["duracao_ms"] = duracao_ms
                    it["midia"] = None
                    it["nota"] = None
                    it["folha"] = None
                    storage.salvar_item(it)
                    self._versao += 1
                    self._item_versao[item_id] = self._versao
        finally:
            with self._lock:
                self._pendentes.discard(resolved)
