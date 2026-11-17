"""Testes das telas /prod e /press, extração com caixas, motor Fluxo, API e isolamento."""
import json
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

import pandas as pd
import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

import evaluate
from agroflow import config, fluxo as fluxo_mod, invoices, pipeline, storage
from agroflow.fluxo import Fluxo, FluxoOcupado, decidir_folha, decidir_nota, ler_limiares
from agroflow.invoices import local_extractor
from agroflow.storage import Row
from agroflow.web import STATIC_DIR, criar_app


# ---------- helpers ----------

def _aguardar_ocioso(motor: Fluxo, timeout: float = 10.0) -> dict:
    prazo = time.monotonic() + timeout
    while time.monotonic() < prazo:
        est = motor.estado()
        if est["ocioso"] and est["itens"] and all(
            it["estado"] in ("aceito", "conferir", "rejeitado") for it in est["itens"]
        ):
            return est
        time.sleep(0.05)
    raise AssertionError(f"Fluxo não ficou ocioso em {timeout}s: {motor.estado()}")


def _fazer_pdf_simples(caminho: Path, texto: str = "DANFE SIMPLES") -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), texto)
    doc.save(str(caminho))
    doc.close()
    return caminho


@pytest.fixture
def ambiente_fluxo(tmp_path, monkeypatch):
    """Isola BUCKET, RESULTS, RESULTS_DB e modelos falsos rápidos em tmp_path."""
    bucket = tmp_path / "bucket"
    results = tmp_path / "results"
    db = results / "agroflow.db"
    modelo_pt = tmp_path / "models" / "leaf_classifier.pt"
    modelo_pt.parent.mkdir(parents=True, exist_ok=True)
    modelo_pt.write_bytes(b"fake-pt")

    monkeypatch.setattr(config, "BUCKET", bucket)
    monkeypatch.setattr(config, "RESULTS", results)
    monkeypatch.setattr(config, "RESULTS_DB", db)
    monkeypatch.setattr(config, "LEAF_MODEL", modelo_pt)

    (results).mkdir(parents=True, exist_ok=True)
    (results / "metricas.json").write_text(
        json.dumps(
            {
                "notas_teste": {"limiar_escolhido": 0.05},
                "classificador": {"limiar_escolhido": 0.90},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        pipeline.leaves,
        "baseline",
        lambda p, k=5: [("corn", 0.51), ("leaf", 0.22)],
    )
    monkeypatch.setattr(
        pipeline.leaves,
        "classify",
        lambda p, modelo="produto": (
            "ferrugem_comum",
            0.96,
            {
                "ferrugem_comum": 0.96,
                "cercosporiose": 0.02,
                "helmintosporiose": 0.01,
                "saudavel": 0.01,
            },
        ),
    )
    monkeypatch.setattr(
        pipeline.leaves,
        "classificador_disponivel",
        lambda modelo="produto": modelo_pt.exists(),
    )

    return {
        "tmp_path": tmp_path,
        "bucket": bucket,
        "results": results,
        "db": db,
        "modelo_pt": modelo_pt,
    }


# ---------- 1. Regras de situação ----------

def test_decidir_nota_aceita_quando_todos_campos_ok():
    campos = [
        {"campo": "cnpj_emitente", "valor": "12.345.678/0001-95", "confianca": 0.85, "situacao": "ok"},
        {"campo": "numero", "valor": "123", "confianca": 0.95, "situacao": "ok"},
        {"campo": "data_emissao", "valor": "2026-01-10", "confianca": 0.90, "situacao": "ok"},
        {"campo": "valor_total", "valor": "100.00", "confianca": 0.05, "situacao": "ok"},
    ]
    estado, resumo = decidir_nota(campos, limiar=0.05)
    assert estado == "aceito"
    assert "4 campos" in resumo
    assert all(c["situacao"] == "ok" for c in campos)


def test_decidir_nota_conferir_campo_faltando_e_baixa_confianca():
    campos = [
        {"campo": "cnpj_emitente", "valor": "12.345.678/0001-95", "confianca": 0.85, "situacao": "ok"},
        {"campo": "numero", "valor": "123", "confianca": 0.40, "situacao": "ok"},
        {"campo": "data_emissao", "valor": "2026-01-10", "confianca": 0.90, "situacao": "ok"},
        {"campo": "valor_total", "valor": None, "confianca": 0.0, "situacao": "nao_encontrado"},
    ]
    estado, resumo = decidir_nota(campos, limiar=0.50)
    assert estado == "conferir"
    assert campos[1]["situacao"] == "baixa"
    assert campos[3]["situacao"] == "nao_encontrado"
    assert "valor total não encontrado" in resumo
    assert "número" in resumo


def test_decidir_nota_multiplos_campos_faltando():
    campos = [
        {"campo": "cnpj_emitente", "valor": None, "confianca": 0.0},
        {"campo": "numero", "valor": None, "confianca": 0.0},
        {"campo": "data_emissao", "valor": "2026-01-10", "confianca": 0.9},
        {"campo": "valor_total", "valor": "10.00", "confianca": 0.9},
    ]
    estado, resumo = decidir_nota(campos, limiar=0.05)
    assert estado == "conferir"
    assert "não encontrados" in resumo
    assert "CNPJ do emitente" in resumo and "número" in resumo


def test_decidir_folha_acima_e_abaixo_do_limiar():
    est_ok, res_ok = decidir_folha("Ferrugem comum", 0.90, 0.90)
    assert est_ok == "aceito"
    assert "Ferrugem comum" in res_ok

    est_conf, res_conf = decidir_folha("Helmintosporiose", 0.654, 0.90)
    assert est_conf == "conferir"
    assert "65.4%" in res_conf and "90%" in res_conf


def test_ler_limiares_padroes_e_metricas(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTS", tmp_path / "vazio")
    assert ler_limiares() == (0.05, 0.90)

    (tmp_path / "vazio").mkdir()
    (tmp_path / "vazio" / "metricas.json").write_text(
        json.dumps({"notas_teste": {"limiar_escolhido": 0.15}, "classificador": {"limiar_escolhido": 0.95}}),
        encoding="utf-8",
    )
    assert ler_limiares() == (0.15, 0.95)


# ---------- 2. extract_detalhado ----------

@pytest.mark.parametrize(
    "nome_pdf",
    [
        "nota_001.pdf",  # variante, digital
        "nota_002.pdf",  # compacto, digital
        "nota_007.pdf",  # padrao, digital
        "nota_005.pdf",  # variante, escaneada
        "nota_006.pdf",  # compacto, escaneada
        "nota_018.pdf",  # padrao, escaneada
    ],
)
def test_extract_detalhado_bate_com_extract_e_caixas_validas(nome_pdf):
    pdf = config.INVOICES_TEST_DIR / "pdf" / nome_pdf
    assert pdf.is_file(), f"PDF de teste ausente: {pdf}"

    campos_det, fonte_det, tamanho = invoices.extract_detalhado(pdf)
    campos_orig, fonte_orig = invoices.extract(pdf)

    assert fonte_det == fonte_orig
    assert tamanho[0] > 0 and tamanho[1] > 0
    assert {c: (v, conf) for c, (v, conf, _) in campos_det.items()} == campos_orig
    assert len(campos_det) >= 3

    for campo, (_valor, _conf, caixa) in campos_det.items():
        if caixa is not None:
            assert set(caixa.keys()) == {"x", "y", "w", "h"}, campo
            assert 0.0 <= caixa["x"] <= 100.0
            assert 0.0 <= caixa["y"] <= 100.0
            assert 0.0 <= caixa["w"] <= 100.0
            assert 0.0 <= caixa["h"] <= 100.0
            assert caixa["x"] + caixa["w"] <= 100.05
            assert caixa["y"] + caixa["h"] <= 100.05


def test_extract_detalhado_campo_pela_chave_tem_caixa_none(monkeypatch):
    chave = "35260565167612000119550010000455651000000010"  # CNPJ 65167612000119, num 45565
    boxes = [
        local_extractor.Box(10, 10, 200, 20, "CHAVE DE ACESSO", 1.0),
        local_extractor.Box(10, 25, 300, 35, chave, 1.0),
    ]
    monkeypatch.setattr(local_extractor, "_boxes_e_tamanho", lambda _p: (boxes, "texto", (595.0, 842.0)))

    campos, fonte, tamanho = local_extractor.extract_detalhado("fake.pdf")
    assert fonte == "texto"
    assert tamanho == (595.0, 842.0)
    assert campos["cnpj_emitente"] == ("65.167.612/0001-19", 0.5, None)
    assert campos["numero"] == ("45565", 0.5, None)


# ---------- 3. Motor Fluxo ----------

def test_fluxo_processa_nota_folha_e_txt_com_estados_e_limpar(ambiente_fluxo, fazer_imagem, monkeypatch):
    pdf_src = config.INVOICES_TEST_DIR / "pdf" / "nota_002.pdf"
    img_src = fazer_imagem(ambiente_fluxo["tmp_path"] / "folha_teste.jpg", semente=42, tamanho=(96, 96))

    estados_observados: list[tuple[str, str]] = []
    orig_processar = fluxo_mod.Fluxo._processar_item

    def _rastrear(self, item_id, path, resolved):
        with self._lock:
            it = self._itens[item_id]
            estados_observados.append((it["arquivo"], it["estado"]))
            if it["tipo"] == "folha":
                assert it["midia"] == f"/api/midia/{item_id}"
        orig_processar(self, item_id, path, resolved)
        with self._lock:
            it_fim = self._itens.get(item_id)
            if it_fim:
                estados_observados.append((it_fim["arquivo"], it_fim["estado"]))

    monkeypatch.setattr(fluxo_mod.Fluxo, "_processar_item", _rastrear)

    motor = Fluxo(iniciar_observador=False, aquecer=False)
    motor.iniciar()
    try:
        # Envia nota digital, folha e arquivo não suportado
        n = motor.enviar_arquivos([
            ("nota_002.pdf", pdf_src.read_bytes()),
            ("folha_teste.jpg", img_src.read_bytes()),
            ("anotacoes.txt", b"texto livre"),
        ])
        assert n == 3

        est = _aguardar_ocioso(motor)
        assert len(est["itens"]) == 3
        por_nome = {it["arquivo"]: it for it in est["itens"]}

        # Nota aceita + DANFE PNG renderizada
        nota = por_nome["nota_002.pdf"]
        assert nota["tipo"] == "nota"
        assert nota["estado"] == "aceito"
        assert nota["midia"] == f"/api/midia/{nota['id']}"
        assert motor.caminho_midia(nota["id"]).is_file()
        assert nota["nota"]["fonte"] == "texto"
        assert len(nota["nota"]["campos"]) == 4

        # Folha aceita + miniatura + 4 probabilidades + baseline
        folha = por_nome["folha_teste.jpg"]
        assert folha["tipo"] == "folha"
        assert folha["estado"] == "aceito"
        assert folha["midia"] == f"/api/midia/{folha['id']}"
        assert motor.caminho_midia(folha["id"]).is_file()
        assert len(folha["folha"]["probabilidades"]) == 4
        assert len(folha["folha"]["linha_de_base"]) == 2

        # .txt rejeitado + sem mídia + log
        txt = por_nome["anotacoes.txt"]
        assert txt["tipo"] == "outro"
        assert txt["estado"] == "rejeitado"
        assert txt["motivo"]
        assert txt["midia"] is None
        assert motor.caminho_midia(txt["id"]) is None

        # Transições chegaram e finalizaram
        assert ("nota_002.pdf", "chegou") in estados_observados
        assert ("nota_002.pdf", "aceito") in estados_observados
        assert ("folha_teste.jpg", "chegou") in estados_observados
        assert ("folha_teste.jpg", "aceito") in estados_observados
        assert ("anotacoes.txt", "chegou") in estados_observados
        assert ("anotacoes.txt", "rejeitado") in estados_observados

        # Arquivos movidos da entrada para processados/ e rejeitados/
        assert (ambiente_fluxo["bucket"] / "processados" / "notas" / "nota_002.pdf").is_file()
        assert (ambiente_fluxo["bucket"] / "processados" / "imagens" / "folha_teste.jpg").is_file()
        assert (ambiente_fluxo["bucket"] / "rejeitados" / "anotacoes.txt").is_file()
        assert "anotacoes.txt" in (ambiente_fluxo["bucket"] / "rejeitados.log").read_text(encoding="utf-8")

        # Limpar zera itens, resultados de origem='fluxo' e mídia, mantendo 'lote'
        storage.save([Row("lote_nota.pdf", "nota", "numero", "1", 0.9, origem="lote")])
        versao_antes = est["versao"]
        motor.limpar()
        est_pos = motor.estado()
        assert est_pos["itens"] == []
        assert est_pos["versao"] > versao_antes
        assert list(motor.midia_dir.iterdir()) == []

        df = storage.load_dataframe()
        assert list(df["origem"]) == ["lote"]
        assert storage.listar_itens() == []
    finally:
        motor.parar()


def test_fluxo_evento_duplicado_nao_duplica_item(ambiente_fluxo, fazer_imagem):
    motor = Fluxo(iniciar_observador=False, aquecer=False)
    img = fazer_imagem(ambiente_fluxo["bucket"] / "entrada" / "imagens" / "dup.jpg", semente=7)
    id1 = motor._enfileirar(img)
    id2 = motor._enfileirar(img)
    assert id1 is not None
    assert id2 is None
    assert len(motor.estado()["itens"]) == 1


def test_fluxo_ignora_temporarios_com_ponto_no_observador(ambiente_fluxo):
    motor = Fluxo(iniciar_observador=False, aquecer=False)
    tmp_file = ambiente_fluxo["bucket"] / "entrada" / ".parcial.pdf"
    tmp_file.write_bytes(b"parcial")
    assert motor._enfileirar(tmp_file) is None

    handler = fluxo_mod._ObservadorEntrada(motor)
    class _Evt:
        is_directory = False
        src_path = str(tmp_file)
        dest_path = str(tmp_file)
    handler.on_created(_Evt())
    handler.on_moved(_Evt())
    assert motor.estado()["itens"] == []


def test_fluxo_colisao_nome_no_destino_e_persistencia_entre_reinicios(ambiente_fluxo, fazer_imagem):
    img = fazer_imagem(ambiente_fluxo["tmp_path"] / "mesmo.jpg", semente=10)
    (ambiente_fluxo["bucket"] / "processados" / "imagens").mkdir(parents=True, exist_ok=True)
    (ambiente_fluxo["bucket"] / "processados" / "imagens" / "mesmo.jpg").write_bytes(b"antigo")

    motor1 = Fluxo(iniciar_observador=False, aquecer=False)
    motor1.iniciar()
    try:
        motor1.enviar_arquivos([("mesmo.jpg", img.read_bytes())])
        est = _aguardar_ocioso(motor1)
        item_id = est["itens"][0]["id"]
        assert (ambiente_fluxo["bucket"] / "processados" / "imagens" / f"mesmo_{item_id}.jpg").is_file()
    finally:
        motor1.parar()

    # Nova instância carrega itens finalizados do SQLite
    motor2 = Fluxo(iniciar_observador=False, aquecer=False)
    est2 = motor2.estado()
    assert len(est2["itens"]) == 1
    assert est2["itens"][0]["id"] == item_id
    assert est2["itens"][0]["estado"] == "aceito"


def test_fluxo_modelo_folha_faltando_rejeita_folha_mas_aceita_nota(ambiente_fluxo, fazer_imagem):
    ambiente_fluxo["modelo_pt"].unlink()
    pdf_src = config.INVOICES_TEST_DIR / "pdf" / "nota_002.pdf"
    img_src = fazer_imagem(ambiente_fluxo["tmp_path"] / "sem_modelo.jpg", semente=13)

    motor = Fluxo(iniciar_observador=False, aquecer=False)
    assert motor.estado()["modelos"] == "faltando"
    motor.iniciar()
    try:
        motor.enviar_arquivos([
            ("sem_modelo.jpg", img_src.read_bytes()),
            ("nota_002.pdf", pdf_src.read_bytes()),
        ])
        est = _aguardar_ocioso(motor)
        por_nome = {it["arquivo"]: it for it in est["itens"]}
        assert por_nome["sem_modelo.jpg"]["estado"] == "rejeitado"
        assert "train_leaf_classifier.py" in por_nome["sem_modelo.jpg"]["motivo"]
        assert por_nome["nota_002.pdf"]["estado"] == "aceito"
    finally:
        motor.parar()


# ---------- 4. API FastAPI com TestClient ----------

def test_api_paginas_estado_upload_exemplos_limpar_409_e_midia(ambiente_fluxo, fazer_imagem):
    motor = Fluxo(iniciar_observador=False, aquecer=False)
    app = criar_app(fluxo=motor, iniciar_fluxo=True)

    img_path = fazer_imagem(ambiente_fluxo["tmp_path"] / "api_folha.jpg", semente=99)
    pdf_path = _fazer_pdf_simples(ambiente_fluxo["tmp_path"] / "vazio.pdf", "sem danfe")

    with TestClient(app) as client:
        # Páginas e redirecionamento
        r_root = client.get("/", follow_redirects=False)
        assert r_root.status_code in (302, 307)
        assert r_root.headers["location"] == "/prod"

        for rota in ("/prod", "/press"):
            r = client.get(rota)
            assert r.status_code == 200
            assert "text/html" in r.headers["content-type"]

        # Estado inicial completo
        r_est0 = client.get("/api/estado")
        assert r_est0.status_code == 200
        d0 = r_est0.json()
        assert d0["completo"] is True
        assert d0["ocioso"] is True
        assert d0["itens"] == []
        v0 = d0["versao"]

        # Upload com campo `arquivos` e com campo `files` (reduzindo caminho ao nome base)
        r_up = client.post(
            "/api/enviar",
            files=[
                ("arquivos", ("subpasta/api_folha.jpg", img_path.read_bytes(), "image/jpeg")),
                ("files", ("../vazio.pdf", pdf_path.read_bytes(), "application/pdf")),
            ],
        )
        assert r_up.status_code == 200
        assert r_up.json() == {"recebidos": 2}

        est_fim = _aguardar_ocioso(motor)
        v_fim = est_fim["versao"]

        # Estado incremental sem mudanças
        r_inc_vazio = client.get(f"/api/estado?desde={v_fim}")
        assert r_inc_vazio.status_code == 200
        assert r_inc_vazio.json()["completo"] is False
        assert r_inc_vazio.json()["itens"] == []

        # Estado incremental desde v0 traz os 2 itens novos
        r_inc = client.get(f"/api/estado?desde={v0}")
        assert r_inc.status_code == 200
        d_inc = r_inc.json()
        assert d_inc["completo"] is False
        assert {it["arquivo"] for it in d_inc["itens"]} == {"api_folha.jpg", "vazio.pdf"}

        # Mídia existente vs inexistente / rejeitada
        por_nome = {it["arquivo"]: it for it in d_inc["itens"]}
        r_midia_ok = client.get(por_nome["api_folha.jpg"]["midia"])
        assert r_midia_ok.status_code == 200
        assert r_midia_ok.headers["content-type"].startswith("image/")

        r_midia_404 = client.get(f"/api/midia/{por_nome['vazio.pdf']['id']}")
        assert r_midia_404.status_code == 404
        assert client.get("/api/midia/999999").status_code == 404

        # 409 em /api/limpar quando não ocioso
        with motor._lock:
            motor._itens[9999] = {
                "id": 9999,
                "arquivo": "travado.pdf",
                "tipo": "nota",
                "estado": "processando",
                "resumo": "lendo a nota",
                "motivo": None,
                "recebido_em": "2026-11-16T00:00:00Z",
                "duracao_ms": None,
                "midia": None,
                "nota": None,
                "folha": None,
            }
        r_409 = client.post("/api/limpar")
        assert r_409.status_code == 409

        with motor._lock:
            motor._itens.pop(9999, None)

        # Limpar quando ocioso -> 200 + consulta incremental antiga volta completo=True
        r_limpar = client.post("/api/limpar")
        assert r_limpar.status_code == 200
        r_apos_limpar = client.get(f"/api/estado?desde={v_fim}")
        assert r_apos_limpar.status_code == 200
        assert r_apos_limpar.json()["completo"] is True
        assert r_apos_limpar.json()["itens"] == []


def test_api_exemplos_dispara_sem_erro(ambiente_fluxo, monkeypatch):
    motor = Fluxo(iniciar_observador=False, aquecer=False)
    chamadas = []

    def _exemplos_falso():
        chamadas.append(True)
        motor.enviar_arquivos([("anotacoes.txt", b"exemplo rapido")])

    monkeypatch.setattr(motor, "enviar_exemplos", _exemplos_falso)
    app = criar_app(fluxo=motor, iniciar_fluxo=True)

    with TestClient(app) as client:
        r = client.post("/api/exemplos")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
        assert chamadas == [True]
        est = _aguardar_ocioso(motor)
        assert est["itens"][0]["arquivo"] == "anotacoes.txt"
        assert est["itens"][0]["estado"] == "rejeitado"


# ---------- 5. Não-contaminação de evaluate.py e migração SQLite ----------

def test_migracao_automatica_coluna_origem_em_banco_antigo(tmp_path, monkeypatch):
    db = tmp_path / "results" / "agroflow.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as con:
        con.execute(
            """CREATE TABLE resultados (
                arquivo TEXT NOT NULL,
                tipo TEXT NOT NULL,
                campo TEXT NOT NULL,
                valor TEXT,
                confidence REAL,
                backend TEXT NOT NULL,
                duracao_ms REAL,
                processado_em TEXT NOT NULL
            )"""
        )
        con.execute(
            "INSERT INTO resultados VALUES ('nota_001.pdf','nota','numero','10',0.9,'local',2.0,'2026-11-16T00:00:00Z')"
        )

    monkeypatch.setattr(config, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(config, "RESULTS_DB", db)

    storage.save([Row("fluxo.pdf", "nota", "numero", "20", 0.8, origem="fluxo")])
    df = storage.load_dataframe()
    assert "origem" in df.columns
    assert df.set_index("arquivo")["origem"].to_dict() == {
        "nota_001.pdf": "lote",
        "fluxo.pdf": "fluxo",
    }


def test_evaluate_ignora_linhas_com_origem_fluxo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(config, "RESULTS_DB", tmp_path / "results" / "agroflow.db")
    monkeypatch.setattr(config, "REPORT", tmp_path / "report")
    monkeypatch.setattr(evaluate, "FIG", tmp_path / "results" / "figures")
    monkeypatch.setattr(evaluate, "TAB", tmp_path / "report" / "tabelas")
    monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "nao_existe.pt")
    monkeypatch.setattr(config, "DISPUTA", tmp_path / "nao_existe.json")

    # Gabarito mínimo de notas com 1 nota de lote
    gab = tmp_path / "gabarito.csv"
    gab.write_text(
        "arquivo,cnpj_emitente,numero,data_emissao,valor_total,layout,escaneada\n"
        "nota_001.pdf,60.181.590/0001-28,239473,2026-06-15,2896.66,padrao,0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "GABARITO_NOTAS", gab)
    monkeypatch.setattr(config, "GABARITO_NOTAS_TESTE", tmp_path / "gabarito_teste_ausente.csv")

    from agroflow.leaves.conjuntos import CLASSES

    linhas_lote = [
        Row("nota_001.pdf", "nota", "cnpj_emitente", "60.181.590/0001-28", 0.9, origem="lote"),
        Row("nota_001.pdf", "nota", "numero", "239473", 0.9, origem="lote"),
        Row("nota_001.pdf", "nota", "data_emissao", "2026-06-15", 0.9, origem="lote"),
        Row("nota_001.pdf", "nota", "valor_total", "2896.66", 0.9, origem="lote"),
        Row("nota_001.pdf", "nota", "_fonte", "texto", None, origem="lote"),
        Row("campo/val/cercosporiose/v1.jpg", "folha_classificador", "classe", "cercosporiose", 0.95, origem="lote"),
        Row("campo/teste/ferrugem_comum/t1.jpg", "folha_classificador", "classe", "ferrugem_comum", 0.96, origem="lote"),
    ] + [
        Row(f"lab/teste/{c}/x.jpg", "folha_classificador", "classe", c, 0.99, origem="lote")
        for c in CLASSES
    ]
    storage.save(linhas_lote)
    evaluate.main()
    m_sem_fluxo = json.loads((tmp_path / "results" / "metricas.json").read_text(encoding="utf-8"))

    # Agora injeta linhas com origem='fluxo' (inclusive sobrescrevendo o mesmo nome de arquivo com erro!)
    linhas_fluxo = [
        Row("nota_001.pdf", "nota", "valor_total", "0.00", 0.1, origem="fluxo"),
        Row("campo/teste/ferrugem_comum/t1.jpg", "folha_classificador", "classe", "saudavel", 0.99, origem="fluxo"),
        Row("lab/teste/saudavel/x.jpg", "folha_classificador", "classe", "ferrugem_comum", 0.99, origem="fluxo"),
    ]
    storage.save(linhas_fluxo)
    df_carregado = evaluate.carregar()
    assert (df_carregado["origem"] == "lote").all()

    evaluate.main()
    m_com_fluxo = json.loads((tmp_path / "results" / "metricas.json").read_text(encoding="utf-8"))
    assert m_com_fluxo == m_sem_fluxo


# ---------- 6. Verificação de integração estática HTML / CSS / JS <-> API ----------

def test_integracao_estatica_html_css_js_e_api():
    app = criar_app(fluxo=Fluxo(iniciar_observador=False, aquecer=False), iniciar_fluxo=False)
    rotas_api = {
        route.path
        for route in app.routes
        if hasattr(route, "path") and route.path.startswith("/api/")
    }

    # Verifica referências estáticas e ausência de CDNs externos
    for pagina in ("prod.html", "press.html"):
        html = (STATIC_DIR / pagina).read_text(encoding="utf-8")
        assert "http://" not in html and "https://" not in html

        refs = re.findall(r'(?:src|href)=["\'](/static/[^"\']+)["\']', html)
        assert refs, f"{pagina} não referencia arquivos em /static/"
        for ref in refs:
            rel = ref.removeprefix("/static/")
            assert (STATIC_DIR / rel).is_file(), f"{pagina} referencia arquivo inexistente: {ref}"

    # Verifica que todos os IDs buscados via getElementById existem no respectivo HTML
    for pagina, script in (("prod.html", "prod.js"), ("press.html", "press.js")):
        html = (STATIC_DIR / pagina).read_text(encoding="utf-8")
        js = (STATIC_DIR / script).read_text(encoding="utf-8")
        ids_html = set(re.findall(r'id=["\']([^"\']+)["\']', html))
        ids_js = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', js))
        faltando = ids_js - ids_html
        assert not faltando, f"{script} referencia IDs ausentes em {pagina}: {faltando}"

    # Verifica que endpoints usados em api.js existem no FastAPI
    api_js = (STATIC_DIR / "api.js").read_text(encoding="utf-8")
    endpoints_js = set(re.findall(r'["\`](/api/[a-zA-Z0-9_]+)', api_js))
    assert endpoints_js <= rotas_api, f"Endpoints em api.js ausentes no FastAPI: {endpoints_js - rotas_api}"

    # Verifica contratos de campo entre JS (api.js, detalhe.js, prod.js, press.js) e backend
    assert "desde=" in api_js
    assert 'form.append("arquivos"' in api_js

    detalhe_js = (STATIC_DIR / "detalhe.js").read_text(encoding="utf-8")
    for campo_contrato in (
        "nota.fonte",
        "nota.campos",
        "folha.limiar",
        "folha.confianca",
        "folha.probabilidades",
        "folha.linha_de_base",
        "item.midia",
        "item.motivo",
        "item.duracao_ms",
        "nao_encontrado",
        "baixa",
    ):
        assert campo_contrato in detalhe_js, f"detalhe.js deve tratar {campo_contrato}"

    # Verifica CSS sem URLs externas
    for css_name in ("tokens.css", "prod.css", "press.css"):
        css = (STATIC_DIR / css_name).read_text(encoding="utf-8")
        assert "http://" not in css and "https://" not in css

    # Se node estiver disponível, valida sintaxe de todos os scripts JS
    node = shutil.which("node")
    if node:
        for js_name in ("api.js", "detalhe.js", "prod.js", "press.js"):
            res = subprocess.run([node, "--check", str(STATIC_DIR / js_name)], capture_output=True, text=True)
            assert res.returncode == 0, f"Erro de sintaxe em {js_name}: {res.stderr}"

    # Servir assets via TestClient
    with TestClient(app) as client:
        for asset in ("tokens.css", "api.js", "detalhe.js", "prod.css", "prod.js", "press.css", "press.js"):
            resp = client.get(f"/static/{asset}")
            assert resp.status_code == 200, asset
