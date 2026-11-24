# Guia completo: rodar o AgroFlow localmente

Cobre a aplicação web (telas `/prod` e `/press`), o pipeline em lote, a avaliação e o Docker
(CPU e GPU). Para o Google Cloud, veja [GUIA_CLOUD.md](GUIA_CLOUD.md).

## 1. Pré-requisitos

| Item | Observação |
|---|---|
| Python 3.12 (3.13+ exige um ajuste no OCR, ver 2.1) | `python3 --version` |
| Git | para clonar; os testes `test_prepare_campo.py` também chamam `git` |
| GPU NVIDIA (opcional) | RTX 3090 nas medições do relatório; sem GPU roda na CPU, mais lento |
| Docker + Compose (só para o caminho Docker) | `docker --version` |
| NVIDIA Container Toolkit (só para Docker com GPU) | ver seção 3.3 |

## 2. Rodar direto na máquina

Todos os comandos partem da raiz do repositório, salvo indicação.

### 2.1 Ambiente

```bash
python3 -m venv .venv
# GPU (CUDA 12.8). Sem GPU, use o índice https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv/bin/python -m pip install -r sojatech_local/requirements.txt
```

No Windows troque `.venv/bin/python` por `.venv/Scripts/python`.

Em Python 3.13+ o `pip` recua em silêncio para o RapidOCR 1.2.3, que lê pior as notas escaneadas.
Instale com `pip install --ignore-requires-python rapidocr-onnxruntime==1.4.4`.

### 2.2 Subir a aplicação web

```bash
cd sojatech_local
../.venv/bin/python scripts/app.py --porta 8000
```

- Operador: <http://localhost:8000/prod> (envia lote misto de notas e fotos)
- Apresentação: <http://localhost:8000/press>
- `--sem-navegador` impede de abrir o navegador; `--host 0.0.0.0` expõe na rede local.

Fluxo da tela: enviar arquivos → cada item vira **aceito**, **conferir** (revisão humana) ou
**rejeitado**. O limiar das folhas é 0,95. O botão de exemplos carrega amostras prontas; a
fila é limpa por `POST /api/limpar`.

Verificação rápida pela API:

```bash
curl -s -X POST localhost:8000/api/enviar -F "files=@data/invoices/pdf/nota_001.pdf" \
     -F "files=@data/leaves/test/cercosporiose/cercosporiose_000.jpg"
curl -s localhost:8000/api/estado
```

### 2.3 Pipeline em lote e avaliação

```bash
cd sojatech_local
../.venv/bin/python scripts/train_leaf_classifier.py   # só se quiser retreinar (models/)
../.venv/bin/python scripts/run_batch.py notas
../.venv/bin/python scripts/run_batch.py folhas
../.venv/bin/python scripts/evaluate.py                # métricas, figuras e tabelas LaTeX
```

Saídas: `sojatech_local/results/resumo.md`, `metricas.json`, `results/figures/` e
`report/tabelas/*.tex`, `report/figuras/*.png`.

### 2.4 Pasta monitorada (evento)

```bash
../.venv/bin/python scripts/watch_bucket.py      # --once processa o que já está lá e sai
```

Copie PDFs para `bucket/entrada/notas` e JPG/PNG para `bucket/entrada/imagens`. Processados vão
para `bucket/processados/`, inválidos para `bucket/rejeitados/` (motivo em `rejeitados.log`).

### 2.5 Testes

```bash
cd sojatech_local && ../.venv/bin/python -m pytest tests -q
```

## 3. Rodar com Docker

O `docker-compose.yml` fica na raiz e monta `data/`, `report/` e `sojatech_local/{models,results,bucket}`
como volumes: o que a aplicação grava aparece no repositório.

### 3.1 CPU

```bash
docker compose up -d --build agroflow
```

### 3.2 GPU

```bash
docker compose --profile gpu up -d --build agroflow-gpu
docker exec agroflow-agroflow-gpu-1 python -c "import torch; print(torch.cuda.is_available())"   # True
```

CPU e GPU usam a mesma porta 8000: pare um antes de subir o outro (`docker compose stop agroflow`).

### 3.3 NVIDIA Container Toolkit (uma vez por máquina)

Sem ele, o erro é `could not select device driver "nvidia" with capabilities: [[gpu]]`.
O driver NVIDIA precisa estar instalado no host (`nvidia-smi` deve listar a placa).

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker        # derruba os containers em execução
```

### 3.4 Operação

```bash
docker ps                                   # STATUS deve chegar a (healthy)
docker logs -f agroflow-agroflow-gpu-1
docker compose --profile gpu down           # parar
docker compose --profile test run --rm test # pytest dentro do container
```

## 4. Problemas conhecidos

| Sintoma | Causa e saída |
|---|---|
| `could not select device driver "nvidia"` | falta o toolkit (3.3) |
| 2 testes de `test_prepare_campo.py` falham no container com `FileNotFoundError: 'git'` | a imagem não tem `git`; passam no host. Não afeta a aplicação |
| Primeira nota demora alguns segundos a mais | carga do modelo OCR; o aquecimento ocorre na subida |
| Porta 8000 ocupada | outro container ou processo; `docker ps` e `ss -ltnp \| grep 8000` |
| Folhas caem em "conferir" com confidence 0,94 | é o limiar de 0,95 funcionando, não erro |
