#!/usr/bin/env bash
# Lab B (GSP1139): Document AI nas notas fiscais. Roda no Cloud Shell, depois do zip descompactado
# e de criar o processador INVOICE PARSER no console (copie o ID dele).
#
#   cd sojatech_cloud && bash scripts/lab_b.sh <ID_DO_PROCESSADOR> [REGIAO]
#
# REGIAO é a do processador (padrão us). Primeiro um teste rápido em 3 notas da validação, para
# achar erro de ID/região/permissão sem gastar o holdout; depois o holdout_s9 inteiro, UMA vez
# (veja data/invoices/CONJUNTOS.md). Se o teste rápido falhar, corrija e rode de novo.
set -euo pipefail
cd "$(dirname "$0")/.."

export DOCAI_PROCESSOR_ID="${1:?uso: bash scripts/lab_b.sh <ID_DO_PROCESSADOR> [REGIAO]}"
export GCP_LOCATION="${2:-us}"
export GCP_PROJECT="$(gcloud config get-value project 2>/dev/null)"
echo "projeto=$GCP_PROJECT regiao=$GCP_LOCATION processador=$DOCAI_PROCESSOR_ID"

gcloud services enable documentai.googleapis.com
pip install -q google-cloud-documentai

echo "== teste rápido: 3 notas de validacao_s8 =="
python3 scripts/docai_minimo.py --pasta ../data/invoices/validacao_s8 --limite 3

read -r -p "O teste rápido funcionou? Rodar o holdout_s9 inteiro (40 notas)? [s/N] " r
[ "$r" = "s" ] || { echo "parei antes do holdout."; exit 0; }

echo "== holdout_s9 =="
python3 scripts/docai_minimo.py

python3 -m zipfile -c resultados_lab_b.zip results/
echo
echo "Resultados em sojatech_cloud/resultados_lab_b.zip (CSVs em results/)."
command -v cloudshell >/dev/null && cloudshell download resultados_lab_b.zip || true
