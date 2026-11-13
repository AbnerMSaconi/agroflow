"""Redes candidatas do torchvision para o classificador de folhas.

Cada rede traz dos pesos do torchvision a resolução e a normalização com que foi
treinada no ImageNet. `lote` é o micro-lote que cabe numa GPU de 8 GB com precisão
mista; o treino completa o lote efetivo com acumulação de gradiente.
"""
from typing import Callable

from torch import nn
from torchvision import models
from torchvision import transforms as T

REDES = {
    "efficientnet_b0": dict(pesos=models.EfficientNet_B0_Weights.IMAGENET1K_V1, lote=32),
    "efficientnet_v2_s": dict(pesos=models.EfficientNet_V2_S_Weights.IMAGENET1K_V1, lote=16),
    "convnext_small": dict(pesos=models.ConvNeXt_Small_Weights.IMAGENET1K_V1, lote=32),
    "vit_b_16": dict(pesos=models.ViT_B_16_Weights.IMAGENET1K_SWAG_E2E_V1, lote=8),
}
REDE_PADRAO = "efficientnet_b0"


def resolucao(nome: str) -> int:
    return REDES[nome]["pesos"].transforms().crop_size[0]


def n_parametros(nome: str) -> int:
    return REDES[nome]["pesos"].meta["num_params"]


def construir_rede(nome: str, n_classes: int, pretreinada: bool = True) -> nn.Module:
    """A rede com a última camada trocada por uma de `n_classes` saídas.

    pretreinada=False não baixa nada: serve para carregar pesos já ajustados.
    """
    extra = {"image_size": resolucao(nome)} if nome.startswith("vit") else {}
    m = models.get_model(nome, weights=REDES[nome]["pesos"] if pretreinada else None, **extra)
    if nome.startswith("efficientnet"):
        m.classifier[1] = nn.Linear(m.classifier[1].in_features, n_classes)
    elif nome.startswith("convnext"):
        m.classifier[2] = nn.Linear(m.classifier[2].in_features, n_classes)
    else:
        m.heads.head = nn.Linear(m.heads.head.in_features, n_classes)
    return m


def transformacoes(nome: str, treino: bool) -> Callable:
    """Pré-processamento dos pesos da rede; no treino, aumento de dados que imita foto de campo."""
    base = REDES[nome]["pesos"].transforms()
    if not treino:
        return base
    return T.Compose([
        T.RandomResizedCrop(resolucao(nome), scale=(0.6, 1.0), interpolation=base.interpolation),
        T.RandomHorizontalFlip(),
        T.RandomVerticalFlip(),
        T.TrivialAugmentWide(),
        T.ColorJitter(0.2, 0.2, 0.2),
        T.RandomApply([T.GaussianBlur(5)], p=0.2),
        T.ToTensor(),
        T.Normalize(base.mean, base.std),
        T.RandomErasing(p=0.25),
    ])
