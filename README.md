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
| Situação | **ativo**: é o que roda o trabalho | **arquivado**: a conta GCP não ficou disponível |
| Onde roda | máquina local (GPU) ou Google Colab | Google Cloud, pelo Colab |
| Notas fiscais | PyMuPDF + RapidOCR + regras por rótulo | Document AI Invoice Parser |
| Linha de base folhas | ResNet-50 ImageNet (top-5 rótulos) | Vision API label detection |
| Classificador folhas | EfficientNet-B0 fine-tuned | Vertex AI AutoML |
| Evento | pasta `bucket/entrada/` + watchdog | Cloud Storage + Cloud Function |
| Resultados | SQLite `results/agroflow.db` | BigQuery (mesmo esquema) |
| Custo | zero | créditos GCP |

Os dois usam os mesmos dados e escrevem no mesmo relatório, que ficam na raiz.
O `sojatech_cloud` lê os resultados do `sojatech_local` para a comparação
Google vs. local, então rode o local primeiro.

**Começo rápido:** abra [`sojatech_local/notebooks/agroflow_colab.ipynb`](sojatech_local/notebooks/agroflow_colab.ipynb)
no Colab, ou siga o [README do sojatech_local](sojatech_local/README.md) para rodar na máquina.

## Estrutura

```
data/                compartilhado: notas fictícias + gabaritos, folhas treino/teste
report/              relatório LaTeX (secoes/, tabelas/ e figuras/ geradas pelo evaluate)
docs/                STATUS.md (andamento do plano)
sojatech_local/      pacote agroflow local, scripts, modelo, resultados, notebook do Colab
sojatech_cloud/      pacote agroflow com Document AI/Vision/Vertex/BigQuery, Cloud Function,
                     infra gcloud, notebook do Colab para o GCP
_downloads/          (não versionado) origem do PlantVillage para scripts/prepare_leaves.py
```
