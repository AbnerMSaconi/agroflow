"""Roteamento: olha a extensão, chama o extrator certo e grava na tabela.

Chamado pelo watcher (scripts/watch_bucket.py), pelos lotes (scripts/run_batch.py)
e pelo motor do fluxo (agroflow/fluxo.py).
"""
import logging
import time
from pathlib import Path

from . import config, invoices, leaves
from .leaves.conjuntos import CLASSES
from .storage import Row, save

log = logging.getLogger("agroflow")

CAMPOS_NOTA = ("cnpj_emitente", "numero", "data_emissao", "valor_total")
ROTULOS_CAMPO_NOTA = {
    "cnpj_emitente": "CNPJ do emitente",
    "numero": "Número da nota",
    "data_emissao": "Data de emissão",
    "valor_total": "Valor total",
}
ROTULOS_FOLHA = {
    "cercosporiose": "Cercosporiose",
    "ferrugem_comum": "Ferrugem comum",
    "helmintosporiose": "Helmintosporiose",
    "saudavel": "Saudável",
}


class ArquivoInvalido(Exception):
    pass


def _formatar_campo_nota(campo: str, valor: str | None) -> str | None:
    if valor is None:
        return None
    if campo == "data_emissao" and len(valor) == 10 and valor[4] == "-" and valor[7] == "-":
        a, m, d = valor.split("-")
        return f"{d}/{m}/{a}"
    if campo == "valor_total":
        try:
            v = float(valor)
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except ValueError:
            return valor
    return str(valor)


def process_invoice(path, nome=None, origem: str = "lote") -> list[Row]:
    nome = nome or Path(path).name
    t = time.perf_counter()
    campos, fonte = invoices.extract(path)
    ms = (time.perf_counter() - t) * 1000
    if not campos:
        raise ArquivoInvalido(f"nenhum campo de DANFE encontrado em {nome}")
    rows = [Row(nome, "nota", c, v, conf, duracao_ms=ms, origem=origem) for c, (v, conf) in campos.items()]
    rows.append(Row(nome, "nota", "_fonte", fonte, None, duracao_ms=ms, origem=origem))
    return rows


TIPO_CLASSIFICADOR = {"produto": "folha_classificador", "lab": "folha_classificador_lab"}


def process_leaf(
    path,
    nome=None,
    baseline=True,
    classificador=None,
    modelo="produto",
    origem: str = "lote",
) -> list[Row]:
    """classificador=None: usa o classificador se o arquivo do modelo existir (ver leaves).

    modelo: "produto" (lab+campo, o das telas) ou "lab" (só laboratório); muda o tipo gravado.
    """
    if classificador is None:
        classificador = leaves.classificador_disponivel(modelo)
    nome = nome or Path(path).name
    rows = []
    if baseline:
        t = time.perf_counter()
        labels = leaves.baseline(path)
        ms = (time.perf_counter() - t) * 1000
        rows += [Row(nome, "folha_baseline", f"rotulo_{i}", l, s, duracao_ms=ms, origem=origem)
                 for i, (l, s) in enumerate(labels, 1)]
    if classificador:
        t = time.perf_counter()
        classe, conf, _ = leaves.classify(path, modelo=modelo)
        rows.append(Row(nome, TIPO_CLASSIFICADOR[modelo], "classe", classe, conf,
                        duracao_ms=(time.perf_counter() - t) * 1000, origem=origem))
    return rows


