"""Document AI nas notas fiscais: extrai os campos e compara com o gabarito.

Sem bucket, sem Cloud Function e sem BigQuery: lê os PDFs de uma pasta, chama o
Invoice Parser e grava um CSV com campo, valor extraído, confidence e acerto.

Uso (no Cloud Shell do lab, com o processador criado):
  export GCP_PROJECT=<id do projeto do lab>
  export DOCAI_PROCESSOR_ID=<id do processador Invoice Parser>
  python scripts/docai_minimo.py                              # holdout_s9
  python scripts/docai_minimo.py --pasta ../data/invoices/validacao_s8
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config  # noqa: E402

CAMPOS = ["cnpj_emitente", "numero", "data_emissao", "valor_total"]


def avalia(pasta: Path, extrair) -> list[dict]:
    """Uma linha por nota e campo: esperado, extraído, confidence e acerto."""
    linhas = []
    with open(pasta / "gabarito.csv", encoding="utf-8", newline="") as f:
        gabarito = list(csv.DictReader(f))
    for i, g in enumerate(gabarito, 1):
        try:
            campos, _ = extrair(pasta / "pdf" / g["arquivo"])
            erro = ""
        except Exception as e:  # uma nota com problema não derruba o lote
            campos, erro = {}, f"{type(e).__name__}: {e}"
        for campo in CAMPOS:
            valor, conf = campos.get(campo, (None, 0.0))
            linhas.append(dict(
                arquivo=g["arquivo"], layout=g["layout"], escaneada=g["escaneada"], campo=campo,
                esperado=g[campo], extraido=valor or "", confidence=conf,
                acertou=int(valor == g[campo]), erro=erro,
            ))
        print(f"{i}/{len(gabarito)} {g['arquivo']}", flush=True)
    return linhas


def resumo(linhas: list[dict]) -> str:
    out = []
    for campo in CAMPOS:
        ls = [l for l in linhas if l["campo"] == campo]
        certos = [l["confidence"] for l in ls if l["acertou"]]
        errados = [l["confidence"] for l in ls if not l["acertou"]]
        media = lambda v: f"{sum(v) / len(v):.3f}" if v else "-"
        out.append(f"{campo:15} acerto {len(certos)}/{len(ls)}  "
                   f"confidence médio: certos {media(certos)} | errados {media(errados)}")
    notas = {l["arquivo"] for l in linhas}
    inteiras = sum(all(l["acertou"] for l in linhas if l["arquivo"] == n) for n in notas)
    out.append(f"nota inteira    {inteiras}/{len(notas)}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", type=Path, default=config.INVOICES_DIR / "holdout_s9",
                    help="pasta com pdf/ e gabarito.csv (padrão: holdout_s9)")
    ap.add_argument("--saida", type=Path, help="CSV de saída (padrão: results/docai_<pasta>.csv)")
    args = ap.parse_args()

    if not (config.GCP_PROJECT and config.DOCAI_PROCESSOR_ID):
        sys.exit("defina GCP_PROJECT e DOCAI_PROCESSOR_ID (veja o topo deste arquivo)")
    from agroflow.invoices.docai_extractor import extract

    linhas = avalia(args.pasta, extract)
    saida = args.saida or config.RESULTS / f"docai_{args.pasta.name}.csv"
    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    print(f"\n{resumo(linhas)}\n\nCSV em {saida}")


if __name__ == "__main__":
    main()
