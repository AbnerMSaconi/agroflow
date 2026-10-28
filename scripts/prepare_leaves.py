"""Separa o subconjunto do PlantVillage usado no trabalho.

4 classes de milho (cultura de rotação da soja; o PlantVillage só tem soja
saudável). Treino de 100 por classe e um teste fixo de 25 por classe, que
avalia tanto a linha de base quanto o classificador. Também escreve o CSV de
importação do Vertex AI (gs://<bucket>/folhas/treino/<classe>/<arquivo>,<classe>).

Baixar a origem (só as pastas de milho, ~60 MB):
  git clone --filter=blob:none --no-checkout --depth 1 https://github.com/spMohanty/PlantVillage-Dataset _downloads/PlantVillage
  cd _downloads/PlantVillage && git sparse-checkout set --no-cone "/raw/color/Corn_(maize)___*/" && git checkout

Uso: python scripts/prepare_leaves.py [--gcs-bucket meu-bucket]
"""
import argparse
import csv
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sojatech import config  # noqa: E402

ORIGEM = config.ROOT / "_downloads" / "PlantVillage" / "raw" / "color"
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
    ap.add_argument("--gcs-bucket", default="SEU-BUCKET")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    if config.LEAVES_DIR.exists():
        shutil.rmtree(config.LEAVES_DIR)
    vertex = []
    for pasta, classe in CLASSES.items():
        imgs = sorted((ORIGEM / pasta).glob("*.[jJ][pP][gG]"))
        rng.shuffle(imgs)
        for split, sel in (("test", imgs[:args.teste]), ("train", imgs[args.teste:args.teste + args.treino])):
            dst = config.LEAVES_DIR / split / classe
            dst.mkdir(parents=True)
            for i, src in enumerate(sel):
                nome = f"{classe}_{i:03d}.jpg"
                shutil.copy(src, dst / nome)
                if split == "train":
                    vertex.append((f"gs://{args.gcs_bucket}/folhas/treino/{classe}/{nome}", classe))
        print(f"{classe:18s} treino={args.treino} teste={args.teste} (de {len(imgs)})")

    with open(config.LEAVES_DIR / "vertex_import.csv", "w", newline="") as f:
        csv.writer(f).writerows(vertex)
    print(f"CSV do Vertex: {config.LEAVES_DIR / 'vertex_import.csv'}")


if __name__ == "__main__":
    main()
