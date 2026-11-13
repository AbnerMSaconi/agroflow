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
DOWNLOADS = REPO / "_downloads"
REPORT = REPO / "report"

BUCKET = ROOT / "bucket"  # pasta observada pelo watcher
RESULTS = ROOT / "results"
RESULTS_DB = RESULTS / "agroflow.db"
MODELS = ROOT / "models"
LEAF_MODEL = MODELS / "leaf_classifier.pt"

PDF_EXT = {".pdf"}
IMAGE_EXT = {".jpg", ".jpeg", ".png"}
