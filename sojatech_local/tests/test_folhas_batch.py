"""Pipeline e lote de folhas: tipo gravado por modelo, partições e nomes."""
import pytest

from agroflow import config, leaves, pipeline, storage
from agroflow.leaves.conjuntos import ler_nome_folha
from agroflow.storage import Row


def test_tipo_por_modelo(tmp_path, monkeypatch, fazer_imagem):
    monkeypatch.setattr(pipeline.leaves, "classify", lambda p, modelo="produto": ("saudavel", 0.9, {}))
    f = fazer_imagem(tmp_path / "f.jpg", 1)
    assert pipeline.process_leaf(f, "x", baseline=False, classificador=True)[0].tipo == "folha_classificador"
    assert (pipeline.process_leaf(f, "x", baseline=False, classificador=True, modelo="lab")[0].tipo
            == "folha_classificador_lab")


def test_itens_folhas_sem_treino(manifestos_falsos):
    import run_batch
    ordem = [(i.conjunto, i.particao) for i in run_batch.itens_folhas()]
    assert ordem == sorted(ordem, key=[("lab", "val"), ("lab", "teste"), ("campo", "val"), ("campo", "teste")].index)
    assert "treino" not in {p for _, p in ordem}


@pytest.fixture
def lote_falso(tmp_path, monkeypatch, manifestos_falsos):
    """Banco SQLite de verdade numa pasta temporária; modelos falsos (rápidos)."""
    monkeypatch.setattr(config, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(config, "RESULTS_DB", tmp_path / "results" / "agroflow.db")
    monkeypatch.setattr(leaves, "baseline", lambda p, k=5: [("corn", 0.5)])
    monkeypatch.setattr(leaves, "classify", lambda p, modelo="produto": ("saudavel", 0.9, {}))
    monkeypatch.setattr(leaves, "classificador_disponivel", lambda modelo="produto": True)
    import run_batch
    return run_batch


def test_lote_folhas_por_conjunto_e_particao(lote_falso):
    assert lote_falso.lote_folhas() == 28  # val + teste: lab 2×4×2, campo 2×3×2
    df = storage.load_dataframe()
    assert df.groupby("tipo").size().to_dict() == {
        "folha_baseline": 14, "folha_classificador": 28, "folha_classificador_lab": 28}
    partes = df.arquivo.map(ler_nome_folha)
    assert partes.notna().all()
    assert {p[1] for p in partes[df.tipo == "folha_baseline"]} == {"teste"}
    assert {(p[0], p[1]) for p in partes} == {("lab", "val"), ("lab", "teste"), ("campo", "val"), ("campo", "teste")}


def test_lote_folhas_sem_lab_nao_apaga_o_lab(lote_falso):
    storage.save([Row("lab/teste/saudavel/antigo.jpg", "folha_classificador_lab", "classe", "saudavel", 0.5)])
    lote_falso.lote_folhas(lab=False)
    df = storage.load_dataframe()
    assert list(df[df.tipo == "folha_classificador_lab"].arquivo) == ["lab/teste/saudavel/antigo.jpg"]
    assert (df.tipo == "folha_classificador").sum() == 28
