#!/usr/bin/env bash
# Fase 0 no GCP. Só é necessário para rodar com AGROFLOW_BACKEND=gcp;
# o backend local não precisa de nada disto.
#
# Pré-requisitos: gcloud instalado e logado (gcloud auth login), conta de
# faturamento com créditos. Rode uma etapa por vez e confira no console.
set -euo pipefail

PROJECT="${PROJECT:-agroflow-p2}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-${PROJECT}-entrada}"
BILLING_ACCOUNT="${BILLING_ACCOUNT:?defina BILLING_ACCOUNT (gcloud billing accounts list)}"
BUDGET_USD="${BUDGET_USD:-50}"
SA="pipeline-sa"

# 1. projeto + faturamento
gcloud projects create "$PROJECT" --name="AgroFlow P2" || true
gcloud config set project "$PROJECT"
gcloud billing projects link "$PROJECT" --billing-account="$BILLING_ACCOUNT"

# 2. orçamento com alertas ANTES de qualquer outra coisa
gcloud services enable billingbudgets.googleapis.com
gcloud billing budgets create --billing-account="$BILLING_ACCOUNT" \
  --display-name="agroflow-p2" --budget-amount="${BUDGET_USD}USD" \
  --filter-projects="projects/$PROJECT" \
  --threshold-rule=percent=0.25 --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9 --threshold-rule=percent=1.0

# 3. APIs
gcloud services enable documentai.googleapis.com vision.googleapis.com aiplatform.googleapis.com \
  cloudfunctions.googleapis.com run.googleapis.com cloudbuild.googleapis.com eventarc.googleapis.com \
  storage.googleapis.com pubsub.googleapis.com bigquery.googleapis.com language.googleapis.com

# 4. service account com papéis mínimos
gcloud iam service-accounts create "$SA" --display-name="Pipeline AgroFlow" || true
SA_EMAIL="$SA@$PROJECT.iam.gserviceaccount.com"
for role in roles/documentai.apiUser roles/aiplatform.user roles/bigquery.dataEditor \
            roles/bigquery.jobUser roles/eventarc.eventReceiver roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA_EMAIL" --role="$role" --condition=None
done

# 5. bucket de entrada (a SA lê e move arquivos só neste bucket)
gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access || true
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$SA_EMAIL" \
  --role=roles/storage.objectAdmin
# o agente do GCS precisa publicar no Pub/Sub para o trigger do Eventarc
GCS_SA="$(gcloud storage service-agent --project="$PROJECT")"
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$GCS_SA" \
  --role=roles/pubsub.publisher --condition=None

# 6. BigQuery: mesmo esquema da tabela SQLite local (agroflow/storage.py)
bq --location=US mk -d "$PROJECT:agroflow" || true
bq mk -t "$PROJECT:agroflow.resultados" \
  arquivo:STRING,tipo:STRING,campo:STRING,valor:STRING,confidence:FLOAT,backend:STRING,duracao_ms:FLOAT,processado_em:TIMESTAMP || true

echo
echo "Feito. Próximos passos:"
echo " - Document AI: crie um processador Invoice Parser no console (região us) e exporte DOCAI_PROCESSOR_ID"
echo " - Vertex AI: infra/vertex_train.sh"
echo " - Cloud Function: infra/deploy_function.sh"
