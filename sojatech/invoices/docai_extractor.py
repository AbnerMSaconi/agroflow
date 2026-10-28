"""Extração com Document AI (Invoice Parser ou Custom Extractor).

Mapeia as entidades do Invoice Parser para os campos do gabarito. O parser é
treinado em faturas estrangeiras, então espera-se que ele confunda CNPJ do
emitente com o do destinatário e a data de emissão com a de saída: isso é
achado para o relatório, não bug.
"""
import re

from .. import config

# entidade do Invoice Parser -> campo do gabarito
ENTIDADES = {
    "supplier_tax_id": "cnpj_emitente",
    "invoice_id": "numero",
    "invoice_date": "data_emissao",
    "total_amount": "valor_total",
}


def _normaliza(campo, ent):
    nv = ent.normalized_value
    texto = ent.mention_text
    if campo == "cnpj_emitente":
        d = re.sub(r"\D", "", texto)
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else texto
    if campo == "numero":
        d = re.sub(r"\D", "", texto)
        return str(int(d)) if d else texto
    if campo == "data_emissao" and nv and nv.date_value.year:
        dv = nv.date_value
        return f"{dv.year:04d}-{dv.month:02d}-{dv.day:02d}"
    if campo == "valor_total":
        if nv and nv.money_value.units:
            m = nv.money_value
            return f"{m.units + m.nanos / 1e9:.2f}"
        s = re.sub(r"[^\d,.]", "", texto)
        return f"{float(s.replace('.', '').replace(',', '.')):.2f}" if s else texto
    return texto


def extract(path) -> tuple[dict, str]:
    from google.api_core.client_options import ClientOptions
    from google.cloud import documentai

    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=f"{config.GCP_LOCATION}-documentai.googleapis.com")
    )
    name = client.processor_path(config.GCP_PROJECT, config.GCP_LOCATION, config.DOCAI_PROCESSOR_ID)
    with open(path, "rb") as f:
        raw = documentai.RawDocument(content=f.read(), mime_type="application/pdf")
    doc = client.process_document(request=documentai.ProcessRequest(name=name, raw_document=raw)).document

    out = {}
    for ent in doc.entities:
        campo = ENTIDADES.get(ent.type_)
        # fica com a entidade de maior confidence quando o parser devolve várias
        if campo and (campo not in out or ent.confidence > out[campo][1]):
            out[campo] = (_normaliza(campo, ent), round(ent.confidence, 3))
    return out, "docai"
