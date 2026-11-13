"""Processa um lote inteiro direto (sem passar pelo bucket) e grava na tabela.

Uso:
  python scripts/run_batch.py notas    # data/invoices/pdf/*.pdf e data/invoices/teste/pdf/*.pdf
  python scripts/run_batch.py folhas   # validação e teste de laboratório e de campo (manifestos)

O nome gravado das notas de teste é "teste/<arquivo>" e o das folhas é
"<conjunto>/<particao>/<classe>/<arquivo>" (ex.: campo/teste/ferrugem_comum/...),
para a avaliação achar o gabarito certo. Nas folhas rodam o modelo do produto
(lab+campo) e o modelo lab, cada um se o arquivo existir; a linha de base roda
só nos testes, porque não escolhe nada na validação.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config, leaves, storage  # noqa: E402
from agroflow.leaves.conjuntos import Item, itens, nome_folha  # noqa: E402
from agroflow.pipeline import process_invoice, process_leaf  # noqa: E402


def itens_folhas() -> list[Item]:
    """Fotos de validação e de teste dos dois conjuntos; o treino nunca é processado aqui."""
    return [i for conjunto in ("lab", "campo") for particao in ("val", "teste") for i in itens(conjunto, particao)]


def lote_folhas(baseline: bool = True, produto: bool = True, lab: bool = True) -> int:
    """Processa as fotos de itens_folhas() e devolve quantas. Só apaga os tipos que vai regravar."""
    produto = produto and leaves.classificador_disponivel("produto")
    lab = lab and leaves.classificador_disponivel("lab")
    for tipo, ligado in (("folha_baseline", baseline), ("folha_classificador", produto),
                         ("folha_classificador_lab", lab)):
        if ligado:
            storage.clear(tipo)
    fotos = itens_folhas()
    for n, item in enumerate(fotos, 1):
        nome = nome_folha(item)
        rows = process_leaf(item.arquivo, nome, baseline=baseline and item.particao == "teste", classificador=produto)
        if lab:
            rows += process_leaf(item.arquivo, nome, baseline=False, classificador=True, modelo="lab")
        storage.save(rows)
        if n % 50 == 0:
            print(f"{n}/{len(fotos)}", flush=True)
    return len(fotos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lote", choices=["notas", "folhas"])
    ap.add_argument("--sem-baseline", action="store_true", help="folhas: pula a linha de base")
    ap.add_argument("--sem-classificador", action="store_true", help="folhas: só a linha de base")
    ap.add_argument("--sem-lab", action="store_true", help="folhas: pula o modelo treinado só com laboratório")
    args = ap.parse_args()

    if args.lote == "notas":
        storage.clear("nota")
        arquivos = [(p, p.name) for p in sorted((config.INVOICES_DIR / "pdf").glob("*.pdf"))]
        arquivos += [(p, f"teste/{p.name}") for p in sorted((config.INVOICES_TEST_DIR / "pdf").glob("*.pdf"))]
        for p, nome in arquivos:
            rows = process_invoice(p, nome=nome)
            storage.save(rows)
            print(nome, {r.campo: r.valor for r in rows})
        n = len(arquivos)
    else:
        n = lote_folhas(baseline=not args.sem_baseline, produto=not args.sem_classificador,
                        lab=not (args.sem_classificador or args.sem_lab))
    print(f"{n} arquivos processados")


if __name__ == "__main__":
    main()
