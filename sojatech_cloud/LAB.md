# Roteiro mínimo no lab (Document AI nas notas fiscais)

O enunciado pede extrair campos de notas fiscais em PDF com o Document AI e apresentar o
*confidence score*. É só isso: sem bucket, Cloud Function, BigQuery nem Vertex.
(`infra/` e o resto deste projeto ficam arquivados.)

## No lab (Cloud Shell, projeto já criado pelo lab)

1. Pegar o código (repositório privado: use um token só de leitura e revogue depois):
   ```
   gh repo clone AbnerMSaconi/agroflow && cd agroflow && git switch gcp-minimo
   ```
2. Habilitar a API e instalar a biblioteca:
   ```
   gcloud services enable documentai.googleapis.com
   pip install google-cloud-documentai
   ```
3. No console: **Document AI > Processor gallery > Invoice Parser > Create**, região `us`.
   Copiar o **ID** do processador (na página dele).
4. Rodar no holdout (uma única vez; veja `data/invoices/CONJUNTOS.md`):
   ```
   export GCP_PROJECT=$(gcloud config get-value project)
   export DOCAI_PROCESSOR_ID=<id do passo 3>
   cd sojatech_cloud
   python scripts/docai_minimo.py
   ```
5. Guardar: o CSV em `sojatech_cloud/results/docai_holdout_s9.csv`, a tabela que o script
   imprime e prints do console (processador criado, API habilitada, execução).

## O que esperar

O Invoice Parser é treinado em faturas estrangeiras. Pode confundir o CNPJ do emitente com o do
destinatário e a data de emissão com a de saída. Isso é resultado para o relatório, não bug.

Para comparar com o extrator local, use o mesmo `holdout_s9`.
