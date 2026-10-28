"""Treina o classificador de folhas localmente (substituto do Vertex AI AutoML).

Transfer learning de uma EfficientNet-B0 pré-treinada no ImageNet: congela
nada, poucas épocas, 15% do treino separado para validação. O conjunto de
teste não é tocado aqui; ele é avaliado por run_batch.py + evaluate.py.

Uso: python scripts/train_leaf_classifier.py [--epocas 8]
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Subset
from torchvision.datasets import ImageFolder

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sojatech import config  # noqa: E402
from sojatech.leaves.local_models import DEVICE, build_classifier, classifier_transform  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epocas", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    torch.manual_seed(args.seed)

    root = config.LEAVES_DIR / "train"
    ds_train = ImageFolder(root, classifier_transform(train=True))
    ds_val = ImageFolder(root, classifier_transform())
    idx = list(range(len(ds_train)))
    random.Random(args.seed).shuffle(idx)
    n_val = int(0.15 * len(idx))
    train_dl = DataLoader(Subset(ds_train, idx[n_val:]), batch_size=32, shuffle=True, num_workers=0)
    val_dl = DataLoader(Subset(ds_val, idx[:n_val]), batch_size=64, num_workers=0)

    model = build_classifier(len(ds_train.classes)).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epocas)
    loss_fn = torch.nn.CrossEntropyLoss()

    t0, hist = time.time(), []
    for ep in range(1, args.epocas + 1):
        model.train()
        tot = 0.0
        for x, y in train_dl:
            x, y = x.to(DEVICE), y.to(DEVICE)
            opt.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()
            tot += loss.item() * len(y)
        sched.step()
        model.eval()
        acertos = n = 0
        with torch.no_grad():
            for x, y in val_dl:
                acertos += (model(x.to(DEVICE)).argmax(1).cpu() == y).sum().item()
                n += len(y)
        hist.append(dict(epoca=ep, loss=tot / (len(idx) - n_val), acc_val=acertos / n))
        print(f"época {ep}: loss={hist[-1]['loss']:.3f} acc_val={hist[-1]['acc_val']:.3f}")

    config.MODELS.mkdir(exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "classes": ds_train.classes}, config.LEAF_MODEL)
    info = dict(classes=ds_train.classes, n_treino=len(idx) - n_val, n_val=n_val, epocas=args.epocas,
                tempo_treino_s=round(time.time() - t0, 1), dispositivo=DEVICE,
                gpu=torch.cuda.get_device_name() if DEVICE == "cuda" else None, historico=hist)
    (config.MODELS / "leaf_classifier.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
    print(f"modelo salvo em {config.LEAF_MODEL} ({info['tempo_treino_s']} s)")


if __name__ == "__main__":
    main()
