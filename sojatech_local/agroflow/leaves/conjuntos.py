"""Conjuntos de fotos de folha: manifestos, hash perceptual, divisão e nomes gravados.

Dois conjuntos, cada um com um manifesto CSV fixo (arquivo, classe, particao):
- lab: PlantVillage, em data/leaves (validação é um pedaço fixo de train/);
- campo: PlantDoc, em data/leaves/campo.

Partições: treino, val, teste. O nome gravado na tabela de resultados é
<conjunto>/<particao>/<classe>/<arquivo>, e a avaliação lê o gabarito dele.
"""
import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .. import config

CLASSES = ["cercosporiose", "ferrugem_comum", "helmintosporiose", "saudavel"]
PASTAS_PLANTDOC = {"Corn Gray leaf spot": "cercosporiose", "Corn leaf blight": "helmintosporiose",
                   "Corn rust leaf": "ferrugem_comum"}
CONJUNTOS = ("lab", "campo")
PARTICOES = ("treino", "val", "teste")


@dataclass(frozen=True)
class Item:
    arquivo: Path
    classe: str
    conjunto: str
    particao: str


def dhash(img: Image.Image) -> int:
    """Hash perceptual de 64 bits: em cada linha da miniatura 9×8, esquerda < direita."""
    px = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS).tobytes()
    v = 0
    for y in range(8):
        for x in range(8):
            v = (v << 1) | (px[y * 9 + x] < px[y * 9 + x + 1])
    return v


def distancia(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def indices_unicos(hashes: list[int], limite: int = 4) -> list[int]:
    """Índices mantidos: cada hash fica só se estiver a mais de `limite` bits de todos os já mantidos."""
    mantidos: list[int] = []
    for i, h in enumerate(hashes):
        if all(distancia(h, hashes[j]) > limite for j in mantidos):
            mantidos.append(i)
    return mantidos


def dividir_estratificado(chaves: list[tuple[str, str]], seed: int = 42,
                          fracoes=(0.5, 0.15)) -> dict[str, str]:
    """(id, classe) -> partição. Cada classe tem seu próprio sorteio, independente das outras."""
    por_classe: dict[str, list[str]] = defaultdict(list)
    for id_, classe in chaves:
        por_classe[classe].append(id_)
    out = {}
    for classe, ids in por_classe.items():
        ids = sorted(ids)
        random.Random(f"{seed}-{classe}").shuffle(ids)
        n_treino, n_val = round(fracoes[0] * len(ids)), round(fracoes[1] * len(ids))
        for i, id_ in enumerate(ids):
            out[id_] = "treino" if i < n_treino else "val" if i < n_treino + n_val else "teste"
    return out


def escrever_manifesto(caminho: Path, linhas: list[dict]) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(linhas, key=lambda linha: linha["arquivo"]))


def itens(conjunto: str, particao: str) -> list[Item]:
    """Fotos de uma partição, na ordem do manifesto. Lê o config na hora (os testes trocam os caminhos)."""
    if conjunto == "lab":
        manifesto, base = config.MANIFESTO_LAB, config.LEAVES_DIR
    elif conjunto == "campo":
        manifesto, base = config.MANIFESTO_CAMPO, config.CAMPO_DIR
    else:
        raise ValueError(f"conjunto desconhecido: {conjunto}")
    with open(manifesto, encoding="utf-8", newline="") as f:
        return [Item(base / linha["arquivo"], linha["classe"], conjunto, particao)
                for linha in csv.DictReader(f) if linha["particao"] == particao]


def nome_folha(item: Item) -> str:
    return f"{item.conjunto}/{item.particao}/{item.classe}/{item.arquivo.name}"


def ler_nome_folha(nome: str) -> tuple[str, str, str] | None:
    """(conjunto, particao, classe) de um nome gravado, ou None se não tiver esse formato."""
    partes = nome.split("/")
    if (len(partes) == 4 and partes[0] in CONJUNTOS and partes[1] in PARTICOES
            and partes[2] in CLASSES and partes[3]):
        return partes[0], partes[1], partes[2]
    return None
