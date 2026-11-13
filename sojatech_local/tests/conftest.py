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
