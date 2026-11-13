"""Substitutos locais da Vision API e do Vertex AI AutoML.

- baseline(): ResNet-50 pré-treinada no ImageNet devolvendo os 5 rótulos mais
  prováveis. Faz o papel da *label detection*: rótulos genéricos com score
  alto, sem saber nada de doença de folha.
- classify(): rede ajustada por scripts/train_leaf_classifier.py (transfer
  learning, a mesma ideia do AutoML Image Classification). O arquivo do modelo
  diz qual rede é, as classes e a resolução; "produto" é o modelo lab+campo e
  "lab" o treinado só com fotos de laboratório.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import torch
from PIL import Image

from .. import config
from .redes import construir_rede, transformacoes

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODELOS = {"produto": "LEAF_MODEL", "lab": "LEAF_MODEL_LAB"}  # nome -> atributo do config


@lru_cache
def _baseline_model():
    from torchvision.models import ResNet50_Weights, resnet50

    w = ResNet50_Weights.IMAGENET1K_V2
    return resnet50(weights=w).eval().to(DEVICE), w.transforms(), w.meta["categories"]


@torch.no_grad()
def baseline(path, k=5) -> list[tuple[str, float]]:
    model, tf, cats = _baseline_model()
    with Image.open(path) as im:
        x = tf(im.convert("RGB")).unsqueeze(0).to(DEVICE)
    p = model(x).softmax(1)[0]
    top = p.topk(k)
    return [(cats[i], round(float(s), 4)) for s, i in zip(top.values, top.indices)]


def _caminho(modelo: str) -> Path:
    return getattr(config, MODELOS[modelo])


@lru_cache(maxsize=4)
def _classifier(caminho: str, versao: int):
    """Rede pronta para inferir. `versao` (mtime) faz um arquivo retreinado ser relido."""
    ck = torch.load(caminho, map_location=DEVICE)
    rede = ck.get("rede", "efficientnet_b0")  # arquivos antigos só tinham a EfficientNet-B0
    m = construir_rede(rede, len(ck["classes"]), pretreinada=False)  # sem baixar pesos do ImageNet
    m.load_state_dict(ck["state_dict"])
    return m.eval().to(DEVICE), ck["classes"], transformacoes(rede, treino=False)


@torch.no_grad()
def classify(path, modelo: str = "produto") -> tuple[str, float, dict]:
    caminho = _caminho(modelo)
    model, classes, tf = _classifier(str(caminho), caminho.stat().st_mtime_ns)
    with Image.open(path) as im:
        x = tf(im.convert("RGB")).unsqueeze(0).to(DEVICE)
    p = model(x).softmax(1)[0].tolist()
    i = max(range(len(p)), key=p.__getitem__)
    return classes[i], round(p[i], 4), dict(zip(classes, (round(v, 4) for v in p)))


def classificador_disponivel(modelo: str = "produto") -> bool:
    return _caminho(modelo).exists()


def sha256_arquivo(caminho) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def modelo_confere() -> bool | None:
    """O modelo do produto é o mesmo que gerou results/metricas.json? None se faltar um dos dois."""
    metricas = config.RESULTS / "metricas.json"
    if not config.LEAF_MODEL.exists() or not metricas.exists():
        return None
    esperado = json.loads(metricas.read_text(encoding="utf-8")).get("modelo_avaliado_sha256")
    return None if not esperado else sha256_arquivo(config.LEAF_MODEL) == esperado
