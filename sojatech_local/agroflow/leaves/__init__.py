from . import local_models as _m


def baseline(path, k=5):
    """Rótulos genéricos com score: [(rótulo, score), ...]."""
    return _m.baseline(path, k)


def classificador_disponivel() -> bool:
    return True


def classify(path):
    """Classe de doença: (classe, confidence, {classe: prob})."""
    return _m.classify(path)