def processar_detalhado(path, nome=None, origem: str = "lote") -> tuple[list[Row], dict]:
    """Processa nota ou folha retornando (rows, detalhe) para o motor das telas."""
    nome = nome or Path(path).name
    ext = Path(nome or path).suffix.lower()

    if ext in config.PDF_EXT:
        t = time.perf_counter()
        try:
            campos_det, fonte, tamanho = invoices.extract_detalhado(path)
        except ArquivoInvalido:
            raise
        except (OSError, RuntimeError, ValueError, IndexError) as e:
            raise ArquivoInvalido(f"arquivo PDF ilegível: {e}") from e
        ms = (time.perf_counter() - t) * 1000
        if not campos_det:
            raise ArquivoInvalido(f"nenhum campo de DANFE encontrado em {nome}")

        rows = [
            Row(nome, "nota", c, v, conf, duracao_ms=ms, origem=origem)
            for c, (v, conf, _) in campos_det.items()
        ]
        rows.append(Row(nome, "nota", "_fonte", fonte, None, duracao_ms=ms, origem=origem))

        campos_lista = []
        for campo in CAMPOS_NOTA:
            if campo in campos_det:
                valor, conf, caixa = campos_det[campo]
                campos_lista.append({
                    "campo": campo,
                    "rotulo": ROTULOS_CAMPO_NOTA[campo],
                    "valor": valor,
                    "exibicao": _formatar_campo_nota(campo, valor),
                    "confianca": float(conf),
                    "caixa": caixa,
                    "situacao": "ok",
                })
            else:
                campos_lista.append({
                    "campo": campo,
                    "rotulo": ROTULOS_CAMPO_NOTA[campo],
                    "valor": None,
                    "exibicao": None,
                    "confianca": 0.0,
                    "caixa": None,
                    "situacao": "nao_encontrado",
                })

        detalhe = {
            "tipo": "nota",
            "duracao_ms": round(ms, 1),
            "nota": {
                "fonte": fonte,
                "tamanho_pt": list(tamanho),
                "campos": campos_lista,
            },
            "folha": None,
        }
        return rows, detalhe

    if ext in config.IMAGE_EXT:
        rows = []
        t_inicio = time.perf_counter()
        try:
            t_base = time.perf_counter()
            labels = leaves.baseline(path)
            ms_base = (time.perf_counter() - t_base) * 1000
            rows += [
                Row(nome, "folha_baseline", f"rotulo_{i}", lbl, score, duracao_ms=ms_base, origem=origem)
                for i, (lbl, score) in enumerate(labels, 1)
            ]

            folha_det = None
            if leaves.classificador_disponivel("produto"):
                t_cls = time.perf_counter()
                classe, conf, probs = leaves.classify(path, modelo="produto")
                ms_cls = (time.perf_counter() - t_cls) * 1000
                rows.append(
                    Row(
                        nome,
                        TIPO_CLASSIFICADOR["produto"],
                        "classe",
                        classe,
                        conf,
                        duracao_ms=ms_cls,
                        origem=origem,
                    )
                )
                prob_map = {c: float(probs.get(c, 0.0)) for c in CLASSES}
                probabilidades = sorted(
                    [
                        {"classe": c, "rotulo": ROTULOS_FOLHA.get(c, c), "p": prob_map[c]}
                        for c in CLASSES
                    ],
                    key=lambda item: -item["p"],
                )
                folha_det = {
                    "classe": classe,
                    "rotulo": ROTULOS_FOLHA.get(classe, classe),
                    "confianca": float(conf),
                    "limiar": None,
                    "probabilidades": probabilidades,
                    "linha_de_base": [{"rotulo": lbl, "score": float(score)} for lbl, score in labels],
                }
        except (OSError, ValueError) as e:
            raise ArquivoInvalido(str(e)) from e

        ms_total = (time.perf_counter() - t_inicio) * 1000
        return rows, {
            "tipo": "folha",
            "duracao_ms": round(ms_total, 1),
            "nota": None,
            "folha": folha_det,
        }

    raise ArquivoInvalido(f"extensão não suportada: {ext or '(nenhuma)'}")


def process_file(path, nome=None) -> list[Row]:
    """Processa um arquivo do bucket e grava o resultado. Levanta ArquivoInvalido."""
    ext = Path(nome or path).suffix.lower()
    if ext in config.PDF_EXT:
        rows = process_invoice(path, nome)
    elif ext in config.IMAGE_EXT:
        try:
            rows = process_leaf(path, nome)
        except OSError as e:  # PIL não conseguiu abrir
            raise ArquivoInvalido(str(e)) from e
    else:
        raise ArquivoInvalido(f"extensão não suportada: {ext or '(nenhuma)'}")
    save(rows)
    return rows
