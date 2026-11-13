"""Inferência: a rede, a resolução e as classes vêm do arquivo do modelo."""
import hashlib
import json

import pytest
import torch

from agroflow import config
from agroflow.leaves import classificador_disponivel, classify, local_models, modelo_confere
from agroflow.leaves.conjuntos import CLASSES
from agroflow.leaves.redes import construir_rede, resolucao


@pytest.fixture(autouse=True)
def cache_limpo():
    local_models._classifier.cache_clear()
    yield
    local_models._classifier.cache_clear()


def salvar_ck(caminho, rede, classes, com_rede=True):
    ck = {"classes": classes, "state_dict": construir_rede(rede, len(classes), False).state_dict()}
    if com_rede:
        ck |= {"rede": rede, "resolucao": resolucao(rede)}
    torch.save(ck, caminho)


@pytest.mark.parametrize("rede", ["efficientnet_b0", "efficientnet_v2_s", "convnext_small", "vit_b_16"])
def test_checkpoint_novo(tmp_path, monkeypatch, fazer_imagem, rede):
    salvar_ck(tmp_path / "p.pt", rede, CLASSES)
    monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "p.pt")
    classe, conf, probs = classify(fazer_imagem(tmp_path / "f.jpg", 3))
    assert classe in CLASSES and 0 <= conf <= 1 and abs(sum(probs.values()) - 1) < 1e-3


def test_checkpoint_antigo_sem_rede(tmp_path, monkeypatch, fazer_imagem):
    salvar_ck(tmp_path / "v.pt", "efficientnet_b0", CLASSES, com_rede=False)
    monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "v.pt")
    assert classify(fazer_imagem(tmp_path / "f.jpg", 3))[0] in CLASSES


def test_modelo_lab_usa_outro_arquivo(tmp_path, monkeypatch, fazer_imagem):
    salvar_ck(tmp_path / "l.pt", "efficientnet_b0", CLASSES[::-1])
    monkeypatch.setattr(config, "LEAF_MODEL_LAB", tmp_path / "l.pt")
    assert list(classify(fazer_imagem(tmp_path / "f.jpg", 3), modelo="lab")[2]) == CLASSES[::-1]


def test_modelo_retreinado_no_mesmo_caminho_e_relido(tmp_path, monkeypatch, fazer_imagem):
    monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "p.pt")
    foto = fazer_imagem(tmp_path / "f.jpg", 3)
    salvar_ck(tmp_path / "p.pt", "efficientnet_b0", CLASSES)
    assert list(classify(foto)[2]) == CLASSES
    salvar_ck(tmp_path / "p.pt", "efficientnet_b0", CLASSES[::-1])
    assert list(classify(foto)[2]) == CLASSES[::-1]


def test_disponivel_e_confere(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "nao.pt")
    assert not classificador_disponivel() and modelo_confere() is None
    (tmp_path / "m.pt").write_bytes(b"pesos")
    monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "m.pt")
    monkeypatch.setattr(config, "RESULTS", tmp_path)
    (tmp_path / "metricas.json").write_text(json.dumps({"modelo_avaliado_sha256": hashlib.sha256(b"pesos").hexdigest()}))
    assert classificador_disponivel() and modelo_confere() is True
    (tmp_path / "m.pt").write_bytes(b"outros")
    assert modelo_confere() is False
