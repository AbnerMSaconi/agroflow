#!/usr/bin/env bash
# Vertex AI AutoML: sobe as imagens, cria o dataset e treina com o menor orçamento.
# É o único passo com custo relevante. Acompanhe o Billing durante o treino.
#
#   ./infra/vertex_train.sh upload     # imagens + CSV no bucket, cria dataset
#   ./infra/vertex_train.sh train      # treino AutoML (8 horas de nó = mínimo)
#   ./infra/vertex_train.sh batch      # classifica o teste por batch prediction (sem endpoint)
#   ./infra/vertex_train.sh deploy     # implanta o modelo num endpoint (COBRA POR HORA)
#   ./infra/vertex_train.sh undeploy   # remove a implantação: rode logo após testes/demo
set -euo pipefail

PROJECT="${PROJECT:-agroflow-p2}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-${PROJECT}-entrada}"
cd "$(dirname "$0")/.."
if [ -z "${PY:-}" ]; then
  if [ -x ../.venv/Scripts/python.exe ]; then PY=../.venv/Scripts/python.exe; else PY=python3; fi
fi

case "${1:-}" in
  upload)
    # CSV de importação a partir das imagens já separadas em ../data/leaves/train
    $PY - <<EOF
import csv, pathlib
imgs = sorted(pathlib.Path("../data/leaves/train").glob("*/*.jpg"))
with open("vertex_import.csv", "w", newline="") as f:
    csv.writer(f).writerows((f"gs://$BUCKET/folhas/treino/{p.parent.name}/{p.name}", p.parent.name) for p in imgs)
print(len(imgs), "imagens no CSV")
EOF
    gcloud storage cp -r ../data/leaves/train/* "gs://$BUCKET/folhas/treino/"
    gcloud storage cp vertex_import.csv "gs://$BUCKET/folhas/vertex_import.csv"
    $PY - <<EOF
from google.cloud import aiplatform
aiplatform.init(project="$PROJECT", location="$REGION")
ds = aiplatform.ImageDataset.create(display_name="folhas-milho",
    gcs_source="gs://$BUCKET/folhas/vertex_import.csv",
    import_schema_uri=aiplatform.schema.dataset.ioformat.image.single_label_classification)
print("DATASET_ID", ds.name)
EOF
    ;;
  train)
    : "${DATASET_ID:?defina DATASET_ID}"
    $PY - <<EOF
from google.cloud import aiplatform
aiplatform.init(project="$PROJECT", location="$REGION")
job = aiplatform.AutoMLImageTrainingJob(display_name="folhas-automl",
    prediction_type="classification", model_type="CLOUD")
model = job.run(dataset=aiplatform.ImageDataset("$DATASET_ID"), budget_milli_node_hours=8000,
    training_fraction_split=0.8, validation_fraction_split=0.1, test_fraction_split=0.1,
    model_display_name="folhas-milho")
print("MODEL_ID", model.name)
EOF
    ;;
  batch)
    : "${MODEL_ID:?defina MODEL_ID}"
    GCP_PROJECT="$PROJECT" VERTEX_REGION="$REGION" BQ_TABLE="${BQ_TABLE:-$PROJECT.agroflow.resultados}" $PY scripts/vertex_batch.py --model-id "$MODEL_ID" --bucket "$BUCKET"
    ;;
  deploy)
    : "${MODEL_ID:?defina MODEL_ID}"
    $PY - <<EOF
from google.cloud import aiplatform
aiplatform.init(project="$PROJECT", location="$REGION")
ep = aiplatform.Model("$MODEL_ID").deploy(min_replica_count=1, max_replica_count=1)
print("VERTEX_ENDPOINT_ID", ep.name, "-- lembre de rodar 'undeploy' depois!")
EOF
    ;;
  undeploy)
    : "${VERTEX_ENDPOINT_ID:?defina VERTEX_ENDPOINT_ID}"
    $PY - <<EOF
from google.cloud import aiplatform
aiplatform.init(project="$PROJECT", location="$REGION")
aiplatform.Endpoint("$VERTEX_ENDPOINT_ID").undeploy_all()
print("implantação removida")
EOF
    ;;
  *) sed -n '2,10p' "$0"; exit 1 ;;
esac
