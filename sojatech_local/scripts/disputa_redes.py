"""Disputa entre as redes candidatas do classificador de folhas (dados lab+campo).

Todas treinam com o mesmo protocolo (épocas, semente, aumento de dados e lote efetivo)
e são medidas na validação de campo: vence o maior F1 macro, e uma diferença menor que
0,02 vai para a rede com menos parâmetros. O teste não entra na escolha.

A vencedora vira o modelo do produto (models/leaf_classifier.pt e .json), e o resultado
fica em results/disputa_redes.json. --rapido treina 1 época com 8 fotos por classe só para
conferir que tudo roda e cabe na GPU; não grava resultado nem troca o modelo.

Uso: python scripts/disputa_redes.py [--rapido] [--redes efficientnet_b0 vit_b_16] [--epocas 15]
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config  # noqa: E402
from agroflow.leaves.redes import REDES  # noqa: E402
from agroflow.leaves.treino import escolher_vencedora, treinar  # noqa: E402


def disputar(redes: list[str], epocas: int = 15, rapido: bool = False, pretreinada: bool = True,
             workers: int = 4) -> dict:
    pasta = config.MODELS / ("disputa_rapida" if rapido else "disputa")
    candidatas = []
    for rede in redes:
        info = treinar(rede, "lab+campo", pasta / f"{rede}.pt", epocas=1 if rapido else epocas,
                       max_por_classe=8 if rapido else None, pretreinada=pretreinada, workers=workers)
        candidatas.append(dict(rede=rede, f1_val_campo=info["val"]["campo"]["f1_macro"],
                               acuracia_val_campo=info["val"]["campo"]["acuracia"],
                               f1_val_lab=info["val"]["lab"]["f1_macro"], n_parametros=info["n_parametros"],
                               tempo_treino_s=info["tempo_treino_s"], lote=info["lote"],
                               melhor_epoca=info["melhor_epoca"]))
    resultado = dict(candidatas=candidatas, vencedora=escolher_vencedora(candidatas))
    if not rapido:
        config.DISPUTA.parent.mkdir(parents=True, exist_ok=True)
        config.DISPUTA.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
        vencedora = pasta / f"{resultado['vencedora']}.pt"
        shutil.copyfile(vencedora, config.LEAF_MODEL)
        shutil.copyfile(vencedora.with_suffix(".json"), config.LEAF_MODEL.with_suffix(".json"))
    return resultado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--redes", nargs="+", choices=list(REDES), default=list(REDES))
    ap.add_argument("--epocas", type=int, default=15)
    ap.add_argument("--rapido", action="store_true", help="1 época, 8 fotos por classe; não grava nada")
    args = ap.parse_args()
    r = disputar(args.redes, epocas=args.epocas, rapido=args.rapido)
    print(f"\n{'rede':18s} {'parâm. (M)':>10s} {'F1 val campo':>12s} {'F1 val lab':>10s} {'época':>5s} "
          f"{'lote':>4s} {'tempo (min)':>11s}")
    for c in r["candidatas"]:
        print(f"{c['rede']:18s} {c['n_parametros'] / 1e6:10.1f} {c['f1_val_campo']:12.3f} {c['f1_val_lab']:10.3f} "
              f"{c['melhor_epoca']:5d} {c['lote']:4d} {c['tempo_treino_s'] / 60:11.1f}")
    print(f"vencedora: {r['vencedora']}" + ("" if args.rapido else f" -> copiada para {config.LEAF_MODEL}"))


if __name__ == "__main__":
    main()
