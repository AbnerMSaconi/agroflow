FROM python:3.12-slim

ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências de sistema necessárias para OpenCV / RapidOCR e PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Camada de dependências antes do código-fonte para aproveitar o cache do Docker
COPY sojatech_local/requirements.txt sojatech_local/requirements-dev.txt ./sojatech_local/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url "${TORCH_INDEX_URL}" && \
    pip install --no-cache-dir -r sojatech_local/requirements.txt -r sojatech_local/requirements-dev.txt

# Código do projeto local
COPY sojatech_local/agroflow ./sojatech_local/agroflow
COPY sojatech_local/scripts ./sojatech_local/scripts
COPY sojatech_local/tests ./sojatech_local/tests

# Pastas esperadas pelo pipeline e pelo servidor (montadas via volumes no Compose)
RUN mkdir -p /app/data \
    /app/report \
    /app/sojatech_local/models \
    /app/sojatech_local/results \
    /app/sojatech_local/bucket/entrada/notas \
    /app/sojatech_local/bucket/entrada/imagens \
    /app/sojatech_local/bucket/processados \
    /app/sojatech_local/bucket/rejeitados

WORKDIR /app/sojatech_local

EXPOSE 8000

CMD ["python", "scripts/app.py", "--host", "0.0.0.0", "--porta", "8000", "--sem-navegador"]
