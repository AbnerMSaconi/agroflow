"""Separa o subconjunto do PlantVillage usado no trabalho (fotos de laboratório).

4 classes de milho (cultura de rotação da soja; o PlantVillage só tem soja
saudável). Por classe: um teste fixo de 25 fotos, que avalia a linha de base e
os classificadores, e 450 de treino, das quais 15% (fixas) são a validação.
As partições ficam em data/leaves/manifesto_lab.csv.

O sorteio é o mesmo desde a primeira versão (100 de treino): o teste não muda e
as 100 fotos de treino antigas continuam com o mesmo nome; as novas vêm depois.
A pasta data/leaves/campo (fotos de campo, scripts/prepare_campo.py) não é tocada.

Baixar a origem (só as pastas de milho, ~60 MB), a partir da raiz do repositório:
  git clone --filter=blob:none --no-checkout --depth 1 https://github.com/spMohanty/PlantVillage-Dataset _downloads/PlantVillage
  cd _downloads/PlantVillage && git sparse-checkout set --no-cone "/raw/color/Corn_(maize)___*/" && git checkout

Uso: python scripts/prepare_leaves.py
"""
import argparse
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config  # noqa: E402
from agroflow.leaves.conjuntos import escrever_manifesto  # noqa: E402

ORIGEM = config.DOWNLOADS / "PlantVillage" / "raw" / "color"
CLASSES = {  # pasta do PlantVillage -> nome curto da classe (a ordem define o sorteio)
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "cercosporiose",
    "Corn_(maize)___Common_rust_": "ferrugem_comum",
    "Corn_(maize)___Northern_Leaf_Blight": "helmintosporiose",
    "Corn_(maize)___healthy": "saudavel",
}


def preparar_lab(origem: Path, destino: Path, treino: int = 450, teste: int = 25,
                 frac_val: float = 0.15, seed: int = 42) -> None:
    origem, destino = Path(origem), Path(destino)
    for sub in ("train", "test"):
        if (destino / sub).exists():
            shutil.rmtree(destino / sub)
    (destino / "manifesto_lab.csv").unlink(missing_ok=True)

    rng = random.Random(seed)
    linhas = []
    for pasta, classe in CLASSES.items():
        imgs = sorted((origem / pasta).glob("*.[jJ][pP][gG]"))
        rng.shuffle(imgs)
        nomes = {}
        for split, sel in (("test", imgs[:teste]), ("train", imgs[teste:teste + treino])):
            dst = destino / split / classe
            dst.mkdir(parents=True)
            nomes[split] = [f"{classe}_{i:03d}.jpg" for i in range(len(sel))]
            for src, nome in zip(sel, nomes[split]):
                shutil.copy(src, dst / nome)
        # validação: sorteio próprio, para não mexer no sorteio do teste e do treino
        embaralhados = list(nomes["train"])
        random.Random(f"{seed}-val-{classe}").shuffle(embaralhados)
        val = set(embaralhados[:round(frac_val * len(embaralhados))])
        linhas += [dict(arquivo=f"test/{classe}/{n}", classe=classe, particao="teste") for n in nomes["test"]]
        linhas += [dict(arquivo=f"train/{classe}/{n}", classe=classe, particao="val" if n in val else "treino")
                    for n in nomes["train"]]
        print(f"{classe:18s} treino={len(nomes['train'])} (val {len(val)}) teste={len(nomes['test'])} "
              f"(de {len(imgs)})")
    escrever_manifesto(destino / "manifesto_lab.csv", linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--treino", type=int, default=450)
    ap.add_argument("--teste", type=int, default=25)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    preparar_lab(ORIGEM, config.LEAVES_DIR, treino=args.treino, teste=args.teste, seed=args.seed)


if __name__ == "__main__":
    main()
