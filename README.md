# AgroFlow

Automação inteligente de processos agrícolas em nuvem: extração de notas
fiscais, diagnóstico de doenças foliares e avaliação de confiança dos modelos.
Estudo de caso: **SojaTech** (Workshop P2).

Pipeline orientado a eventos que (1) extrai campos de notas fiscais (DANFE) e
(2) classifica doenças em folhas, gravando tudo numa tabela de resultados, e
uma avaliação que compara o **confidence** dos modelos com o **acerto medido**
contra gabarito próprio.

O mesmo código roda em dois backends, escolhidos por `SOJATECH_BACKEND`:

| Papel | `gcp` | `local` (padrão, custo zero) |
|---|---|---|
| Entrada + evento | Cloud Storage + Eventarc | `bucket/entrada/` + watchdog |
| Roteamento | Cloud Function 2ª ger. (`cloud_function/main.py`) | `scripts/watch_bucket.py` |
| Notas fiscais | Document AI Invoice Parser | PyMuPDF + RapidOCR + regras por rótulo |
| Linha de base folhas | Vision API label detection | ResNet-50 ImageNet (top-5 rótulos) |
| Classificador folhas | Vertex AI AutoML | EfficientNet-B0 fine-tuned (GPU) |
| Resultados | BigQuery | SQLite `results/sojatech.db` (mesmo esquema) |

```
bucket/entrada/{notas,imagens}  ──►  pipeline.process_file()  ──►  tabela resultados
        │ extensão .pdf → invoices.extract()                          │
        │ extensão .jpg/.png → leaves.baseline() + leaves.classify()  ▼
        └─► processados/ ou rejeitados/ (+ log)               scripts/evaluate.py
```

## Rodando localmente (sem GCP)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv/Scripts/python -m pip install -r requirements.txt

# dados (já versionados; só rode para regenerar)
python scripts/gen_danfes.py --n 40          # DANFEs fictícias + data/invoices/gabarito.csv
python scripts/prepare_leaves.py             # precisa do PlantVillage em _downloads/ (ver docstring)

python scripts/train_leaf_classifier.py      # ~15 s na GPU -> models/leaf_classifier.pt
python scripts/run_batch.py notas            # extrai as 40 notas
python scripts/run_batch.py folhas           # linha de base + classificador no teste fixo
python scripts/evaluate.py                   # métricas, gráficos e tabelas LaTeX
```

Saídas: `results/resumo.md`, `results/metricas.json`, `results/figures/`,
`report/tabelas/*.tex`.

**Demo do pipeline:** `python scripts/watch_bucket.py` e copie PDFs/JPGs para
`bucket/entrada/notas` ou `bucket/entrada/imagens`. Cada arquivo aparece no
log com os campos e o confidence e é movido para `bucket/processados/`;
arquivos inválidos vão para `bucket/rejeitados/` com o motivo em
`bucket/rejeitados.log`. Use `--once` para processar o que já está lá e sair.

## Rodando no GCP

1. `infra/setup_gcp.sh` — projeto, **orçamento com alerta**, APIs, service account, bucket, tabela BigQuery
2. Console → Document AI → criar processador *Invoice Parser* → `export DOCAI_PROCESSOR_ID=...`
3. `infra/vertex_train.sh upload | train | deploy` — e **`undeploy` logo após testes/demo**
4. `infra/deploy_function.sh` — publica a Cloud Function com trigger no bucket
5. Rodar os lotes contra as APIs e avaliar a partir do BigQuery:
   ```bash
   pip install -r requirements-gcp.txt
   export SOJATECH_BACKEND=gcp GCP_PROJECT=... DOCAI_PROCESSOR_ID=... VERTEX_ENDPOINT_ID=... BQ_TABLE=projeto.sojatech.resultados
   python scripts/run_batch.py notas && python scripts/run_batch.py folhas && python scripts/evaluate.py
   ```

## Estrutura

```
sojatech/            pacote compartilhado (local e Cloud Function)
  config.py          backend, caminhos, variáveis GCP
  storage.py         tabela resultados: SQLite ou BigQuery
  pipeline.py        roteamento por extensão + rejeitados
  invoices/          local_extractor.py | docai_extractor.py
  leaves/            local_models.py    | gcp_models.py
scripts/             gerar dados, treinar, lote, watcher, avaliação
cloud_function/      entry point da Cloud Function
infra/               scripts gcloud (setup, deploy, Vertex)
data/                notas fictícias + gabarito, folhas treino/teste
report/              relatório LaTeX (secoes/ para dar \input no template)
docs/                STATUS.md (andamento do plano) e prints/
```
