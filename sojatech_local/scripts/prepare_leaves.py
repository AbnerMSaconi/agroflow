"""Separa o subconjunto do PlantVillage usado no trabalho.

4 classes de milho (cultura de rotação da soja; o PlantVillage só tem soja
saudável). Treino de 100 por classe e um teste fixo de 25 por classe, que
avalia tanto a linha de base quanto o classificador.

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

ORIGEM = config.DOWNLOADS / "PlantVillage" / "raw" / "color"
CLASSES = {  # pasta do PlantVillage -> nome curto da classe
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "cercosporiose",
    "Corn_(maize)___Common_rust_": "ferrugem_comum",
    "Corn_(maize)___Northern_Leaf_Blight": "helmintosporiose",
    "Corn_(maize)___healthy": "saudavel",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--treino", type=int, default=100)
    ap.add_argument("--teste", type=int, default=25)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    if config.LEAVES_DIR.exists():
        shutil.rmtree(config.LEAVES_DIR)
    for pasta, classe in CLASSES.items():
        imgs = sorted((ORIGEM / pasta).glob("*.[jJ][pP][gG]"))
        rng.shuffle(imgs)
        for split, sel in (("test", imgs[:args.teste]), ("train", imgs[args.teste:args.teste + args.treino])):
            dst = config.LEAVES_DIR / split / classe
            dst.mkdir(parents=True)
            for i, src in enumerate(sel):
                nome = f"{classe}_{i:03d}.jpg"
                shutil.copy(src, dst / nome)
        print(f"{classe:18s} treino={args.treino} teste={args.teste} (de {len(imgs)})")


if __name__ == "__main__":
    main()
