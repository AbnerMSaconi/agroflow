#!/usr/bin/env bash
# Publica a Cloud Function (2ª geração) com trigger de finalização de objeto.
set -euo pipefail

PROJECT="${PROJECT:-agroflow-p2}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-${PROJECT}-entrada}"
SA_EMAIL="pipeline-sa@$PROJECT.iam.gserviceaccount.com"
: "${DOCAI_PROCESSOR_ID:?defina DOCAI_PROCESSOR_ID}"

cd "$(dirname "$0")/.."
BUILD="$(mktemp -d)"
cp cloud_function/main.py cloud_function/requirements.txt "$BUILD/"
cp -r agroflow "$BUILD/"
find "$BUILD" -name __pycache__ -prune -exec rm -rf {} +

gcloud functions deploy agroflow-pipeline --gen2 --runtime=python312 --region="$REGION" \
  --source="$BUILD" --entry-point=on_upload --memory=1Gi --timeout=300s \
  --service-account="$SA_EMAIL" \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=$BUCKET" \
  --set-env-vars="AGROFLOW_BACKEND=gcp,GCP_PROJECT=$PROJECT,GCP_LOCATION=us,DOCAI_PROCESSOR_ID=$DOCAI_PROCESSOR_ID,VERTEX_REGION=$REGION,VERTEX_ENDPOINT_ID=${VERTEX_ENDPOINT_ID:-},BQ_TABLE=$PROJECT.agroflow.resultados"

echo "Teste: gcloud storage cp data/invoices/pdf/nota_001.pdf gs://$BUCKET/entrada/notas/"
