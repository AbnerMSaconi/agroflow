from . import local_models as _m


def baseline(path, k=5):
    """Rótulos genéricos com score: [(rótulo, score), ...]."""
    return _m.baseline(path, k)


def classificador_disponivel(modelo: str = "produto") -> bool:
    """modelo: "produto" (lab+campo, o das telas) ou "lab" (só laboratório)."""
    return _m.classificador_disponivel(modelo)


def classify(path, modelo: str = "produto"):
    """Classe de doença: (classe, confidence, {classe: prob})."""
    return _m.classify(path, modelo)


def modelo_confere():
    """True/False: o modelo do produto é o avaliado em results/metricas.json; None se não dá para saber."""
    return _m.modelo_confere()
