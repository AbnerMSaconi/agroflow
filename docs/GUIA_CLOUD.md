# Guia completo: rodar o AgroFlow no Google Cloud (labs Skills Boost)

Como não há conta GCP própria, usamos dois labs do Google Cloud Skills Boost, que dão um projeto
temporário. Rodamos só o caminho mínimo: sem bucket, Cloud Function, BigQuery nem pipeline por
evento. Para rodar localmente, veja [GUIA_LOCAL.md](GUIA_LOCAL.md).

| | Lab | Serviço | Script | Créditos |
|---|---|---|---|---|
| A | **GSP037** Detect Labels, Faces, and Landmarks in Images with the Cloud Vision API | Vision API (`LABEL_DETECTION`) | `lab_a.sh` | 5 |
| B | **GSP1139** Form Parsing with Document AI (Python) | Document AI **Invoice Parser** | `lab_b.sh` | 1 nas execuções feitas (a página indica 5) |

Não servem: GSP1141 (uptraining leva horas) e OCBL447 (Gemini: sem Vision nem Document AI, sem
confidence). O cronômetro do lab **não pausa**: confira ao iniciar. O treino no Vertex AI AutoML
(`sojatech_cloud/infra/vertex_train.sh`) exige ao menos 8 horas de nó e não cabe nos labs.

## 1. Antes do lab (na sua máquina)

```bash
python sojatech_cloud/scripts/empacotar_lab.py
# gera sojatech_cloud/build/agroflow-lab.zip (~13 MB): código, notas e folhas
```

## 2. Em cada lab (Cloud Shell)

1. **Start Lab** e entre com as credenciais temporárias em **janela anônima**.
2. Abra o Cloud Shell. Menu de três pontos → **Upload** → `agroflow-lab.zip`.
3. Descompacte e entre na pasta:
   ```bash
   python3 -m zipfile -e agroflow-lab.zip . && cd sojatech_cloud
   ```
   (Clonar o repositório privado também funciona, mas autenticar no GitHub gasta tempo do lab.)

## 3. Lab A: Vision API nas folhas (GSP037)

1. Faça os passos do próprio lab (chave de API, bucket, requisições de exemplo). Tire prints do console.
2. Rode:
   ```bash
   bash scripts/lab_a.sh        # 40 imagens de laboratório e 40 de campo
   bash scripts/lab_a.sh 0      # todas: 100 de laboratório e 127 de campo (227 chamadas)
   ```
   O script habilita `vision.googleapis.com`, instala `google-cloud-vision`, roda os dois
   conjuntos e baixa `resultados_lab_a.zip`.
3. Guarde `results/vision_test.csv` (laboratório), `results/vision_teste.csv` (campo), o resumo
   impresso e os prints.

**Como ler:** a API devolve rótulos genéricos (*Plant pathology*, *Green*, *Plant stem*) com score
alto. Contamos em quantas imagens algum rótulo nomeia a doença/praga ou cita planta/folha, com a
mesma regra usada na ResNet-50 local. Score alto aqui não é diagnóstico.

## 4. Lab B: Document AI nas notas (GSP1139)

1. No console: **Document AI → Explore processors → Specialized → Invoice Parser → Create**.
   O lab só pede o Form Parser, mas o nosso extrator usa o Invoice Parser. Anote o **ID do
   processador** e a **região** (usamos `us`).
2. Opcional: no processador, aba de teste, envie uma nota (`nota_001.pdf`) e tire print das
   entidades e scores.
3. Rode:
   ```bash
   bash scripts/lab_b.sh <ID_DO_PROCESSADOR> [REGIAO]     # região padrão: us
   ```
   O script mapeia `supplier_tax_id`, `invoice_id`, `invoice_date` e `total_amount` para o
   gabarito, ficando com a entidade de maior confidence. Faz primeiro um teste em 3 notas de
   `validacao_s8` (acha erro de ID, região ou permissão sem gastar o holdout), pergunta se pode
   seguir e roda o `holdout_s9` (40 notas) **uma única vez**. Baixa `resultados_lab_b.zip`.

**Regra do holdout:** `data/invoices/holdout_s9` é lacrado. Avalie uma vez, sem ajustar o extrator
depois. O papel de cada conjunto está em `data/invoices/CONJUNTOS.md`.

## 5. Trazer os resultados para o relatório

1. Descompacte os zips em `sojatech_cloud/results/`.
2. Gere as tabelas do relatório:
   ```bash
   python sojatech_cloud/scripts/gera_tabelas_cloud.py
   ```
   (escreve `report/tabelas/cloud_*.tex`)
