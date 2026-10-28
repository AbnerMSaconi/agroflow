from .. import config


def _impl():
    if config.BACKEND == "gcp":
        from . import gcp_models as m
    else:
        from . import local_models as m
    return m


def baseline(path, k=5):
    """Rótulos genéricos com score: [(rótulo, score), ...]."""
    return _impl().baseline(path, k)


def classify(path):
    """Classe de doença: (classe, confidence, {classe: prob})."""
    return _impl().classify(path)
