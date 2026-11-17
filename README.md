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

## Rodar nos labs do Google Cloud (branch `gcp-minimo`)

O enunciado pede **uma** destas opções, apresentando a taxa de precisão (*confidence score*):

- **A (principal):** Cloud Vision API (ou um modelo básico no Vertex AI) identificando objetos ou
  defeitos em imagens de teste.
- **B (plano B):** Document AI extraindo campos de notas fiscais em PDF.

Como a conta GCP de estudante não saiu, usamos labs do Google Skills Boost, que dão um projeto
temporário. Fazemos as duas opções, cada uma no seu lab, sem bucket, Cloud Function, BigQuery nem
pipeline por evento. Detalhes e justificativas em [`sojatech_cloud/LAB.md`](sojatech_cloud/LAB.md).

| | Lab | Script |
|---|---|---|
| A | **GSP037** Detect Labels, Faces, and Landmarks in Images with the Cloud Vision API | `sojatech_cloud/scripts/lab_a.sh` |
| B | **GSP1139** Form Parsing with Document AI (Python) | `sojatech_cloud/scripts/lab_b.sh` |

Não servem: GSP1141 (o treino do uptraining leva horas) e OCBL447 (Gemini: não usa Vision nem
Document AI e não devolve confidence). Cada lab custa 5 créditos e a página indica 10 minutos;
confira o cronômetro ao iniciar, porque o lab não pausa.

### Antes do lab (na sua máquina)

```
python sojatech_cloud/scripts/empacotar_lab.py     # gera sojatech_cloud/build/agroflow-lab.zip (~13 MB)
```

### Em cada lab (Cloud Shell)

1. Start lab e entre com as credenciais temporárias (janela anônima).
2. No Cloud Shell: menu de três pontos > **Upload** > `agroflow-lab.zip`.
3. `python3 -m zipfile -e agroflow-lab.zip . && cd sojatech_cloud`

**Lab A (Vision):** faça os passos do próprio lab (chave de API, bucket, requisições) e rode

```
bash scripts/lab_a.sh        # 40 fotos de laboratório e 40 de campo (use 0 para todas)
```

**Lab B (Document AI):** no console, Document AI > Explore processors > **Specialized > Invoice
Parser** > Create (o lab só pede o Form Parser; o nosso extrator usa o Invoice Parser). Copie o ID
do processador e a região, e rode

```
bash scripts/lab_b.sh <ID_DO_PROCESSADOR> [REGIAO]     # região padrão: us
```

O `lab_b.sh` faz um teste rápido em 3 notas da `validacao_s8`, pergunta se pode seguir e roda o
`holdout_s9` inteiro, **uma vez**. Os dois scripts empacotam `results/` em `resultados_lab_*.zip` e
baixam o zip. Guarde também prints do console, que o relatório precisa.

### Regras e limites

- `data/invoices/holdout_s9` é lacrado: avaliado uma vez, sem ajustar o extrator depois. O papel de
  cada conjunto está em [`data/invoices/CONJUNTOS.md`](data/invoices/CONJUNTOS.md).
- Os scripts só foram testados offline, com extratores falsos. A chamada real à Vision e ao Document
  AI nunca foi executada; o primeiro erro pode ser de permissão, API ou região.
- Não verifiquei se o projeto do lab permite criar o Invoice Parser. Se não permitir, o lab B não
  roda como está (o Form Parser devolve pares chave/valor e precisaria de outro extrator).
- A Vision devolve rótulos genéricos (Leaf, Plant...) com score alto; na linha de base local nenhuma
  imagem teve rótulo de doença. É um resultado para o relatório, mas não é taxa de acerto por classe.
  Essa taxa exigiria o Vertex AI AutoML (`sojatech_cloud/infra/vertex_train.sh`, mínimo de 8 horas
  de nó), que pode não caber no lab.

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
