"""Cloud Function (2ª geração) disparada por google.cloud.storage.object.v1.finalized.

Baixa o arquivo para /tmp, chama sojatech.pipeline.process_file (o mesmo código
do pipeline local, com SOJATECH_BACKEND=gcp) e move arquivos inválidos para
rejeitados/. O deploy copia o pacote sojatech/ para cá: veja infra/deploy_function.sh.
"""
import logging
import os
import tempfile

import functions_framework
from google.cloud import storage

os.environ.setdefault("SOJATECH_BACKEND", "gcp")
from sojatech.pipeline import ArquivoInvalido, process_file  # noqa: E402

PREFIXO_ENTRADA = "entrada/"


@functions_framework.cloud_event
def on_upload(event):
    data = event.data
    bucket_name, nome = data["bucket"], data["name"]
    if not nome.startswith(PREFIXO_ENTRADA) or nome.endswith("/"):
        return  # ignora rejeitados/, processados/ e "pastas"

    bucket = storage.Client().bucket(bucket_name)
    blob = bucket.blob(nome)
    base = os.path.basename(nome)
    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(tmp, base)
        blob.download_to_filename(local)
        try:
            rows = process_file(local, nome=base)
            logging.info("%s processado: %d linhas", nome, len(rows))
            destino = "processados/" + nome[len(PREFIXO_ENTRADA):]
        except ArquivoInvalido as e:
            logging.warning("REJEITADO %s: %s", nome, e)
            destino = "rejeitados/" + nome[len(PREFIXO_ENTRADA):]
    bucket.copy_blob(blob, bucket, destino)
    blob.delete()
