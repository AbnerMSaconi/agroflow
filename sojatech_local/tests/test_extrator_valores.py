import pytest

from agroflow.invoices import local_extractor as le


@pytest.mark.parametrize("texto,esperado", [
    ("657,30", 657.30),
    ("1.234,56", 1234.56),
    ("12 345,60", 12345.60),
    ("657.30", 657.30),  # OCR trocou a vírgula por ponto
])
def test_valor_float(texto, esperado):
    assert le.valor_float(texto) == pytest.approx(esperado)


def test_re_valor_aceita_ponto_do_ocr():
    assert le.RE_VALOR.search("Valor R$ 657.30").group() == "657.30"
    assert le.RE_VALOR.search("Valor R$ 1.234,56").group() == "1.234,56"


@pytest.mark.parametrize("rotulo", [
    "VALOR TOTAL DA NOTA",
    "V. TOTAL NF-e",
    "VALOR TOTAL DA NF-e",
    "VALOR TOTAL DANF-e",  # OCR junta "DA" e "NF-e"
])
def test_r_total_reconhece_os_rotulos(rotulo):
    assert le.R_TOTAL.search(rotulo)


@pytest.mark.parametrize("rotulo", ["VALOR TOTAL DOS PRODUTOS", "VALOR TOTAL DO IPI", "V. TOTAL TRIBUTOS"])
def test_r_total_ignora_outros_totais(rotulo):
    assert not le.R_TOTAL.search(rotulo)
