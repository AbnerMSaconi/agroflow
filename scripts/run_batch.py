"""Processa um lote inteiro direto (sem passar pelo bucket) e grava na tabela.

Uso:
  python scripts/run_batch.py notas    # data/invoices/pdf/*.pdf
  python scripts/run_batch.py folhas   # data/leaves/test/<classe>/*
O nome gravado das folhas é "<classe>/<arquivo>" para a avaliação achar o gabarito.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sojatech import config, storage  # noqa: E402
from sojatech.pipeline import process_invoice, process_leaf  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lote", choices=["notas", "folhas"])
    ap.add_argument("--sem-baseline", action="store_true", help="folhas: pula a linha de base")
    args = ap.parse_args()

    if args.lote == "notas":
        storage.clear("nota")
        arquivos = sorted((config.INVOICES_DIR / "pdf").glob("*.pdf"))
        for p in arquivos:
            rows = process_invoice(p)
            storage.save(rows)
            print(p.name, {r.campo: r.valor for r in rows})
    else:
        storage.clear("folha_classificador")
        if not args.sem_baseline:
            storage.clear("folha_baseline")
        arquivos = sorted((config.LEAVES_DIR / "test").glob("*/*"))
        for i, p in enumerate(arquivos, 1):
            storage.save(process_leaf(p, nome=f"{p.parent.name}/{p.name}", baseline=not args.sem_baseline))
            if i % 20 == 0:
                print(f"{i}/{len(arquivos)}")
    print(f"{len(arquivos)} arquivos processados com backend={config.BACKEND}")


if __name__ == "__main__":
    main()
