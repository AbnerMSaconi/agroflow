# sojatech_cloud

> **Nesta branch (`gcp-minimo`) o caminho é o mínimo, pelos labs do Skills Boost:**
> `scripts/vision_minimo.py` e `scripts/docai_minimo.py`, com o roteiro em [`LAB.md`](LAB.md) e os
> scripts `scripts/lab_a.sh` e `scripts/lab_b.sh`.
>
> O pipeline completo descrito abaixo (Cloud Function, BigQuery, Vertex, `infra/`) continua
> arquivado: a conta GCP de estudante não ficou disponível, e esse código nunca foi executado
> contra o GCP de verdade. O [`sojatech_local`](../sojatech_local/README.md) é a demonstração.

A mesma pipeline do `sojatech_local`, com os serviços do Google no lugar dos
substitutos locais:

| Papel | Serviço |
|---|---|
| Entrada + evento | Cloud Storage + Eventarc |
| Roteamento | Cloud Function 2ª geração (`cloud_function/main.py`) |
| Notas fiscais | Document AI Invoice Parser |
| Linha de base folhas | Vision API label detection |
| Classificador folhas | Vertex AI AutoML (avaliado por *batch prediction*, sem endpoint) |
| Resultados | BigQuery (mesmo esquema do SQLite local) |

Lê os dados de `../data/`. A avaliação (`scripts/evaluate.py`) junta o BigQuery
com `../sojatech_local/results/agroflow.db` e gera
`../report/tabelas/comparacao_backends.tex` (Google vs. local): rode o
`sojatech_local` antes.

## Pelo Colab (caminho recomendado)

[`notebooks/agroflow_cloud_colab.ipynb`](notebooks/agroflow_cloud_colab.ipynb):
o Colab já traz o `gcloud` e autentica com a conta Google numa célula. Roda o lado
local para a comparação (célula A) e depois setup com orçamento, Document AI,
Vision API, treino AutoML, *batch prediction*, comparação, Cloud Function
opcional e limpeza.

## Passo a passo manual (máquina com `gcloud`, a partir desta pasta)

1. `infra/setup_gcp.sh`: projeto, **orçamento com alerta**, APIs, service account, bucket, tabela BigQuery
2. Console → Document AI → criar processador *Invoice Parser* → `export DOCAI_PROCESSOR_ID=...`
3. Notas e linha de base das folhas contra as APIs:
   ```bash
   pip install -r requirements.txt
   export GCP_PROJECT=... DOCAI_PROCESSOR_ID=... BQ_TABLE=projeto.agroflow.resultados
   python scripts/run_batch.py notas && python scripts/run_batch.py folhas --sem-classificador
   ```
4. `infra/vertex_train.sh upload | train | batch`: o `batch` classifica o teste
   sem endpoint (nada fica cobrando por hora). `deploy`/`undeploy` só para demo ao vivo.
5. `python scripts/evaluate.py`: Google vs. local
6. `infra/deploy_function.sh`: publica a Cloud Function com trigger no bucket

## Estrutura

```
agroflow/            config.py (variáveis GCP), storage.py (BigQuery), pipeline.py
  invoices/          docai_extractor.py
  leaves/            gcp_models.py (Vision API + endpoint do Vertex)
scripts/             run_batch.py, vertex_batch.py, evaluate.py (com a comparação)
cloud_function/      entry point da Cloud Function
infra/               setup_gcp.sh, vertex_train.sh, deploy_function.sh
notebooks/           agroflow_cloud_colab.ipynb
vertex_import.csv    CSV de importação do dataset (regerado por vertex_train.sh upload)
```
