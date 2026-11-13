"""Treino do classificador de folhas, com qualquer rede de `redes` e dados lab ou lab+campo.

- lab: só PlantVillage; a época é escolhida na validação de laboratório e nenhuma
  foto de campo é lida (é o modelo que mede a queda no campo).
- lab+campo: o modelo do produto; as fotos de campo são ~1/3 de cada época
  (amostragem ponderada) e a época é escolhida na validação de campo.

Precisão mista e channels_last na GPU; o lote efetivo é o mesmo para todas as redes,
completado por acumulação de gradiente quando o micro-lote é menor.
"""
import hashlib
import json
import math
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

import torch
from PIL import Image
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from . import conjuntos
from .conjuntos import CLASSES, Item
from .redes import REDES, construir_rede, n_parametros, resolucao, transformacoes


class ImagensDataset(Dataset):
    def __init__(self, itens: list[Item], classes: list[str], transform):
        self.itens, self.transform = list(itens), transform
        self.indice = {c: i for i, c in enumerate(classes)}

    def __len__(self):
        return len(self.itens)

    def __getitem__(self, i):
        item = self.itens[i]
        with Image.open(item.arquivo) as im:
            img = im.convert("RGB")
        return self.transform(img), self.indice[item.classe]


def pesos_amostragem(conjuntos: list[str], fracao_campo: float = 1 / 3) -> list[float]:
    """Peso de cada foto para o campo somar `fracao_campo` de cada época (1.0 para todas sem campo)."""
    n_campo = sum(c == "campo" for c in conjuntos)
    if n_campo == 0:
        return [1.0] * len(conjuntos)
    n_lab = len(conjuntos) - n_campo
    return [fracao_campo / n_campo if c == "campo" else (1 - fracao_campo) / n_lab for c in conjuntos]


def passos_acumulacao(lote_efetivo: int, lote: int) -> int:
    return max(1, math.ceil(lote_efetivo / lote))


def escolher_vencedora(resultados: list[dict], margem: float = 0.02) -> str:
    """Maior F1 na validação de campo; diferença menor que `margem` vai para a de menos parâmetros."""
    melhor = max(r["f1_val_campo"] for r in resultados)
    perto = [r for r in resultados if melhor - r["f1_val_campo"] < margem]
    return min(perto, key=lambda r: r["n_parametros"])["rede"]


def _cortar(lista: list[Item], maximo: int | None) -> list[Item]:
    """As primeiras `maximo` fotos de cada classe (todas se None)."""
    if maximo is None:
        return lista
    conta, out = defaultdict(int), []
    for item in lista:
        if conta[item.classe] < maximo:
            out.append(item)
            conta[item.classe] += 1
    return out


@torch.no_grad()
def _avaliar(model, dl, dispositivo: str, amp: bool) -> dict:
    """Acurácia e F1 macro sobre as classes presentes (prever uma classe ausente conta como erro)."""
    model.eval()
    reais, previstos = [], []
    for x, y in dl:
        x = x.to(dispositivo, non_blocking=True)
        if amp:
            x = x.to(memory_format=torch.channels_last)
        with torch.autocast(device_type=dispositivo, enabled=amp):
            previstos += model(x).argmax(1).cpu().tolist()
        reais += y.tolist()
    return dict(acuracia=sum(a == b for a, b in zip(reais, previstos)) / len(reais),
                f1_macro=float(f1_score(reais, previstos, labels=sorted(set(reais)), average="macro",
                                        zero_division=0)))


