"""Vision API (label detection) nas folhas de teste: rótulos, scores e se algum nomeia a praga.

Sem bucket, Cloud Function nem BigQuery: lê as imagens de uma pasta, chama a Vision API
e grava um CSV com os rótulos e o score de cada um. A regra de "nomeia a praga" é a mesma
da linha de base local (sojatech_local/scripts/evaluate.py), para as duas serem comparáveis.

Uso (no Cloud Shell do lab, com a Vision API habilitada):
  python scripts/vision_minimo.py                                  # data/leaves/test (laboratório)
  python scripts/vision_minimo.py --pasta ../data/leaves/campo/teste
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config  # noqa: E402

TERMOS_PRAGA = ["rust", "blight", "spot", "fung", "disease", "mildew", "mold", "lesion", "pest"]
TERMOS_PLANTA = ["leaf", "plant", "corn", "maize", "ear", "vegetation", "grass", "flora", "botany"]


def amostra(itens: list, limite: int | None) -> list:
    """`limite` itens espaçados pela lista inteira (que vem ordenada por classe)."""
    if not limite or limite >= len(itens):
        return itens
    passo = len(itens) / limite
    return [itens[int(i * passo)] for i in range(limite)]


def tem(rotulo: str, termos: list[str]) -> int:
    return int(any(t in rotulo.lower() for t in termos))


def avalia(imagens: list[Path], rotular, k: int = 10) -> list[dict]:
    """Uma linha por imagem e rótulo devolvido. `rotular(path, k)` -> [(rótulo, score), ...]."""
    linhas = []
    for i, p in enumerate(imagens, 1):
        try:
            rotulos, erro = rotular(p, k), ""
        except Exception as e:  # uma imagem com problema não derruba o lote
            rotulos, erro = [], f"{type(e).__name__}: {e}"
        if not rotulos:
            linhas.append(dict(arquivo=p.name, classe=p.parent.name, rank=0, rotulo="", score=0.0,
                               praga=0, planta=0, erro=erro))
        for r, (rotulo, score) in enumerate(rotulos, 1):
            linhas.append(dict(arquivo=p.name, classe=p.parent.name, rank=r, rotulo=rotulo, score=score,
                               praga=tem(rotulo, TERMOS_PRAGA), planta=tem(rotulo, TERMOS_PLANTA), erro=""))
        if i % 10 == 0 or i == len(imagens):
            print(f"{i}/{len(imagens)}", flush=True)
    return linhas


def resumo(linhas: list[dict]) -> str:
    por_img = {}
    for l in linhas:
        d = por_img.setdefault((l["classe"], l["arquivo"]), dict(praga=0, planta=0, top1=0.0, rotulo1=""))
        d["praga"] |= l["praga"]
        d["planta"] |= l["planta"]
        if l["rank"] == 1:
            d["top1"], d["rotulo1"] = l["score"], l["rotulo"]
    n = len(por_img)
    media = lambda v: sum(v) / len(v) if v else 0.0
    out = [f"imagens: {n}",
           f"algum rótulo nomeia praga/doença: {sum(d['praga'] for d in por_img.values())}/{n}",
           f"algum rótulo menciona planta/folha: {sum(d['planta'] for d in por_img.values())}/{n}",
           f"score médio do rótulo top-1: {media([d['top1'] for d in por_img.values()]):.3f}",
           "por classe (nomeia praga / imagens):"]
    for c in sorted({k[0] for k in por_img}):
        ds = [d for k, d in por_img.items() if k[0] == c]
        out.append(f"  {c:18} {sum(d['praga'] for d in ds)}/{len(ds)}")
    top = Counter(d["rotulo1"] for d in por_img.values()).most_common(5)
    out.append("rótulos top-1 mais frequentes: " + ", ".join(f"{r or '(nenhum)'} ({q})" for r, q in top))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", type=Path, default=config.LEAVES_DIR / "test",
                    help="pasta com <classe>/<imagem> (padrão: data/leaves/test)")
    ap.add_argument("--k", type=int, default=10, help="rótulos por imagem")
    ap.add_argument("--limite", type=int, help="usa só N imagens espaçadas (para lab com pouco tempo)")
    ap.add_argument("--saida", type=Path, help="CSV de saída (padrão: results/vision_<pasta>.csv)")
    args = ap.parse_args()

    imagens = amostra(sorted(p for p in args.pasta.glob("*/*") if p.suffix.lower() in config.IMAGE_EXT),
                      args.limite)
    if not imagens:
        sys.exit(f"nenhuma imagem em {args.pasta}/<classe>/")
    from agroflow.leaves.gcp_models import baseline

    linhas = avalia(imagens, baseline, args.k)
    saida = args.saida or config.RESULTS / f"vision_{args.pasta.name}.csv"
    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    print(f"\n{resumo(linhas)}\n\nCSV em {saida}")


if __name__ == "__main__":
    main()
