"""Monta o conjunto de campo (fotos tiradas na lavoura) a partir do PlantDoc.

Três classes de milho com doença (o PlantDoc não tem milho saudável):
  Corn Gray leaf spot -> cercosporiose, Corn leaf blight -> helmintosporiose,
  Corn rust leaf -> ferrugem_comum.

1. Baixa só essas pastas do PlantDoc para _downloads/PlantDoc. Sem checkout: o PlantDoc
   tem nomes com "?" (inválidos no Windows) e o checkout falha; as fotos saem direto dos
   objetos do git, com "_" no lugar desses caracteres.
2. Junta o treino e o teste originais e tira as fotos repetidas (dHash a até 4 bits):
   o PlantDoc tem a mesma foto nos dois lados, por isso a divisão original não serve.
3. Divide de novo por classe (50% treino, 15% validação, 35% teste, semente fixa).
4. Grava em data/leaves/campo/<particao>/<classe>/ com no máximo 512 px, mais o
   manifesto.csv (foto de origem e hash) e o FONTE.md (atribuição, CC BY 4.0).

Uso: python -I scripts/prepare_campo.py
(-I: as fotos vêm da internet; o script só passa caminhos para o Pillow.)
"""
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config  # noqa: E402
from agroflow.leaves.conjuntos import (PARTICOES, PASTAS_PLANTDOC, dhash, dividir_estratificado,  # noqa: E402
                                       escrever_manifesto, indices_unicos)

REPO_PLANTDOC = "https://github.com/pratikkayal/PlantDoc-Dataset"
EXTENSOES = {".jpg", ".jpeg", ".png"}
INVALIDOS_WINDOWS = re.compile(r'[<>:"|?*\\]')
FONTE = """# Fotos de campo: PlantDoc

As fotos desta pasta vêm do PlantDoc, publicado sob a licença Creative Commons
Atribuição 4.0 Internacional (CC BY 4.0): {repo}

Singh, D.; Jain, N.; Jain, P.; Kayal, P.; Kumawat, S.; Batra, N. PlantDoc: A Dataset
for Visual Plant Disease Detection. CoDS-COMAD 2020.

Usamos só as três pastas de milho com doença:

| Pasta do PlantDoc | Classe aqui |
|---|---|
{tabela}

Alterações feitas por `sojatech_local/scripts/prepare_campo.py`:
- fotos reduzidas para no máximo 512 px no lado maior e regravadas em JPEG;
- fotos repetidas (hash perceptual a até 4 bits de distância) removidas, ficando uma;
- divisão refeita por classe: 50% treino, 15% validação e 35% teste, com semente fixa.

O `manifesto.csv` liga cada arquivo à foto de origem no repositório do PlantDoc (na coluna
`origem`, caracteres que o Windows não aceita em nomes, como `?`, aparecem como `_`).
""".format(repo=REPO_PLANTDOC, tabela="\n".join(f"| {p} | {c} |" for p, c in PASTAS_PLANTDOC.items()))


def baixar_plantdoc(destino: Path, repo: str = REPO_PLANTDOC) -> Path:
    """Grava as 6 pastas de milho do PlantDoc em destino/<train|test>/<pasta>/ e devolve destino.

    Clona sem baixar fotos (--filter=blob:none) e lê só as das 6 pastas com `git cat-file`,
    que busca cada uma no servidor (~0,7 s por foto). O arquivo .baixado marca o fim.
    """
    destino = Path(destino)
    pronto = destino / ".baixado"
    if pronto.exists():
        return destino
    if not (destino / ".git").exists():
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth", "1", repo, str(destino)],
                       check=True)
    git = ["git", "-C", str(destino)]
    pastas = [f"{split}/{pasta}" for split in ("train", "test") for pasta in PASTAS_PLANTDOC]
    arvore = subprocess.run(git + ["ls-tree", "-r", "-z", "HEAD", "--"] + pastas, check=True, capture_output=True).stdout
    arquivos = []
    for registro in filter(None, arvore.split(b"\0")):  # "<modo> <tipo> <oid>\t<caminho>"
        meta, caminho = registro.split(b"\t", 1)
        _, tipo, oid = meta.split()
        if tipo == b"blob":
            arquivos.append((oid.decode(), caminho.decode("utf-8")))
    print(f"baixando {len(arquivos)} fotos do PlantDoc, uma a uma (alguns minutos)...", flush=True)
    saida = subprocess.run(git + ["cat-file", "--batch"], input="".join(f"{oid}\n" for oid, _ in arquivos).encode(),
                           check=True, capture_output=True).stdout
    pos, gravados = 0, set()
    for _, caminho in arquivos:  # cada objeto: "<oid> <tipo> <tamanho>\n<conteúdo>\n"
        fim = saida.index(b"\n", pos)
        tamanho = int(saida[pos:fim].split()[2])
        dados, pos = saida[fim + 1:fim + 1 + tamanho], fim + 1 + tamanho + 1
        pasta, nome = caminho.rsplit("/", 1)
        alvo = destino / pasta / INVALIDOS_WINDOWS.sub("_", nome)
        if alvo in gravados:
            raise ValueError(f"dois arquivos viram o mesmo nome no Windows: {caminho}")
        gravados.add(alvo)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(dados)
    pronto.write_text(f"{len(arquivos)} fotos de {repo}\n", encoding="utf-8")
    return destino