def treinar(rede: str, dados: str, saida: Path, epocas: int = 15, lote: int | None = None,
            lote_efetivo: int = 32, lr: float = 1e-4, seed: int = 42, fracao_campo: float = 1 / 3,
            pretreinada: bool = True, workers: int = 4, max_por_classe: int | None = None) -> dict:
    if dados not in ("lab", "lab+campo"):
        raise ValueError(f"dados deve ser 'lab' ou 'lab+campo', não {dados!r}")
    saida = Path(saida)
    random.seed(seed)
    torch.manual_seed(seed)
    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    amp = dispositivo == "cuda"
    lote = lote or REDES[rede]["lote"]
    passos = passos_acumulacao(lote_efetivo, lote)

    com_campo = dados == "lab+campo"
    itens_treino = _cortar(conjuntos.itens("lab", "treino"), max_por_classe)
    itens_val = {"lab": _cortar(conjuntos.itens("lab", "val"), max_por_classe)}
    if com_campo:
        itens_treino += _cortar(conjuntos.itens("campo", "treino"), max_por_classe)
        itens_val["campo"] = _cortar(conjuntos.itens("campo", "val"), max_por_classe)

    amostrador = WeightedRandomSampler(pesos_amostragem([i.conjunto for i in itens_treino], fracao_campo),
                                       num_samples=len(itens_treino), replacement=True,
                                       generator=torch.Generator().manual_seed(seed))
    dl_treino = DataLoader(ImagensDataset(itens_treino, CLASSES, transformacoes(rede, True)), batch_size=lote,
                           sampler=amostrador, num_workers=workers, persistent_workers=workers > 0,
                           pin_memory=amp)
    # validação é pequena: roda no processo principal, sem abrir mais processos (caros no Windows)
    tf_val = transformacoes(rede, False)
    dl_val = {k: DataLoader(ImagensDataset(v, CLASSES, tf_val), batch_size=2 * lote) for k, v in itens_val.items()}

    model = construir_rede(rede, len(CLASSES), pretreinada).to(dispositivo)
    if amp:
        model = model.to(memory_format=torch.channels_last)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.05)
    passos_por_epoca = math.ceil(len(dl_treino) / passos)
    total = epocas * passos_por_epoca

    def fator(passo):  # 1 época de aquecimento linear, depois cosseno até zero
        if passo < passos_por_epoca:
            return (passo + 1) / passos_por_epoca
        return 0.5 * (1 + math.cos(math.pi * (passo - passos_por_epoca) / max(1, total - passos_por_epoca)))

    agenda = torch.optim.lr_scheduler.LambdaLR(opt, fator)
    escala = torch.amp.GradScaler("cuda", enabled=amp)
    perda_fn = torch.nn.CrossEntropyLoss()

    escolha = "campo" if com_campo else "lab"
    historico, melhor, melhor_estado, t0 = [], None, None, time.time()
    for ep in range(1, epocas + 1):
        model.train()
        soma, n = 0.0, 0
        opt.zero_grad(set_to_none=True)
        for i, (x, y) in enumerate(dl_treino, 1):
            x, y = x.to(dispositivo, non_blocking=True), y.to(dispositivo, non_blocking=True)
            if amp:
                x = x.to(memory_format=torch.channels_last)
            with torch.autocast(device_type=dispositivo, enabled=amp):
                perda = perda_fn(model(x), y)
            escala.scale(perda / passos).backward()
            soma, n = soma + perda.item() * len(y), n + len(y)
            if i % passos == 0 or i == len(dl_treino):  # o último lote da época também dá o passo
                antes = escala.get_scale()
                escala.step(opt)
                escala.update()
                opt.zero_grad(set_to_none=True)
                if escala.get_scale() >= antes:  # passo pulado por overflow não avança a agenda
                    agenda.step()
        val = {k: _avaliar(model, dl, dispositivo, amp) for k, dl in dl_val.items()}
        historico.append(dict(epoca=ep, perda=soma / n, val=val))
        print(f"[{rede} {dados}] época {ep}/{epocas}: perda {soma / n:.3f} "
              + " ".join(f"{k}: acc {v['acuracia']:.3f} f1 {v['f1_macro']:.3f}" for k, v in val.items()), flush=True)
        if melhor is None or val[escolha]["f1_macro"] > melhor["val"][escolha]["f1_macro"]:
            melhor = dict(epoca=ep, val=val)
            melhor_estado = {k: v.detach().to("cpu", copy=True) for k, v in model.state_dict().items()}

    saida.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"rede": rede, "classes": CLASSES, "resolucao": resolucao(rede), "state_dict": melhor_estado}, saida)
    info = dict(rede=rede, dados=dados, classes=CLASSES, resolucao=resolucao(rede), n_parametros=n_parametros(rede),
                epocas=epocas, melhor_epoca=melhor["epoca"], lote=lote, passos_acumulacao=passos,
                n_treino=dict(Counter(i.conjunto for i in itens_treino)),
                n_val={k: len(v) for k, v in itens_val.items()},
                val={"lab": melhor["val"]["lab"], "campo": melhor["val"].get("campo")},
                historico=historico, tempo_treino_s=round(time.time() - t0, 1), dispositivo=dispositivo,
                gpu=torch.cuda.get_device_name() if amp else None,
                sha256=hashlib.sha256(saida.read_bytes()).hexdigest())
    saida.with_suffix(".json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    return info
