"""Conjuntos: hash perceptual, divisão estratificada, manifestos e nomes gravados."""
from pathlib import Path

from PIL import Image

from agroflow import config
from agroflow.leaves.conjuntos import (Item, dhash, distancia, dividir_estratificado, escrever_manifesto,
                                       indices_unicos, itens, ler_nome_folha, nome_folha)


def test_dhash_quase_igual_para_copia_recomprimida(tmp_path, fazer_imagem):
    a = Image.open(fazer_imagem(tmp_path / "a.png", 1, (200, 150)))
    a.convert("RGB").save(tmp_path / "b.jpg", quality=60)
    assert distancia(dhash(a), dhash(Image.open(tmp_path / "b.jpg"))) <= 4


def test_dhash_distante_para_fotos_diferentes(tmp_path, fazer_imagem):
    a, b = (Image.open(fazer_imagem(tmp_path / f"{s}.png", s, (200, 150))) for s in (1, 2))
    assert distancia(dhash(a), dhash(b)) > 4


def test_indices_unicos_mantem_o_primeiro():
    assert indices_unicos([0b0, 0b1, 2**64 - 1, 0b11]) == [0, 2]


def test_indices_unicos_limite_de_4_bits():
    # 0b1111 está a 4 bits de 0 (repetida); 0b11111 está a 5 (fica)
    assert indices_unicos([0, 0b1111, 0b11111]) == [0, 2]


def test_divisao_estratificada():
    chaves = [(f"a{i:03d}", "cercosporiose") for i in range(68)] + [(f"b{i:03d}", "helmintosporiose") for i in range(192)]
    d = dividir_estratificado(chaves)
    conta = lambda c, p: sum(1 for k, cl in chaves if cl == c and d[k] == p)  # noqa: E731
    assert [conta("cercosporiose", p) for p in ("treino", "val", "teste")] == [34, 10, 24]
    assert [conta("helmintosporiose", p) for p in ("treino", "val", "teste")] == [96, 29, 67]
    assert dividir_estratificado(chaves) == d and dividir_estratificado(chaves, seed=7) != d


def test_nome_folha_ida_e_volta():
    item = Item(Path("x/ferrugem_comum_campo_001.jpg"), "ferrugem_comum", "campo", "teste")
    assert nome_folha(item) == "campo/teste/ferrugem_comum/ferrugem_comum_campo_001.jpg"
    assert ler_nome_folha(nome_folha(item)) == ("campo", "teste", "ferrugem_comum")
    assert ler_nome_folha("demo_folha.jpg") is None and ler_nome_folha("cercosporiose/x.jpg") is None


def test_manifesto_ordenado_e_lido_de_volta(tmp_path, monkeypatch):
    escrever_manifesto(tmp_path / "manifesto_lab.csv", [
        dict(arquivo="train/saudavel/s_1.jpg", classe="saudavel", particao="val"),
        dict(arquivo="test/cercosporiose/c_0.jpg", classe="cercosporiose", particao="teste"),
        dict(arquivo="train/saudavel/s_0.jpg", classe="saudavel", particao="treino")])
    assert (tmp_path / "manifesto_lab.csv").read_bytes() == (
        b"arquivo,classe,particao\n"
        b"test/cercosporiose/c_0.jpg,cercosporiose,teste\n"
        b"train/saudavel/s_0.jpg,saudavel,treino\n"
        b"train/saudavel/s_1.jpg,saudavel,val\n")
    escrever_manifesto(tmp_path / "campo/manifesto.csv", [
        dict(arquivo="teste/ferrugem_comum/f_000.jpg", classe="ferrugem_comum", particao="teste")])
    monkeypatch.setattr(config, "LEAVES_DIR", tmp_path)
    monkeypatch.setattr(config, "MANIFESTO_LAB", tmp_path / "manifesto_lab.csv")
    monkeypatch.setattr(config, "CAMPO_DIR", tmp_path / "campo")
    monkeypatch.setattr(config, "MANIFESTO_CAMPO", tmp_path / "campo/manifesto.csv")
    assert itens("lab", "val") == [Item(tmp_path / "train/saudavel/s_1.jpg", "saudavel", "lab", "val")]
    assert itens("campo", "teste") == [
        Item(tmp_path / "campo/teste/ferrugem_comum/f_000.jpg", "ferrugem_comum", "campo", "teste")]
