"""Configuração do projeto em nuvem (Document AI, Vision API, Vertex AI, BigQuery).

Projeto arquivado: a conta GCP não ficou disponível, o trabalho roda pelo
sojatech_local. Este código fica pronto para quando houver créditos.

ROOT é a pasta sojatech_cloud/; dados e relatório ficam na raiz do repositório
(REPO), compartilhados com o sojatech_local.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
BACKEND = "gcp"

DATA = REPO / "data"
INVOICES_DIR = DATA / "invoices"
GABARITO_NOTAS = INVOICES_DIR / "gabarito.csv"
INVOICES_TEST_DIR = INVOICES_DIR / "teste"
GABARITO_NOTAS_TESTE = INVOICES_TEST_DIR / "gabarito.csv"
LEAVES_DIR = DATA / "leaves"
REPORT = REPO / "report"

RESULTS = ROOT / "results"
# resultados do sojatech_local, só lidos para a comparação Google vs. local
LOCAL_RESULTS_DB = REPO / "sojatech_local" / "results" / "agroflow.db"

PDF_EXT = {".pdf"}
IMAGE_EXT = {".jpg", ".jpeg", ".png"}

GCP_PROJECT = os.getenv("GCP_PROJECT", "")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us")
DOCAI_PROCESSOR_ID = os.getenv("DOCAI_PROCESSOR_ID", "")
VERTEX_REGION = os.getenv("VERTEX_REGION", "us-central1")
VERTEX_ENDPOINT_ID = os.getenv("VERTEX_ENDPOINT_ID", "")
BQ_TABLE = os.getenv("BQ_TABLE", "agroflow.resultados")
