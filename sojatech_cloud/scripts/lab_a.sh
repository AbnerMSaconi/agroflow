#!/usr/bin/env bash
# Lab A (GSP037): Vision API nas folhas. Roda no Cloud Shell, depois do zip descompactado.
#
#   cd sojatech_cloud && bash scripts/lab_a.sh        # 40 imagens por conjunto
#   bash scripts/lab_a.sh 0                           # todas (100 de laboratório, 127 de campo)
#
# Se der erro de API desabilitada logo após o enable, espere cerca de 1 minuto e rode de novo.
set -euo pipefail
cd "$(dirname "$0")/.."

N="${1:-40}"
LIM=()
[ "$N" != "0" ] && LIM=(--limite "$N")

gcloud services enable vision.googleapis.com
pip install -q google-cloud-vision

echo "== laboratório (data/leaves/test) =="
python3 scripts/vision_minimo.py ${LIM[@]+"${LIM[@]}"}
echo
echo "== campo (data/leaves/campo/teste) =="
python3 scripts/vision_minimo.py --pasta ../data/leaves/campo/teste ${LIM[@]+"${LIM[@]}"}

python3 -m zipfile -c resultados_lab_a.zip results/
echo
echo "Resultados em sojatech_cloud/resultados_lab_a.zip (CSVs em results/)."
command -v cloudshell >/dev/null && cloudshell download resultados_lab_a.zip || true
