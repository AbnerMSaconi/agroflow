from .. import config
from . import gcp_models as _m


def baseline(path, k=5):
    """Rótulos genéricos da Vision API: [(rótulo, score), ...]."""
    return _m.baseline(path, k)


def classificador_disponivel() -> bool:
    """O classificador só existe enquanto houver endpoint do Vertex implantado."""
    return bool(config.VERTEX_ENDPOINT_ID)


def classify(path):
    """Classe de doença pelo endpoint do Vertex: (classe, confidence, {classe: prob})."""
    return _m.classify(path)
