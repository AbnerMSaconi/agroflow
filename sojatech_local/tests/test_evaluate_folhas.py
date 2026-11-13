"""Avaliação das folhas por conjunto: limiar da validação, campo sem saudável, nomes."""
import hashlib
import json

import pandas as pd
import pytest

import evaluate
from agroflow import config, storage
from agroflow.leaves.conjuntos import CLASSES
from agroflow.storage import Row
from evaluate import avalia_classificador, folhas, limiar_validacao, tabela_lab_vs_campo


def linha(conjunto, particao, real, previsto, conf, tipo="folha_classificador"):
    """Uma linha como as gravadas no SQLite."""
    return dict(arquivo=f"{conjunto}/{particao}/{real}/{real}_x.jpg", tipo=tipo, campo="classe", valor=previsto,
                confidence=conf, backend="local", duracao_ms=1.0, processado_em="2026-11-13T00:00:00+00:00")


def test_saudavel_previsto_no_campo_e_erro():
    df = pd.DataFrame([linha("campo", "teste", "ferrugem_comum", "ferrugem_comum", .9),
                       linha("campo", "teste", "cercosporiose", "saudavel", .8),
                       linha("campo", "teste", "helmintosporiose", "helmintosporiose", .7)])
    r = avalia_classificador(df, "folha_classificador", "campo", limiar=0.5, gravar=False)
    assert r["acuracia"] == pytest.approx(2 / 3)
    assert set(r["por_classe"]) == {"cercosporiose", "ferrugem_comum", "helmintosporiose"}
    assert r["matriz_confusao"]["previstas"] == CLASSES and r["matriz_confusao"]["valores"][0][3] == 1


def test_limiar_vem_da_validacao_de_campo():
    val = [linha("campo", "val", "cercosporiose", "ferrugem_comum", c) for c in (.55, .60)] + \
          [linha("campo", "val", "cercosporiose", "cercosporiose", c) for c in (.7, .8, .9)]
    teste = [linha("campo", "teste", "cercosporiose", "helmintosporiose", .9)]
    df = pd.DataFrame(val + teste)
    lim = limiar_validacao(folhas(df, "folha_classificador"), "campo")
    assert lim == pytest.approx(0.65)
    r = avalia_classificador(df, "folha_classificador", "campo", lim, gravar=False)
    assert r["limiar"] == pytest.approx(0.65) and r["com_limiar"]["erros_passaram"] == 1


def test_nomes_sem_conjunto_sao_ignorados():
    boa = linha("campo", "teste", "cercosporiose", "cercosporiose", .9)
    df = pd.DataFrame([boa, {**boa, "arquivo": "demo_folha.jpg"}, {**boa, "arquivo": "cercosporiose/x.jpg"}])
    assert list(folhas(df, "folha_classificador").arquivo) == ["campo/teste/cercosporiose/cercosporiose_x.jpg"]


def test_tabela_lab_vs_campo_conta_erros_barrados():
    r = dict(limiar=0.9, acuracia=0.5, f1_macro=0.4, conf_media_errados=0.8, ece=0.3,
             com_limiar=dict(erros_barrados=3, erros_passaram=9))
    t = tabela_lab_vs_campo({"classificador_campo": r})
    assert t.to_dict(orient="records") == [{
        "Modelo": "lab+campo (produto)", "Teste": "campo", "Limiar": 0.9, "Acurácia": 0.5, "F1 macro": 0.4,
        "Conf. dos erros": 0.8, "ECE": 0.3, "Erros barrados": "3 de 12"}]


def test_main_liga_cada_modelo_ao_seu_limiar(tmp_path, monkeypatch):
    """Ponta a ponta com o SQLite real numa pasta temporária: limiares, hash, tabelas e figuras novas."""
    monkeypatch.setattr(config, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(config, "RESULTS_DB", tmp_path / "results" / "agroflow.db")
    monkeypatch.setattr(config, "REPORT", tmp_path / "report")
    monkeypatch.setattr(evaluate, "FIG", tmp_path / "results" / "figures")
    monkeypatch.setattr(evaluate, "TAB", tmp_path / "report" / "tabelas")
    (tmp_path / "m.pt").write_bytes(b"modelo")
    monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "m.pt")
    monkeypatch.setattr(config, "DISPUTA", tmp_path / "disputa.json")
    (tmp_path / "disputa.json").write_text(json.dumps({"vencedora": "convnext_small", "candidatas": [
        dict(rede="convnext_small", f1_val_campo=0.8, f1_val_lab=0.99, n_parametros=50_223_688, tempo_treino_s=300)]}))

    def r(tipo, conjunto, particao, real, previsto, conf):
        return Row(f"{conjunto}/{particao}/{real}/{real}_{conf}.jpg", tipo, "classe", previsto, conf)

    prod, lab = "folha_classificador", "folha_classificador_lab"
    linhas = [r(prod, "campo", "val", "cercosporiose", "ferrugem_comum", c) for c in (.55, .60)]  # limiar 0.65
    linhas += [r(prod, "campo", "val", "cercosporiose", "cercosporiose", c) for c in (.7, .8, .9)]
    linhas += [r(lab, "lab", "val", "saudavel", "ferrugem_comum", .85)]  # limiar 0.9
    linhas += [r(lab, "lab", "val", "saudavel", "saudavel", c) for c in (.9, .95)]
    for tipo in (prod, lab):
        linhas += [r(tipo, "lab", "teste", c, c, .99) for c in CLASSES]
        linhas += [r(tipo, "campo", "teste", "ferrugem_comum", "ferrugem_comum", .95),
                   r(tipo, "campo", "teste", "helmintosporiose", "saudavel", .92)]
    linhas += [Row("lab/teste/saudavel/s.jpg", "folha_baseline", "rotulo_1", "corn", .6),
               Row("campo/teste/ferrugem_comum/f.jpg", "folha_baseline", "rotulo_1", "leaf", .5),
               Row("demo_folha.jpg", prod, "classe", "saudavel", .9)]  # demo pelo bucket: fica de fora
    storage.save(linhas)

    evaluate.main()
    m = json.loads((tmp_path / "results" / "metricas.json").read_text(encoding="utf-8"))
    assert m["classificador"]["limiar_escolhido"] == pytest.approx(0.65)
    assert m["classificador_campo"]["limiar"] == pytest.approx(0.65)
    assert m["classificador_lab"]["campo"]["limiar"] == pytest.approx(0.9)
    assert m["classificador_lab"]["campo"]["com_limiar"]["erros_passaram"] == 1  # 0.92 passa no 0.9 do lab
    assert m["classificador_campo"]["n_imagens"] == 2 and m["classificador"]["n_imagens"] == 4
    assert m["modelo_avaliado_sha256"] == hashlib.sha256(b"modelo").hexdigest()
    assert m["disputa"]["vencedora"] == "convnext_small" and m["baseline_campo"]["n_imagens"] == 1
    for f in ("report/tabelas/folhas_lab_vs_campo.tex", "report/tabelas/disputa_redes.tex",
              "report/tabelas/folhas_por_classe_campo.tex", "report/figuras/folhas_calibracao_lab_no_campo.png",
              "report/figuras/folhas_matriz_confusao_campo.png"):
        assert (tmp_path / f).is_file(), f
    assert "teste de campo" in (tmp_path / "results" / "resumo.md").read_text(encoding="utf-8")
