"""prepare_leaves: teste de laboratório estável, treino ampliado e validação fixa."""
from pathlib import Path

import pandas as pd
import pytest

from prepare_leaves import CLASSES as PASTAS_PLANTVILLAGE, preparar_lab


@pytest.fixture
def origem_falsa(tmp_path, fazer_imagem):
    """As 4 pastas de milho do PlantVillage, com 40 fotos cada (extensões .JPG e .jpg, como no original)."""
    origem = tmp_path / "plantvillage"
    for k, pasta in enumerate(PASTAS_PLANTVILLAGE):
        for i in range(40):
            nome = f"foto ({i}).JPG" if i % 2 else f"foto_{i}.jpg"
            fazer_imagem(origem / pasta / nome, 1000 * k + i)
    return origem


def arquivos_e_bytes(pasta: Path) -> dict[str, bytes]:
    return {p.relative_to(pasta).as_posix(): p.read_bytes() for p in sorted(pasta.rglob("*.jpg"))}


def test_teste_e_inicio_do_treino_estaveis(tmp_path, origem_falsa):
    preparar_lab(origem_falsa, tmp_path / "d1", treino=10, teste=5)
    preparar_lab(origem_falsa, tmp_path / "d2", treino=20, teste=5)
    assert len(arquivos_e_bytes(tmp_path / "d1/test")) == 20
    assert arquivos_e_bytes(tmp_path / "d1/test") == arquivos_e_bytes(tmp_path / "d2/test")
    assert arquivos_e_bytes(tmp_path / "d1/train").items() <= arquivos_e_bytes(tmp_path / "d2/train").items()


def test_validacao_fixa_no_manifesto(tmp_path, origem_falsa):
    preparar_lab(origem_falsa, tmp_path / "d", treino=20, teste=5)
    primeiro = (tmp_path / "d/manifesto_lab.csv").read_bytes()
    preparar_lab(origem_falsa, tmp_path / "d", treino=20, teste=5)
    assert (tmp_path / "d/manifesto_lab.csv").read_bytes() == primeiro
    m = pd.read_csv(tmp_path / "d/manifesto_lab.csv")
    assert m.particao.value_counts().to_dict() == {"treino": 68, "teste": 20, "val": 12}
    val = m[m.particao == "val"]
    assert val.groupby("classe").size().to_dict() == {
        "cercosporiose": 3, "ferrugem_comum": 3, "helmintosporiose": 3, "saudavel": 3}
    assert val.arquivo.str.startswith("train/").all()
    assert all((tmp_path / "d" / a).is_file() for a in m.arquivo)


def test_nao_apaga_campo(tmp_path, origem_falsa):
    (tmp_path / "d/campo").mkdir(parents=True)
    (tmp_path / "d/campo/x.txt").write_text("fica")
    preparar_lab(origem_falsa, tmp_path / "d", treino=10, teste=5)
    assert (tmp_path / "d/campo/x.txt").exists()
