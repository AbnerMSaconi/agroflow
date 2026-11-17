def extract(path):
    """Campos da DANFE: ({campo: (valor, conf)}, fonte)."""
    from .local_extractor import extract as _extract

    return _extract(path)


def extract_detalhado(path):
    """Campos da DANFE com caixas: ({campo: (valor, conf, caixa_pct)}, fonte, (largura_pt, altura_pt))."""
    from .local_extractor import extract_detalhado as _extract_detalhado

    return _extract_detalhado(path)
