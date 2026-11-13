def extract(path):
    """Campos da DANFE: ({campo: (valor, conf)}, fonte)."""
    from .local_extractor import extract as _extract

    return _extract(path)
