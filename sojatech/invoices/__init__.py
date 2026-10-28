from .. import config


def extract(path):
    """Campos da DANFE pelo backend configurado: ({campo: (valor, conf)}, fonte)."""
    if config.BACKEND == "gcp":
        from .docai_extractor import extract as _extract
    else:
        from .local_extractor import extract as _extract
    return _extract(path)
