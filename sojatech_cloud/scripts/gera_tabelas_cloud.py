"""Gera as tabelas LaTeX do Google Cloud do paper a partir dos CSVs dos scripts.

Entradas (todas opcionais):
  sojatech_cloud/results/docai_holdout_s9.csv   scripts/docai_minimo.py
  sojatech_cloud/results/vision_test.csv        scripts/vision_minimo.py (laboratório)
  sojatech_cloud/results/vision_teste.csv       scripts/vision_minimo.py --pasta .../campo/teste
  sojatech_local/results/local_holdout_s9.csv   sojatech_local/scripts/avalia_pasta.py
Saídas em report/tabelas/: cloud_docai.tex, cloud_vision.tex, cloud_vs_local.tex.

Sem um CSV, a tabela sai com "---" e a legenda marca "(pendente)": o paper compila antes e depois
da execução, e nenhum número é inventado.

Uso: python scripts/gera_tabelas_cloud.py
"""
import csv
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REPO = RAIZ.parent
TABELAS = REPO / "report" / "tabelas"
CAMPOS = [("cnpj_emitente", "CNPJ do emitente"), ("numero", "Número"),
          ("data_emissao", "Data de emissão"), ("valor_total", "Valor total")]
VAZIO = "---"


def ler(caminho: Path):
    if not caminho.is_file():
        return None
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}" + r"\%" if b else VAZIO


def num(x, casas=3) -> str:
    return f"{x:.{casas}f}" if x is not None else VAZIO  # ponto decimal, como as tabelas do evaluate.py


def media(v):
    return sum(v) / len(v) if v else None


def resumo_notas(linhas):
    """{campo: (n, acertos, conf_certos, conf_errados)} e (notas inteiras, notas)."""
    por_campo = {}
    for campo, _ in CAMPOS:
        ls = [l for l in linhas if l["campo"] == campo]
        certos = [float(l["confidence"]) for l in ls if l["acertou"] == "1"]
        errados = [float(l["confidence"]) for l in ls if l["acertou"] != "1"]
        por_campo[campo] = (len(ls), len(certos), media(certos), media(errados))
    notas = {}
    for l in linhas:
        notas.setdefault(l["arquivo"], []).append(l["acertou"] == "1")
    return por_campo, (sum(all(v) for v in notas.values()), len(notas))


def tabela(legenda, rotulo, colunas, linhas, formato):
    corpo = "\n".join(" & ".join(l) + r" \\" for l in linhas)
    return (f"\\begin{{table}}[H]\n\\centering\\small\n\\begin{{tabular}}{{{formato}}}\n\\toprule\n"
            f"{' & '.join(colunas)} \\\\\n\\midrule\n{corpo}\n\\bottomrule\n\\end{{tabular}}\n"
            f"\\caption{{{legenda}}}\n\\label{{{rotulo}}}\n\\end{{table}}\n")


def tex_docai(linhas):
    pend = "" if linhas else " Resultados pendentes."
    if linhas:
        por_campo, (inteiras, notas) = resumo_notas(linhas)
        corpo = [[nome, f"{por_campo[c][1]}/{por_campo[c][0]}", pct(por_campo[c][1], por_campo[c][0]),
                  num(por_campo[c][2]), num(por_campo[c][3])] for c, nome in CAMPOS]
        corpo.append(["Nota inteira", f"{inteiras}/{notas}", pct(inteiras, notas), VAZIO, VAZIO])
    else:
        corpo = [[nome] + [VAZIO] * 4 for _, nome in CAMPOS] + [["Nota inteira"] + [VAZIO] * 4]
    return tabela("Document AI (Invoice Parser) no \\emph{holdout}: acerto e confidence médio por campo "
                  f"(``---'' em confidence errados: nenhum erro).{pend}", "tab:cloud-docai",
                  ["Campo", "Acertos", "Acerto", "Conf.\\ certos", "Conf.\\ errados"], corpo, "lrrrr")


