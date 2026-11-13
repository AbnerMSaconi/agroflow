"""Disputa entre redes: a vencedora vira o modelo do produto; a rodada rápida não toca em nada."""
import hashlib
import json

import pytest

import disputa_redes
from agroflow import config


@pytest.fixture
def destinos(tmp_path, monkeypatch, manifestos_falsos):
    monkeypatch.setattr(config, "MODELS", tmp_path / "models")
    monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "models" / "leaf_classifier.pt")
    monkeypatch.setattr(config, "DISPUTA", tmp_path / "results" / "disputa_redes.json")
    return tmp_path


def test_disputa_copia_a_vencedora_para_o_produto(destinos):
    r = disputa_redes.disputar(["efficientnet_b0"], epocas=1, pretreinada=False, workers=0)
    assert r["vencedora"] == "efficientnet_b0" and len(r["candidatas"]) == 1
    assert json.loads(config.DISPUTA.read_text(encoding="utf-8"))["vencedora"] == "efficientnet_b0"
    assert config.LEAF_MODEL.read_bytes() == (destinos / "models/disputa/efficientnet_b0.pt").read_bytes()
    info = json.loads(config.LEAF_MODEL.with_suffix(".json").read_text(encoding="utf-8"))
    assert info["sha256"] == hashlib.sha256(config.LEAF_MODEL.read_bytes()).hexdigest()


def test_disputa_rapida_nao_toca_no_produto(destinos):
    disputa_redes.disputar(["efficientnet_b0"], rapido=True, pretreinada=False, workers=0)
    assert (destinos / "models/disputa_rapida/efficientnet_b0.pt").exists()
    assert not config.LEAF_MODEL.exists() and not config.DISPUTA.exists()
