"""Testes do gerador de tabelas do Google Cloud (dados falsos, nenhuma chamada de rede)."""
import importlib.util
import unittest
from pathlib import Path

CAMINHO = Path(__file__).resolve().parent.parent / "scripts" / "gera_tabelas_cloud.py"
spec = importlib.util.spec_from_file_location("gera_tabelas_cloud", CAMINHO)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

CAMPOS = [c for c, _ in g.CAMPOS]


def notas(erros=None):
    """3 notas; `erros` = {(arquivo, campo): confidence} marca campos errados."""
    linhas = []
    for arq in ("nota_001.pdf", "nota_002.pdf", "nota_003.pdf"):
        for campo in CAMPOS:
            conf = (erros or {}).get((arq, campo))
            linhas.append(dict(arquivo=arq, layout="padrao", escaneada="0", campo=campo, esperado="x",
                               extraido="x" if conf is None else "y", confidence=str(0.9 if conf is None else conf),
                               acertou="1" if conf is None else "0", erro=""))
    return linhas


def vision(*imagens):
    """imagens = (classe, arquivo, [(rótulo, score, praga, planta), ...])."""
    linhas = []
    for classe, arq, rotulos in imagens:
        if not rotulos:
            linhas.append(dict(arquivo=arq, classe=classe, rank="0", rotulo="", score="0.0", praga="0", planta="0", erro="x"))
        for r, (rot, score, praga, planta) in enumerate(rotulos, 1):
            linhas.append(dict(arquivo=arq, classe=classe, rank=str(r), rotulo=rot, score=str(score),
                               praga=str(praga), planta=str(planta), erro=""))
    return linhas


class TestNotas(unittest.TestCase):
    def test_resumo_sem_erros(self):
        por_campo, (inteiras, n) = g.resumo_notas(notas())
        self.assertEqual((inteiras, n), (3, 3))
        self.assertEqual(por_campo["valor_total"][:2], (3, 3))
        self.assertAlmostEqual(por_campo["valor_total"][2], 0.9)
        self.assertIsNone(por_campo["valor_total"][3])

    def test_resumo_com_erro(self):
        por_campo, (inteiras, n) = g.resumo_notas(notas({("nota_002.pdf", "valor_total"): 0.3}))
        self.assertEqual((inteiras, n), (2, 3))
        self.assertEqual(por_campo["valor_total"][:2], (3, 2))
        self.assertAlmostEqual(por_campo["valor_total"][3], 0.3)
        self.assertEqual(por_campo["numero"][:2], (3, 3))

    def test_tabela_docai_com_dados(self):
        tex = g.tex_docai(notas({("nota_002.pdf", "valor_total"): 0.3}))
        self.assertIn(r"66.7\%", tex)  # 2 de 3 notas inteiras e 2 de 3 no valor total
        self.assertNotIn("pendentes", tex)
        self.assertIn(r"\label{tab:cloud-docai}", tex)

    def test_tabela_docai_pendente(self):
        tex = g.tex_docai(None)
        self.assertIn("Resultados pendentes", tex)
        self.assertGreaterEqual(tex.count("---"), 20)  # 5 linhas x 4 colunas sem número
        self.assertNotIn(r"\%", tex)

    def test_comparacao(self):
        tex = g.tex_comparacao(notas({("nota_001.pdf", "cnpj_emitente"): 0.5}), None)
        self.assertIn("Pendente: local.", tex)
        self.assertIn(r"66.7\%", tex)  # CNPJ 2 de 3 no Document AI
        self.assertIn(r"\label{tab:cloud-vs-local}", tex)

    def test_comparacao_completa_sem_pendencia(self):
        tex = g.tex_comparacao(notas(), notas())
        self.assertNotIn("Pendente", tex)
        self.assertIn(r"100.0\%", tex)


class TestVision(unittest.TestCase):
    def test_resumo_vision(self):
        linhas = vision(
            ("ferrugem_comum", "a.jpg", [("Rust", 0.8, 1, 0), ("Leaf", 0.9, 0, 1)]),
            ("saudavel", "b.jpg", [("Leaf", 0.95, 0, 1)]),
            ("saudavel", "c.jpg", []),  # falha na API: conta como imagem sem rótulo
        )
        n, praga, planta, top1 = g.resumo_vision(linhas)
        self.assertEqual((n, praga, planta), (3, 1, 2))
        self.assertAlmostEqual(top1, (0.8 + 0.95 + 0.0) / 3)

    def test_mesmo_nome_em_classes_diferentes_nao_colide(self):
        linhas = vision(("a", "x.jpg", [("Leaf", 0.5, 0, 1)]), ("b", "x.jpg", [("Leaf", 0.7, 0, 1)]))
        self.assertEqual(g.resumo_vision(linhas)[0], 2)

    def test_tabela_vision_pendente(self):
        tex = g.tex_vision(None, None)
        self.assertIn("pendentes", tex)
        self.assertIn(r"\label{tab:cloud-vision}", tex)

    def test_tabela_vision_com_dados(self):
        lab = vision(("saudavel", "a.jpg", [("Leaf", 0.9, 0, 1)]))
        tex = g.tex_vision(lab, lab)
        self.assertNotIn("pendentes", tex)
        self.assertIn("Vision API", tex)


class TestFormatos(unittest.TestCase):
    def test_pct_e_num(self):
        self.assertEqual(g.pct(1, 3), r"33.3\%")
        self.assertEqual(g.pct(0, 0), "---")
        self.assertEqual(g.num(0.5), "0.500")
        self.assertEqual(g.num(None), "---")


if __name__ == "__main__":
    unittest.main()