3. Coloque os prints do console em `report/figuras/cloud/`.

## 6. Problemas conhecidos

| Sintoma | Saída |
|---|---|
| Erro de API desabilitada logo após o `enable` | espere cerca de 1 minuto e rode de novo |
| Erro de permissão, ID ou região no `lab_b.sh` | aparece no teste de 3 notas; confira ID e região do processador |
| Projeto do lab não deixa criar o Invoice Parser | o Form Parser só devolve pares chave/valor e exigiria outro extrator |
| O tempo do lab acabou no meio | o lab não pausa; use a amostra (`lab_a.sh 40`) e empacote antes |

## 7. Projeto GCP próprio (sem Skills Boost)

> **Não testado.** Esta seção descreve `sojatech_cloud/infra/` e o notebook do Colab, que foram
> escritos mas **nunca executados contra o Google Cloud de verdade**. O primeiro erro provável é
> de permissão, API ou região. Gera **custo real** na conta de faturamento.

### 7.1 Pré-requisitos

- Conta com **faturamento ativo** (`gcloud billing accounts list` mostra o ID).
- `gcloud` e `bq` instalados e logados (`gcloud auth login` e `gcloud auth application-default login`).
- Python com `pip install -r sojatech_cloud/requirements.txt`.
- Rodar o lado local antes ([GUIA_LOCAL.md](GUIA_LOCAL.md), seção 2.3): a avaliação compara com
  `sojatech_local/results/agroflow.db`.

### 7.2 Atalho: notebook no Colab

`sojatech_cloud/notebooks/agroflow_cloud_colab.ipynb` já traz o `gcloud` e autentica numa célula.
Roda o lado local, cria orçamento, Document AI, Vision, treino AutoML, *batch prediction*,
comparação, Cloud Function opcional e limpeza.

### 7.3 Passo a passo manual (a partir de `sojatech_cloud/`)

```bash
# 1. Projeto, orçamento com alertas (25/50/90/100%), APIs, service account, bucket, tabela BigQuery
export BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX      # obrigatório
export PROJECT=agroflow-p2 REGION=us-central1    # valores padrão; o ID do projeto precisa ser único
export BUDGET_USD=50
bash infra/setup_gcp.sh

# 2. No console: Document AI > Explore processors > Invoice Parser > Create (região us)
export GCP_PROJECT=$PROJECT DOCAI_PROCESSOR_ID=<ID>
export BQ_TABLE=$PROJECT.agroflow.resultados

# 3. Notas e linha de base das folhas contra as APIs (grava no BigQuery)
python scripts/run_batch.py notas
python scripts/run_batch.py folhas --sem-classificador

# 4. Classificador no Vertex AI AutoML
bash infra/vertex_train.sh upload               # imprime DATASET_ID
export DATASET_ID=<ID>
bash infra/vertex_train.sh train                # imprime MODEL_ID; mínimo de 8 horas de nó
export MODEL_ID=<ID>
bash infra/vertex_train.sh batch                # classifica o teste sem endpoint

# 5. Google vs. local (gera report/tabelas/comparacao_backends.tex)
python scripts/evaluate.py

# 6. Opcional: Cloud Function com trigger no bucket
bash infra/deploy_function.sh                   # exige DOCAI_PROCESSOR_ID
gcloud storage cp ../data/invoices/pdf/nota_001.pdf gs://$PROJECT-entrada/entrada/notas/
```

### 7.4 Custos e limpeza

- `setup_gcp.sh` cria o orçamento **antes** de qualquer outro recurso; confirme os alertas no console.
- O treino AutoML é o único passo caro. O `batch` não deixa endpoint ligado.
- `vertex_train.sh deploy` abre um endpoint que **cobra por hora**; ao terminar a demo, rode
  `VERTEX_ENDPOINT_ID=<ID> bash infra/vertex_train.sh undeploy`.
- Para encerrar tudo: `gcloud projects delete $PROJECT` apaga o projeto e seus recursos.

## 8. Arquitetura de referência (não executada nos labs)

Cloud Storage → evento → Cloud Function → Document AI (PDF) ou Vision/Vertex AI (imagem) →
BigQuery, com valor extraído e confidence. O código está em `sojatech_cloud/cloud_function/` e
`sojatech_cloud/infra/`, e fica arquivado. O custo dominante em produção seria um endpoint do
Vertex AI ligado 24/7; prefira *batch prediction* ou endpoint sob demanda.
