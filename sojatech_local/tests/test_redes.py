"""Redes candidatas: cabeça de 4 classes, resolução e pré-processamento de cada uma."""
import pytest
import torch
from PIL import Image

from agroflow.leaves.redes import construir_rede, n_parametros, resolucao, transformacoes

PARES = [("efficientnet_b0", 224), ("efficientnet_v2_s", 384), ("convnext_small", 224), ("vit_b_16", 384)]


@pytest.mark.parametrize("nome,res", PARES)
def test_rede_sem_pesos_da_4_saidas(nome, res):
    m = construir_rede(nome, 4, pretreinada=False).eval()
    with torch.no_grad():
        assert m(torch.zeros(1, 3, res, res)).shape == (1, 4)
    assert resolucao(nome) == res


@pytest.mark.parametrize("nome,res", PARES)
def test_transformacoes_no_tamanho_da_rede(nome, res):
    img = Image.new("RGB", (300, 500))
    assert transformacoes(nome, False)(img).shape == transformacoes(nome, True)(img).shape == (3, res, res)


def test_ordem_de_tamanho():
    assert (n_parametros("efficientnet_b0") < n_parametros("efficientnet_v2_s")
            < n_parametros("convnext_small") < n_parametros("vit_b_16"))
