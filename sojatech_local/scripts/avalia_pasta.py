"""Avalia o extrator local numa pasta de notas e grava o CSV no mesmo formato do Document AI.

Reusa a avaliação do sojatech_cloud/scripts/docai_minimo.py, então o CSV local e o do Google
Cloud têm as mesmas colunas e a comparação é direta. Não altera o extrator.

Uso:
  python scripts/avalia_pasta.py ../data/invoices/holdout_s9

ATENÇÃO: o holdout_s9 é lacrado. Avalie-o UMA vez, com o extrator congelado (veja
data/invoices/CONJUNTOS.md). Para ajustar o extrator use o desenvolvimento ou a validação.
"""
import argparse
import csv
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agroflow import config  # noqa: E402
from agroflow.invoices.local_extractor import extract  # noqa: E402  (carrega o pacote local antes do outro)


def _docai_minimo():
    caminho = config.REPO / "sojatech_cloud" / "scripts" / "docai_minimo.py"
    spec = importlib.util.spec_from_file_location("docai_minimo", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", type=Path, help="pasta com pdf/ e gabarito.csv")
    ap.add_argument("--saida", type=Path, help="CSV de saída (padrão: results/local_<pasta>.csv)")
    args = ap.parse_args()

    docai = _docai_minimo()
    linhas = docai.avalia(args.pasta, extract)
    saida = args.saida or config.RESULTS / f"local_{args.pasta.name}.csv"
    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    print(f"\n{docai.resumo(linhas)}\n\nCSV em {saida}")


if __name__ == "__main__":
    main()
