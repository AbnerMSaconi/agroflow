def extract(path):
    """Campos da DANFE pelo Document AI: ({campo: (valor, conf)}, fonte)."""
    from .docai_extractor import extract as _extract

    return _extract(path)
