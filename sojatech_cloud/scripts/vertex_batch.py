"""Classifica o conjunto de teste das folhas com o modelo AutoML via batch prediction.

Sem endpoint: o job sobe, classifica as imagens de teste e desliga sozinho,
então nada fica cobrando por hora. As previsões vão para a tabela resultados
como tipo folha_classificador (backend gcp), com o mesmo nome "<classe>/<arquivo>"
que o run_batch usa, para a avaliação achar o gabarito.

Uso (GCP_PROJECT, VERTEX_REGION e BQ_TABLE definidos):
  python scripts/vertex_batch.py --model-id 1234567890 --bucket meu-bucket
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config, storage  # noqa: E402
from agroflow.storage import Row  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default=os.getenv("MODEL_ID"))
    ap.add_argument("--bucket", default=os.getenv("BUCKET"))
    args = ap.parse_args()
    if not (args.model_id and args.bucket):
        ap.error("informe --model-id e --bucket (ou MODEL_ID e BUCKET no ambiente)")

    from google.cloud import aiplatform
    from google.cloud import storage as gcs

    aiplatform.init(project=config.GCP_PROJECT, location=config.VERTEX_REGION)
    cliente = gcs.Client(project=config.GCP_PROJECT)
    bucket = cliente.bucket(args.bucket)

    # 1. sobe o teste fixo e monta a entrada JSONL
    nomes, linhas = {}, []
    imagens = sorted((config.LEAVES_DIR / "test").glob("*/*"))
    for p in imagens:
        nome = f"{p.parent.name}/{p.name}"
        caminho = f"folhas/teste/{nome}"
        bucket.blob(caminho).upload_from_filename(str(p))
        uri = f"gs://{args.bucket}/{caminho}"
        nomes[uri] = nome
        linhas.append(json.dumps({"content": uri, "mimeType": "image/jpeg"}))
    entrada = "folhas/batch/entrada.jsonl"
    bucket.blob(entrada).upload_from_string("\n".join(linhas))
    print(f"{len(imagens)} imagens em gs://{args.bucket}/folhas/teste/")

    # 2. batch prediction (bloqueia até terminar; costuma levar de 20 a 40 min)
    t = time.perf_counter()
    job = aiplatform.Model(args.model_id).batch_predict(
        job_display_name="folhas-teste",
        gcs_source=f"gs://{args.bucket}/{entrada}",
        gcs_destination_prefix=f"gs://{args.bucket}/folhas/batch/saida",
        instances_format="jsonl", predictions_format="jsonl",
        model_parameters={"confidenceThreshold": 0.0, "maxPredictions": 10},
        sync=True,
    )
    # inclui a subida das máquinas do job: é o tempo por imagem de um lote, não de uma chamada
    ms = (time.perf_counter() - t) * 1000 / len(imagens)

    # 3. lê as previsões e grava
    saida = job.output_info.gcs_output_directory.removeprefix("gs://")
    bkt, _, prefixo = saida.partition("/")
    rows = []
    for blob in cliente.list_blobs(bkt, prefix=prefixo):
        if not blob.name.rsplit("/", 1)[-1].startswith("predictions"):
            continue
        for linha in blob.download_as_text().splitlines():
            r = json.loads(linha)
            pred = r["prediction"]
            scores = dict(zip(pred["displayNames"], pred["confidences"]))
            classe = max(scores, key=scores.get)
            rows.append(Row(nomes[r["instance"]["content"]], "folha_classificador", "classe",
                            classe, round(scores[classe], 4), backend="gcp", duracao_ms=ms))
    storage.save(rows)
    print(f"{len(rows)} previsões gravadas em {config.BQ_TABLE}")
    if len(rows) != len(imagens):
        print(f"ATENÇÃO: {len(imagens) - len(rows)} imagens sem previsão; veja os erros do job no console")


if __name__ == "__main__":
    main()
