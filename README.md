# AgroFlow

Automação inteligente de processos agrícolas: extração de notas fiscais,
diagnóstico de doenças foliares e avaliação de confiança dos modelos.
Estudo de caso: **SojaTech** (Workshop P2).

Pipeline orientado a eventos que (1) extrai campos de notas fiscais (DANFE) e
(2) classifica doenças em folhas, gravando tudo numa tabela de resultados, e
uma avaliação que compara o **confidence** dos modelos com o **acerto medido**
contra gabarito próprio.

## Dois projetos

| | [`sojatech_local/`](sojatech_local/README.md) | [`sojatech_cloud/`](sojatech_cloud/README.md) |
|---|---|---|
| Situação | demonstração do produto final (já pronto, sem mais investimento) | **foco desta branch**: roda pelos labs do Skills Boost, só o caminho mínimo (veja abaixo) |
| Onde roda | máquina local (GPU) ou Google Colab | Google Cloud, pelos labs do Skills Boost |
| Notas fiscais | PyMuPDF + RapidOCR + regras por rótulo | Document AI Invoice Parser |
| Linha de base folhas | ResNet-50 ImageNet (top-5 rótulos) | Vision API label detection |
| Classificador folhas | ViT-B/16 ajustado (escolhido na disputa de redes) | Vertex AI AutoML |
| Evento | pasta `bucket/entrada/` + watchdog | Cloud Storage + Cloud Function |
| Resultados | SQLite `results/agroflow.db` | BigQuery (mesmo esquema) |
| Custo | zero | créditos GCP |

Os dois usam os mesmos dados e escrevem no mesmo relatório, que ficam na raiz.
O `sojatech_cloud` lê os resultados do `sojatech_local` para a comparação
Google vs. local, então rode o local primeiro.

## Guias de execução

| Guia | Para quê |
|---|---|
| **[docs/GUIA_LOCAL.md](docs/GUIA_LOCAL.md)** | rodar na máquina ou no Docker (CPU/GPU), tela web, lotes, avaliação e testes |
| **[docs/GUIA_CLOUD.md](docs/GUIA_CLOUD.md)** | rodar nos labs do Google Cloud Skills Boost (Vision API e Document AI) |

### Local (resumo)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv/bin/python -m pip install -r sojatech_local/requirements.txt
cd sojatech_local && ../.venv/bin/python scripts/app.py     # http://localhost:8000/prod
```

Com Docker: `docker compose up -d --build agroflow` (CPU) ou
`docker compose --profile gpu up -d --build agroflow-gpu` (GPU, exige o NVIDIA Container Toolkit).
Passo a passo, testes e problemas conhecidos: [docs/GUIA_LOCAL.md](docs/GUIA_LOCAL.md).

### Google Cloud (resumo)

O enunciado pede uma das opções (Vision API ou Document AI); fazemos as duas, cada uma no seu lab,
sem bucket, Cloud Function nem BigQuery.

| | Lab | Script |
|---|---|---|
| A | **GSP037** Cloud Vision API | `sojatech_cloud/scripts/lab_a.sh` |
| B | **GSP1139** Document AI (Invoice Parser) | `sojatech_cloud/scripts/lab_b.sh <ID> [REGIAO]` |

```bash
python sojatech_cloud/scripts/empacotar_lab.py      # gera sojatech_cloud/build/agroflow-lab.zip
# no Cloud Shell: Upload do zip, depois
python3 -m zipfile -e agroflow-lab.zip . && cd sojatech_cloud
bash scripts/lab_a.sh          # Vision (0 = todas as imagens)
bash scripts/lab_b.sh <ID_DO_PROCESSADOR> us
```

O `data/invoices/holdout_s9` é lacrado: avaliado uma vez, sem ajustar o extrator depois. O
cronômetro do lab não pausa. Passo a passo e problemas conhecidos:
[docs/GUIA_CLOUD.md](docs/GUIA_CLOUD.md). Para um projeto GCP próprio, sem Skills Boost (não testado, gera
custo), veja a seção 7 do mesmo guia.

## Estrutura

```
data/                compartilhado: notas fictícias + gabaritos, folhas treino/teste
report/              (fora do git) destino das tabelas e figuras geradas pelo evaluate; o paper fica no Overleaf
docs/                guias de execução (GUIA_LOCAL.md e GUIA_CLOUD.md)
sojatech_local/      pacote agroflow local, scripts, modelo, resultados, notebook do Colab
sojatech_cloud/      pacote agroflow com Document AI/Vision/Vertex/BigQuery, Cloud Function,
                     infra gcloud, notebook do Colab para o GCP
_downloads/          (não versionado) origem do PlantVillage para scripts/prepare_leaves.py
```
