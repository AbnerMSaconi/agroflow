"""Processa um lote inteiro direto (sem passar pelo bucket) e grava na tabela.

Uso:
  python scripts/run_batch.py notas    # data/invoices/pdf/*.pdf e data/invoices/teste/pdf/*.pdf
  python scripts/run_batch.py folhas   # data/leaves/test/<classe>/*
O nome gravado das folhas é "<classe>/<arquivo>" e o das notas de teste é
"teste/<arquivo>", para a avaliação achar o gabarito certo.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config, storage  # noqa: E402
from agroflow.pipeline import process_invoice, process_leaf  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lote", choices=["notas", "folhas"])
    ap.add_argument("--sem-baseline", action="store_true", help="folhas: pula a linha de base")
    ap.add_argument("--sem-classificador", action="store_true", help="folhas: só a linha de base")
    args = ap.parse_args()

    if args.lote == "notas":
        storage.clear("nota")
        arquivos = [(p, p.name) for p in sorted((config.INVOICES_DIR / "pdf").glob("*.pdf"))]
        arquivos += [(p, f"teste/{p.name}") for p in sorted((config.INVOICES_TEST_DIR / "pdf").glob("*.pdf"))]
        for p, nome in arquivos:
            rows = process_invoice(p, nome=nome)
            storage.save(rows)
            print(nome, {r.campo: r.valor for r in rows})
    else:
        if not args.sem_classificador:
            storage.clear("folha_classificador")
        if not args.sem_baseline:
            storage.clear("folha_baseline")
        arquivos = sorted((config.LEAVES_DIR / "test").glob("*/*"))
        for i, p in enumerate(arquivos, 1):
            storage.save(process_leaf(p, nome=f"{p.parent.name}/{p.name}", baseline=not args.sem_baseline,
                                      classificador=not args.sem_classificador))
            if i % 20 == 0:
                print(f"{i}/{len(arquivos)}")
    print(f"{len(arquivos)} arquivos processados")


if __name__ == "__main__":
    main()
