"""prepare_campo: fotos do PlantDoc viram o conjunto de campo (sem repetidas, até 512 px)."""
import itertools
import re
import subprocess

import pandas as pd
import pytest
from PIL import Image

import prepare_campo
from agroflow.leaves.conjuntos import distancia
from prepare_campo import baixar_plantdoc, preparar_campo

RUST, BLIGHT, GRAY = "Corn rust leaf", "Corn leaf blight", "Corn Gray leaf spot"


@pytest.fixture
def plantdoc_falso(tmp_path, fazer_imagem):
    o = tmp_path / "PlantDoc"
    a = fazer_imagem(o / "train" / RUST / "a.jpg", 1, (300, 200))
    fazer_imagem(o / "train" / RUST / "Foto (1).JPG", 2, (300, 200))
    fazer_imagem(o / "train" / RUST / "g.png", 3, (300, 200), modo="L")
    fazer_imagem(o / "train" / RUST / "r.png", 4, (300, 200), modo="RGBA")
    fazer_imagem(o / "train" / RUST / "grande.jpg", 5, (1200, 800))
    (o / "test" / RUST).mkdir(parents=True)
    Image.open(a).save(o / "test" / RUST / "a_copia.jpg", quality=60)  # a mesma foto, recomprimida
    fazer_imagem(o / "train" / BLIGHT / "c.jpeg", 6, (300, 200), modo="CMYK")
    q = fazer_imagem(o / "train" / BLIGHT / "quebrada.jpg", 7, (300, 200))
    q.write_bytes(q.read_bytes()[:300])
    for k, pasta in enumerate((RUST, BLIGHT, GRAY)):
        for i in range(10):
            fazer_imagem(o / ("train" if i % 2 else "test") / pasta / f"{k}_{i}.jpg", 100 + 10 * k + i, (300, 200))
    return o


def arquivos(pasta):
    return {p.relative_to(pasta).as_posix(): p.read_bytes() for p in sorted(pasta.rglob("*")) if p.is_file()}


def test_prepara_campo(tmp_path, plantdoc_falso):
    res = preparar_campo(plantdoc_falso, tmp_path / "campo")
    assert res["lidas"] == 38 and res["repetidas"] == 1
    assert [a for a, _ in res["puladas"]] == ["train/Corn leaf blight/quebrada.jpg"]
    saidas = sorted((tmp_path / "campo").glob("*/*/*.jpg"))
    for f in saidas:
        with Image.open(f) as im:
            assert im.mode == "RGB" and max(im.size) <= 512
        assert re.fullmatch(r"(cercosporiose|ferrugem_comum|helmintosporiose)_campo_\d{3}\.jpg", f.name)
    m = pd.read_csv(tmp_path / "campo/manifesto.csv", dtype=str)
    assert len(m) == len(saidas) == res["lidas"] - len(res["puladas"]) - res["repetidas"] == 36
    assert m.classe.value_counts().to_dict() == {"ferrugem_comum": 15, "helmintosporiose": 11, "cercosporiose": 10}
    assert {"train/Corn rust leaf/Foto (1).JPG", "train/Corn rust leaf/g.png", "train/Corn rust leaf/r.png",
            "train/Corn leaf blight/c.jpeg"} <= set(m.origem)
    assert all(a.startswith(f"{p}/{c}/") for a, p, c in zip(m.arquivo, m.particao, m.classe))
    hashes = [int(h, 16) for h in m.dhash]
    assert all(distancia(a, b) > 4 for a, b in itertools.combinations(hashes, 2))


def test_prepara_campo_idempotente(tmp_path, plantdoc_falso):
    preparar_campo(plantdoc_falso, tmp_path / "c")
    antes = arquivos(tmp_path / "c")
    preparar_campo(plantdoc_falso, tmp_path / "c")
    assert arquivos(tmp_path / "c") == antes


def test_fonte_tem_atribuicao(tmp_path, plantdoc_falso):
    preparar_campo(plantdoc_falso, tmp_path / "c")
    texto = (tmp_path / "c/FONTE.md").read_text(encoding="utf-8")
    assert "PlantDoc" in texto and "CC BY 4.0" in texto


def repo_plantdoc_falso(raiz):
    """Repositório git local (sem rede) com pastas do PlantDoc e um nome com "?", que só existe dentro do git."""
    def git(*args, entrada=None):
        return subprocess.run(["git", "-C", str(raiz), "-c", "core.protectNTFS=false", *args], input=entrada,
                              check=True, capture_output=True).stdout

    raiz.mkdir()
    git("init", "-q")
    for caminho, dados in {f"train/{RUST}/a.jpg": b"ferrugem", f"test/{BLIGHT}/b.jpg": b"mancha",
                           f"train/{GRAY}/c.jpeg?itok=x.jpg": b"cinza", "train/Tomato leaf/t.jpg": b"tomate"}.items():
        oid = git("hash-object", "-w", "--stdin", entrada=dados).decode().strip()
        git("update-index", "--add", "--cacheinfo", f"100644,{oid},{caminho}")
    git("-c", "user.name=teste", "-c", "user.email=teste@exemplo.invalid", "commit", "-q", "-m", "fotos")
    git("config", "uploadpack.allowFilter", "true")
    git("config", "uploadpack.allowAnySHA1InWant", "true")
    return raiz


def test_baixar_extrai_do_git_sem_checkout(tmp_path):
    origem = repo_plantdoc_falso(tmp_path / "origem")
    destino = baixar_plantdoc(tmp_path / "PlantDoc", repo=origem.as_uri())
    assert (destino / f"train/{RUST}/a.jpg").read_bytes() == b"ferrugem"
    assert (destino / f"test/{BLIGHT}/b.jpg").read_bytes() == b"mancha"
    assert (destino / f"train/{GRAY}/c.jpeg_itok=x.jpg").read_bytes() == b"cinza"  # "?" não existe no Windows
    assert not (destino / "train/Tomato leaf").exists()


def test_baixar_nao_chama_o_git_se_ja_baixado(tmp_path, monkeypatch):
    origem = repo_plantdoc_falso(tmp_path / "origem")
    baixar_plantdoc(tmp_path / "PlantDoc", repo=origem.as_uri())
    monkeypatch.setattr(prepare_campo.subprocess, "run", lambda *a, **k: pytest.fail("não devia chamar o git"))
    assert baixar_plantdoc(tmp_path / "PlantDoc", repo=origem.as_uri()) == tmp_path / "PlantDoc"
