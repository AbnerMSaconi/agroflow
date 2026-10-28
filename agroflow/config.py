"""Configuração central.

AGROFLOW_BACKEND escolhe quem faz o trabalho pesado:
  local -> substitutos que rodam na máquina (padrão, custo zero)
  gcp   -> Document AI, Vision API, Vertex AI e BigQuery de verdade
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = os.getenv("AGROFLOW_BACKEND", "local")

DATA = ROOT / "data"
INVOICES_DIR = DATA / "invoices"
GABARITO_NOTAS = INVOICES_DIR / "gabarito.csv"
LEAVES_DIR = DATA / "leaves"

BUCKET = ROOT / "bucket"  # espelho local do bucket de entrada
RESULTS = ROOT / "results"
RESULTS_DB = RESULTS / "agroflow.db"
MODELS = ROOT / "models"
LEAF_MODEL = MODELS / "leaf_classifier.pt"

PDF_EXT = {".pdf"}
IMAGE_EXT = {".jpg", ".jpeg", ".png"}

# GCP (só usados com AGROFLOW_BACKEND=gcp)
GCP_PROJECT = os.getenv("GCP_PROJECT", "")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us")
DOCAI_PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID", "")
VERTEX_REGION = os.getenv("VERTEX_REGION", "us-central1")
VERTEX_ENDPOINT_ID = os.getenv("VERTEX_ENDPOINT_ID", "")
BQ_TABLE = os.getenv("BQ_TABLE", "agroflow.resultados")
