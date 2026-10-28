"""Substitutos locais da Vision API e do Vertex AI AutoML.

- baseline(): ResNet-50 pré-treinada no ImageNet devolvendo os 5 rótulos mais
  prováveis. Faz o papel da *label detection*: rótulos genéricos com score
  alto, sem saber nada de doença de folha.
- classify(): rede fine-tunada em scripts/train_leaf_classifier.py (transfer
  learning, a mesma ideia do AutoML Image Classification).
"""
from functools import lru_cache

import torch
from PIL import Image

from .. import config

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache
def _baseline_model():
    from torchvision.models import ResNet50_Weights, resnet50

    w = ResNet50_Weights.IMAGENET1K_V2
    return resnet50(weights=w).eval().to(DEVICE), w.transforms(), w.meta["categories"]


@torch.no_grad()
def baseline(path, k=5) -> list[tuple[str, float]]:
    model, tf, cats = _baseline_model()
    x = tf(Image.open(path).convert("RGB")).unsqueeze(0).to(DEVICE)
    p = model(x).softmax(1)[0]
    top = p.topk(k)
    return [(cats[i], round(float(s), 4)) for s, i in zip(top.values, top.indices)]


def build_classifier(n_classes: int):
    from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0

    m = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
    m.classifier[1] = torch.nn.Linear(m.classifier[1].in_features, n_classes)
    return m


def classifier_transform(train=False):
    from torchvision import transforms as T

    norm = T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    if train:
        return T.Compose([T.RandomResizedCrop(224, scale=(0.7, 1.0)), T.RandomHorizontalFlip(),
                          T.RandomVerticalFlip(), T.ColorJitter(0.2, 0.2, 0.2), T.ToTensor(), norm])
    return T.Compose([T.Resize(256), T.CenterCrop(224), T.ToTensor(), norm])


@lru_cache
def _classifier():
    ck = torch.load(config.LEAF_MODEL, map_location=DEVICE)
    m = build_classifier(len(ck["classes"]))
    m.load_state_dict(ck["state_dict"])
    return m.eval().to(DEVICE), ck["classes"]


@torch.no_grad()
def classify(path) -> tuple[str, float, dict]:
    model, classes = _classifier()
    x = classifier_transform()(Image.open(path).convert("RGB")).unsqueeze(0).to(DEVICE)
    p = model(x).softmax(1)[0].tolist()
    i = max(range(len(p)), key=p.__getitem__)
    return classes[i], round(p[i], 4), dict(zip(classes, (round(v, 4) for v in p)))
