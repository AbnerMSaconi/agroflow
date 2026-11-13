"""Configuração central do projeto local (sem nenhum serviço pago).

ROOT é a pasta sojatech_local/; os dados e o relatório ficam na raiz do
repositório (REPO) porque o projeto sojatech_cloud usa os mesmos conjuntos.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
BACKEND = "local"

DATA = REPO / "data"
INVOICES_DIR = DATA / "invoices"
GABARITO_NOTAS = INVOICES_DIR / "gabarito.csv"
# conjunto de teste: outro seed e um layout que o extrator nunca viu
INVOICES_TEST_DIR = INVOICES_DIR / "teste"
GABARITO_NOTAS_TESTE = INVOICES_TEST_DIR / "gabarito.csv"
LEAVES_DIR = DATA / "leaves"
MANIFESTO_LAB = LEAVES_DIR / "manifesto_lab.csv"  # PlantVillage: treino, val (fixa) e teste
CAMPO_DIR = LEAVES_DIR / "campo"  # PlantDoc: fotos de campo
MANIFESTO_CAMPO = CAMPO_DIR / "manifesto.csv"
DOWNLOADS = REPO / "_downloads"
REPORT = REPO / "report"

BUCKET = ROOT / "bucket"  # pasta observada pelo watcher
RESULTS = ROOT / "results"
RESULTS_DB = RESULTS / "agroflow.db"
MODELS = ROOT / "models"
LEAF_MODEL = MODELS / "leaf_classifier.pt"  # lab+campo: o modelo do produto
LEAF_MODEL_LAB = MODELS / "leaf_classifier_lab.pt"  # só laboratório, para medir a queda no campo
DISPUTA = RESULTS / "disputa_redes.json"

PDF_EXT = {".pdf"}
IMAGE_EXT = {".jpg", ".jpeg", ".png"}
