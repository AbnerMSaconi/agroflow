"""Treina o classificador de folhas (GPU desta máquina, a 3090 ou o Colab; CPU funciona, bem devagar).

  --dados lab+campo (padrão): o modelo do produto -> models/leaf_classifier.pt
  --dados lab: só fotos de laboratório -> models/leaf_classifier_lab.pt (mede a queda no campo)

A rede padrão é a vencedora da disputa (scripts/disputa_redes.py). As partições vêm
dos manifestos em data/leaves; o teste não é tocado aqui, e sim por run_batch.py + evaluate.py.

Uso: python scripts/train_leaf_classifier.py [--dados lab] [--rede convnext_small] [--epocas 15]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config  # noqa: E402
from agroflow.leaves.redes import REDE_PADRAO, REDES  # noqa: E402
from agroflow.leaves.treino import treinar  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rede", choices=list(REDES), default=REDE_PADRAO)
    ap.add_argument("--dados", choices=["lab", "lab+campo"], default="lab+campo")
    ap.add_argument("--epocas", type=int, default=15)
    ap.add_argument("--lote", type=int, default=None, help="micro-lote (padrão: o da rede em redes.REDES)")
    ap.add_argument("--saida", type=Path, default=None)
    args = ap.parse_args()
    saida = args.saida or (config.LEAF_MODEL if args.dados == "lab+campo" else config.LEAF_MODEL_LAB)
    info = treinar(args.rede, args.dados, saida, epocas=args.epocas, lote=args.lote)
    print(f"modelo salvo em {saida}: {info['rede']}, época {info['melhor_epoca']}, val {info['val']}, "
          f"{info['tempo_treino_s']} s")


if __name__ == "__main__":
    main()
