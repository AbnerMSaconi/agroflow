"""Configuração dos testes: caminhos de import e imagens sintéticas."""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
for _p in (RAIZ / "scripts", RAIZ):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _fazer_imagem(caminho, semente: int, tamanho=(64, 64), modo="RGB") -> Path:
    """Grava um padrão suave e determinístico: ruído 8×8 ampliado com BICUBIC.

    Ruído puro não serve para testar hash perceptual, porque a recompressão muda o
    dHash dele. O formato sai da extensão do caminho.
    """
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    ruido = np.random.default_rng(semente).integers(0, 256, (8, 8, 3), dtype=np.uint8)
    img = Image.fromarray(ruido).resize(tuple(tamanho), Image.Resampling.BICUBIC).convert(modo)
    img.save(caminho)
    return caminho


@pytest.fixture
def fazer_imagem():
    return _fazer_imagem


@pytest.fixture
def manifestos_falsos(tmp_path, monkeypatch, fazer_imagem):
    """2 fotos por classe em cada partição: lab (4 classes) e campo (3 classes, sem saudável)."""
    from agroflow import config
    from agroflow.leaves.conjuntos import CLASSES, escrever_manifesto

    lab, campo = tmp_path / "leaves", tmp_path / "leaves" / "campo"
    semente = iter(range(1, 10_000))
    linhas_lab, linhas_campo = [], []
    for particao in ("treino", "val", "teste"):
        for classe in CLASSES:
            for i in range(2):
                arq = f"{'test' if particao == 'teste' else 'train'}/{classe}/{classe}_{particao}_{i}.jpg"
                fazer_imagem(lab / arq, next(semente))
                linhas_lab.append(dict(arquivo=arq, classe=classe, particao=particao))
                if classe != "saudavel":
                    arq = f"{particao}/{classe}/{classe}_campo_{particao}_{i}.jpg"
                    fazer_imagem(campo / arq, next(semente))
                    linhas_campo.append(dict(arquivo=arq, classe=classe, particao=particao))
    escrever_manifesto(lab / "manifesto_lab.csv", linhas_lab)
    escrever_manifesto(campo / "manifesto.csv", linhas_campo)
    monkeypatch.setattr(config, "LEAVES_DIR", lab)
    monkeypatch.setattr(config, "MANIFESTO_LAB", lab / "manifesto_lab.csv")
    monkeypatch.setattr(config, "CAMPO_DIR", campo)
    monkeypatch.setattr(config, "MANIFESTO_CAMPO", campo / "manifesto.csv")
    return lab
