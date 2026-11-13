# sojatech_local

O AgroFlow inteiro sem serviço pago: roda na máquina (GPU opcional) ou no
Google Colab. Lê os dados de `../data/` e escreve as tabelas e figuras do
relatório em `../report/`.

| Papel | Implementação |
|---|---|
| Entrada + evento | `bucket/entrada/{notas,imagens}` + watchdog (`scripts/watch_bucket.py`) |
| Notas fiscais | PyMuPDF (texto) ou RapidOCR (escaneada) + regras por rótulo |
| Linha de base folhas | ResNet-50 ImageNet, top-5 rótulos genéricos |
| Classificador folhas | EfficientNet-B0 fine-tuned (`scripts/train_leaf_classifier.py`) |
| Resultados | SQLite `results/agroflow.db` |

```
bucket/entrada/{notas,imagens}  ──►  pipeline.process_file()  ──►  tabela resultados
        │ extensão .pdf → invoices.extract()                          │
        │ extensão .jpg/.png → leaves.baseline() + leaves.classify()  ▼
        └─► processados/ ou rejeitados/ (+ log)               scripts/evaluate.py
```

## No Google Colab

Abra [`notebooks/agroflow_colab.ipynb`](notebooks/agroflow_colab.ipynb), escolha
um ambiente com GPU T4 e rode as células em ordem: treino, notas, folhas,
avaliação, demo do pipeline e download dos resultados. O repositório é privado:
salve um token de leitura do GitHub nos Secrets do Colab como `GITHUB_TOKEN`.

## Na máquina

```bash
# na raiz do repositório
python -m venv .venv
.venv/Scripts/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv/Scripts/python -m pip install -r sojatech_local/requirements.txt

cd sojatech_local    # todos os comandos abaixo rodam daqui, com o venv ativo

# dados (já versionados em ../data; só rode para regenerar)
python scripts/gen_danfes.py --n 40                    # DANFEs fictícias + gabarito
python scripts/gen_danfes.py --n 40 --conjunto teste   # teste separado: outro seed + layout novo
python scripts/prepare_leaves.py                       # precisa do PlantVillage em ../_downloads (ver docstring)

python scripts/train_leaf_classifier.py   # ~15 s na GPU -> models/leaf_classifier.pt
python scripts/run_batch.py notas         # notas de desenvolvimento e de teste
python scripts/run_batch.py folhas        # linha de base + classificador no teste fixo
python scripts/evaluate.py                # métricas, gráficos e tabelas LaTeX
```

Saídas: `results/resumo.md`, `results/metricas.json`, `results/figures/`,
`../report/tabelas/*.tex`, `../report/figuras/*.png`.

**Demo do pipeline:** `python scripts/watch_bucket.py` e copie PDFs/JPGs para
`bucket/entrada/notas` ou `bucket/entrada/imagens`. Cada arquivo aparece no
log com os campos e o confidence e é movido para `bucket/processados/`;
arquivos inválidos vão para `bucket/rejeitados/` com o motivo em
`bucket/rejeitados.log`. Use `--once` para processar o que já está lá e sair.

## Estrutura

```
agroflow/            config.py, storage.py (SQLite), pipeline.py
  invoices/          local_extractor.py
  leaves/            local_models.py
scripts/             gerar dados, treinar, lote, watcher, avaliação
notebooks/           agroflow_colab.ipynb
models/              leaf_classifier.json (versionado) e .pt (gerado)
results/             métricas, resumo, CSVs de comparação, figuras
```