def resumo_vision(linhas):
    """(imagens, nomeia praga, menciona planta, score top-1 médio) por imagem."""
    por_img = {}
    for l in linhas:
        d = por_img.setdefault((l["classe"], l["arquivo"]), {"praga": 0, "planta": 0, "top1": 0.0})
        d["praga"] |= int(l["praga"])
        d["planta"] |= int(l["planta"])
        if l["rank"] == "1":
            d["top1"] = float(l["score"])
    n = len(por_img)
    return (n, sum(d["praga"] for d in por_img.values()), sum(d["planta"] for d in por_img.values()),
            media([d["top1"] for d in por_img.values()]))


def linha_vision(conjunto, servico, r):
    if r is None:
        return [conjunto, servico] + [VAZIO] * 4
    n, praga, planta, top1 = r
    return [conjunto, servico, str(n), pct(praga, n), pct(planta, n), num(top1)]


def tex_vision(lab, campo):
    metricas = REPO / "sojatech_local" / "results" / "metricas.json"
    local = {}
    if metricas.is_file():
        m = json.loads(metricas.read_text(encoding="utf-8"))
        for chave, nome in (("baseline", "lab"), ("baseline_campo", "campo")):
            b = m.get(chave)
            if b:
                n = b["n_imagens"]
                local[nome] = (n, round(b["frac_identifica_praga"] * n), round(b["frac_menciona_planta"] * n),
                               b["score_top1_medio"])
    cloud = {"lab": resumo_vision(lab) if lab else None, "campo": resumo_vision(campo) if campo else None}
    corpo = [linha_vision("Laboratório", "Vision API", cloud["lab"]),
             linha_vision("Laboratório", "Local (ResNet-50)", local.get("lab")),
             linha_vision("Campo", "Vision API", cloud["campo"]),
             linha_vision("Campo", "Local (ResNet-50)", local.get("campo"))]
    pend = "" if (lab and campo) else " Resultados da Vision API pendentes."
    return tabela("Detecção de rótulos nas folhas: fração de imagens com rótulo que nomeia a praga e que "
                  f"menciona a planta, e score médio do rótulo top-1.{pend}", "tab:cloud-vision",
                  ["Conjunto", "Serviço", "Imagens", "Nomeia a praga", "Menciona a planta", "Score top-1"],
                  corpo, "llrrrr")


def tex_comparacao(cloud, local):
    def col(linhas):
        if not linhas:
            return None
        return resumo_notas(linhas)
    c, l = col(cloud), col(local)
    corpo = []
    for campo, nome in CAMPOS:
        corpo.append([nome, pct(l[0][campo][1], l[0][campo][0]) if l else VAZIO,
                      pct(c[0][campo][1], c[0][campo][0]) if c else VAZIO])
    corpo.append(["Nota inteira", pct(*l[1]) if l else VAZIO, pct(*c[1]) if c else VAZIO])
    faltam = [n for n, d in (("local", l), ("Document AI", c)) if not d]
    pend = f" Pendente: {', '.join(faltam)}." if faltam else ""
    return tabela("Acerto no \\emph{holdout} (mesmas 40 notas): extrator local e Document AI."
                  f"{pend}", "tab:cloud-vs-local", ["Campo", "Local", "Document AI"], corpo, "lrr")


def main():
    cloud = ler(RAIZ / "results" / "docai_holdout_s9.csv")
    local = ler(REPO / "sojatech_local" / "results" / "local_holdout_s9.csv")
    lab = ler(RAIZ / "results" / "vision_test.csv")
    campo = ler(RAIZ / "results" / "vision_teste.csv")
    TABELAS.mkdir(parents=True, exist_ok=True)
    saidas = {"cloud_docai.tex": tex_docai(cloud), "cloud_vision.tex": tex_vision(lab, campo),
              "cloud_vs_local.tex": tex_comparacao(cloud, local)}
    for nome, texto in saidas.items():
        (TABELAS / nome).write_text(texto, encoding="utf-8")
    ok = lambda x: "dados" if x else "pendente"
    print(f"cloud_docai: {ok(cloud)} | cloud_vision: lab {ok(lab)}, campo {ok(campo)} | "
          f"cloud_vs_local: local {ok(local)}, Document AI {ok(cloud)}")
    print(f"tabelas em {TABELAS}")


if __name__ == "__main__":
    sys.exit(main())
