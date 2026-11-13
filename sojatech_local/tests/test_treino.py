"""Treino: mistura lab/campo, acumulação, escolha da rede e o arquivo de modelo gerado."""
import hashlib

import torch

from agroflow.leaves import conjuntos, treino
from agroflow.leaves.conjuntos import CLASSES
from agroflow.leaves.treino import escolher_vencedora, passos_acumulacao, pesos_amostragem, treinar


def test_fracao_de_campo():
    w = pesos_amostragem(["lab"] * 90 + ["campo"] * 10)
    assert abs(sum(w[90:]) / sum(w) - 1 / 3) < 1e-9
    assert set(pesos_amostragem(["lab"] * 5)) == {1.0}


def test_passos_acumulacao():
    assert (passos_acumulacao(32, 8), passos_acumulacao(32, 32), passos_acumulacao(32, 12)) == (4, 1, 3)


def test_empate_vai_para_a_mais_leve():
    r = [dict(rede="vit_b_16", f1_val_campo=0.80, n_parametros=86_000_000),
         dict(rede="convnext_small", f1_val_campo=0.79, n_parametros=50_000_000),
         dict(rede="efficientnet_b0", f1_val_campo=0.70, n_parametros=5_000_000)]
    assert escolher_vencedora(r) == "convnext_small"


def test_treino_relampago_gera_modelo_carregavel(tmp_path, manifestos_falsos):
    info = treinar("efficientnet_b0", "lab+campo", tmp_path / "m.pt", epocas=1, lote=4, pretreinada=False, workers=0)
    ck = torch.load(tmp_path / "m.pt")
    assert (ck["rede"], ck["classes"], ck["resolucao"]) == ("efficientnet_b0", CLASSES, 224)
    assert info["val"]["campo"] is not None
    assert info["sha256"] == hashlib.sha256((tmp_path / "m.pt").read_bytes()).hexdigest()


def test_modelo_lab_nunca_le_campo(tmp_path, manifestos_falsos, monkeypatch):
    original = conjuntos.itens

    def vigiado(conjunto, particao):
        assert conjunto != "campo"
        return original(conjunto, particao)

    monkeypatch.setattr(treino.conjuntos, "itens", vigiado)
    info = treinar("efficientnet_b0", "lab", tmp_path / "m.pt", epocas=1, lote=4, pretreinada=False, workers=0)
    assert info["val"]["campo"] is None


def test_max_por_classe_corta_cada_lista(tmp_path, manifestos_falsos):
    info = treinar("efficientnet_b0", "lab+campo", tmp_path / "m.pt", epocas=1, lote=4, pretreinada=False,
                   workers=0, max_por_classe=1)
    assert info["n_treino"] == {"lab": 4, "campo": 3} and info["n_val"] == {"lab": 4, "campo": 3}


def test_epoca_escolhida_e_a_de_maior_f1_no_campo(tmp_path, manifestos_falsos):
    info = treinar("efficientnet_b0", "lab+campo", tmp_path / "m.pt", epocas=3, lote=4, pretreinada=False, workers=0)
    f1 = [h["val"]["campo"]["f1_macro"] for h in info["historico"]]
    assert len(f1) == 3 and f1[info["melhor_epoca"] - 1] == max(f1)
    assert info["val"]["campo"] == info["historico"][info["melhor_epoca"] - 1]["val"]["campo"]