def _fotos(origem: Path) -> list[tuple[str, str, Path]]:
    """(caminho relativo, classe, caminho) de cada foto das 6 pastas, em ordem de caminho."""
    fotos = [(p.relative_to(origem).as_posix(), classe, p)
             for split in ("train", "test") for pasta, classe in PASTAS_PLANTDOC.items()
             for p in (origem / split / pasta).glob("*") if p.is_file() and p.suffix.lower() in EXTENSOES]
    return sorted(fotos)


def preparar_campo(origem: Path, destino: Path, seed: int = 42, lado_max: int = 512, limite: int = 4) -> dict:
    origem, destino = Path(origem), Path(destino)
    fotos = _fotos(origem)
    puladas, miniaturas = [], []
    for rel, classe, caminho in fotos:
        try:
            with Image.open(caminho) as im:
                img = ImageOps.exif_transpose(im).convert("RGB")
            img.thumbnail((lado_max, lado_max))
        except Exception as e:  # noqa: BLE001 — foto corrompida ou formato estranho: registra e segue
            puladas.append((rel, f"{type(e).__name__}: {e}"))
            continue
        miniaturas.append((rel, classe, img))

    hashes = [dhash(img) for _, _, img in miniaturas]
    unicas = [(*miniaturas[i], hashes[i]) for i in indices_unicos(hashes, limite)]
    particao = dividir_estratificado([(rel, classe) for rel, classe, _, _ in unicas], seed)

    for sub in PARTICOES:
        if (destino / sub).exists():
            shutil.rmtree(destino / sub)
    (destino / "manifesto.csv").unlink(missing_ok=True)

    numero = defaultdict(int)
    por_particao = {p: defaultdict(int) for p in PARTICOES}
    linhas = []
    for rel, classe, img, h in unicas:
        p = particao[rel]
        nome = f"{classe}_campo_{numero[classe]:03d}.jpg"
        numero[classe] += 1
        (destino / p / classe).mkdir(parents=True, exist_ok=True)
        img.save(destino / p / classe / nome, quality=90)
        linhas.append(dict(arquivo=f"{p}/{classe}/{nome}", classe=classe, particao=p, origem=rel,
                           dhash=f"{h:016x}"))
        por_particao[p][classe] += 1
    escrever_manifesto(destino / "manifesto.csv", linhas)
    (destino / "FONTE.md").write_text(FONTE, encoding="utf-8", newline="\n")
    return dict(lidas=len(fotos), puladas=puladas, repetidas=len(miniaturas) - len(unicas),
                por_particao={p: dict(sorted(c.items())) for p, c in por_particao.items()})


def main():
    origem = baixar_plantdoc(config.DOWNLOADS / "PlantDoc")
    res = preparar_campo(origem, config.CAMPO_DIR)
    gravadas = res["lidas"] - len(res["puladas"]) - res["repetidas"]
    print(f"lidas={res['lidas']} puladas={len(res['puladas'])} repetidas={res['repetidas']} gravadas={gravadas}")
    for rel, motivo in res["puladas"]:
        print(f"  pulada: {rel} ({motivo})")
    for p, contagem in res["por_particao"].items():
        print(f"{p:7s} {contagem} total={sum(contagem.values())}")


if __name__ == "__main__":
    main()
