"""Fase 4: lê a tabela de resultados + gabaritos e gera métricas, gráficos e tabelas.

Saídas:
  results/metricas.json          números para o relatório
  results/resumo.md              resumo legível
  results/figures/*.png          gráficos (copiados para ../report/figuras)
  ../report/tabelas/*.tex        tabelas prontas para \\input no LaTeX

A tese do trabalho: confidence do modelo e acerto medido são números diferentes.

Folhas: cada modelo (produto = lab+campo; lab = só laboratório) é medido no teste
de laboratório e no de campo. O limiar de cada modelo sai da validação (campo para
o produto, laboratório para o modelo lab); o teste nunca escolhe nada.

Uso: python scripts/evaluate.py
"""
import json
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import classification_report  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config, storage  # noqa: E402
from agroflow.leaves.conjuntos import CLASSES, ler_nome_folha  # noqa: E402
from agroflow.leaves.local_models import sha256_arquivo  # noqa: E402

FIG = config.RESULTS / "figures"
TAB = config.REPORT / "tabelas"
CAMPOS = ["cnpj_emitente", "numero", "data_emissao", "valor_total"]
# rótulo da linha de base que "identifica a praga" de verdade
TERMOS_PRAGA = ["rust", "blight", "spot", "fung", "disease", "mildew", "mold", "lesion", "pest"]
TERMOS_PLANTA = ["leaf", "plant", "corn", "maize", "ear", "vegetation", "grass", "flora", "botany"]

plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9})


def salvar(fig, nome):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / nome)
    plt.close(fig)


def latex_tabela(df: pd.DataFrame, nome, legenda, rotulo):
    TAB.mkdir(parents=True, exist_ok=True)
    corpo = df.to_latex(index=False, escape=True, float_format="%.3f", na_rep="--")
    (TAB / f"{nome}.tex").write_text(
        "\\begin{table}[ht]\n\\centering\n\\small\n" + corpo
        + f"\\caption{{{legenda}}}\n\\label{{{rotulo}}}\n\\end{{table}}\n", encoding="utf-8")


def analise_limiar(conf: np.ndarray, certo: np.ndarray):
    """Para cada limiar: quanto passa direto e quantos erros seriam barrados."""
    linhas = []
    for t in np.round(np.arange(0.0, 1.0, 0.05), 2):
        aceito = conf >= t
        linhas.append(dict(limiar=t, aceitos=aceito.mean(),
                           precisao_aceitos=certo[aceito].mean() if aceito.any() else np.nan,
                           erros_barrados=int((~certo & ~aceito).sum()),
                           erros_passaram=int((~certo & aceito).sum()),
                           acertos_barrados=int((certo & ~aceito).sum())))
    df = pd.DataFrame(linhas)
    ok = df[df.precisao_aceitos >= 0.98]
    escolhido = float(ok.limiar.min()) if len(ok) else float(df.loc[df.precisao_aceitos.idxmax(), "limiar"])
    return df, escolhido


def ece(conf, certo, bins=10):
    """Expected Calibration Error: distância média entre confidence e acerto."""
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for a, b in zip(edges[:-1], edges[1:]):
        m = (conf > a) & (conf <= b)
        if m.any():
            total += m.mean() * abs(conf[m].mean() - certo[m].mean())
    return float(total)


def grafico_limiar(df, escolhido, titulo, nome):
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    ax.plot(df.limiar, df.aceitos, label="fração aceita automaticamente")
    ax.plot(df.limiar, df.precisao_aceitos, label="precisão entre os aceitos")
    ax.axvline(escolhido, ls="--", c="gray", lw=0.8)
    ax.text(escolhido + 0.01, 0.05, f"limiar {escolhido:.2f}", fontsize=8, color="gray")
    ax.set(xlabel="limiar de confidence", ylim=(0, 1.02), title=titulo)
    ax.legend(fontsize=7, loc="lower left")
    salvar(fig, nome)


def avalia_notas(df, gabarito, prefixo="", sufixo="", titulo="Notas fiscais"):
    """prefixo: como o arquivo foi gravado na tabela ("teste/"); sufixo: nome das saídas."""
    if not gabarito.exists():
        return None
    gab = pd.read_csv(gabarito, dtype=str)
    notas = df[df.tipo == "nota"]
    fonte = notas[notas.campo == "_fonte"].set_index("arquivo").valor
    pred = notas[notas.campo.isin(CAMPOS)]
    linhas = []
    for _, g in gab.iterrows():
        for c in CAMPOS:
            p = pred[(pred.arquivo == prefixo + g.arquivo) & (pred.campo == c)]
            valor = p.valor.iloc[0] if len(p) else None
            linhas.append(dict(arquivo=g.arquivo, campo=c, esperado=g[c], extraido=valor,
                               confidence=float(p.confidence.iloc[0]) if len(p) else 0.0,
                               certo=valor == g[c], escaneada=g.escaneada == "1", layout=g.layout,
                               fonte=fonte.get(prefixo + g.arquivo)))
    d = pd.DataFrame(linhas)
    if d.extraido.isna().all():
        return None
    d.to_csv(config.RESULTS / f"notas_comparacao{sufixo}.csv", index=False)

    por_campo = d.groupby("campo").agg(acerto=("certo", "mean"),
                                       conf_media=("confidence", "mean")).reindex(CAMPOS)
    conf_cert = d.groupby(["campo", "certo"]).confidence.mean().unstack()
    por_campo["conf_certos"] = conf_cert.get(True)
    por_campo["conf_errados"] = conf_cert.get(False)
    nota_inteira = d.groupby("arquivo").certo.all()
    por_tipo = d.groupby("escaneada").certo.mean().rename({False: "digital", True: "escaneada"})
    por_layout = d.groupby("layout").certo.mean()
    limiar_df, limiar = analise_limiar(d.confidence.values, d.certo.values)

    tab = por_campo.reset_index()
    tab.columns = ["Campo", "Acerto", "Conf. média", "Conf. (certos)", "Conf. (errados)"]
    latex_tabela(tab, f"notas_por_campo{sufixo}",
                 f"{titulo}: acerto medido vs. confidence por campo.", f"tab:notas-campo{sufixo.replace('_', '-')}")

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    x = np.arange(len(CAMPOS))
    ax.bar(x - 0.2, por_campo.acerto, 0.4, label="acerto medido")
    ax.bar(x + 0.2, por_campo.conf_media, 0.4, label="confidence médio")
    ax.set_xticks(x, CAMPOS)
    ax.set(ylim=(0, 1.05), title=f"{titulo}: acerto vs. confidence")
    ax.legend(fontsize=7)
    salvar(fig, f"notas_acerto_vs_confidence{sufixo}.png")

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    ax.hist([d[d.certo].confidence, d[~d.certo].confidence], bins=np.linspace(0, 1, 21),
            label=["campos certos", "campos errados"], stacked=True)
    ax.set(xlabel="confidence", ylabel="campos", title=f"Distribuição do confidence ({titulo.lower()})")
    ax.legend(fontsize=7)
    salvar(fig, f"notas_hist_confidence{sufixo}.png")
    grafico_limiar(limiar_df, limiar, f"{titulo}: efeito do limiar", f"notas_limiar{sufixo}.png")

    erros = d[~d.certo][["arquivo", "campo", "esperado", "extraido", "confidence", "fonte"]]
    return dict(
        n_notas=int(gab.shape[0]), acerto_campos=float(d.certo.mean()),
        acerto_nota_inteira=float(nota_inteira.mean()),
        por_campo=por_campo.round(3).to_dict(orient="index"),
        por_tipo=por_tipo.round(3).to_dict(), por_layout=por_layout.round(3).to_dict(),
        conf_media_certos=float(d[d.certo].confidence.mean()),
        conf_media_errados=float(d[~d.certo].confidence.mean()) if (~d.certo).any() else None,
        ece=ece(d.confidence.values, d.certo.values.astype(float)),
        limiar_escolhido=limiar,
        limiar_tabela=limiar_df.round(3).to_dict(orient="records"),
        erros=erros.to_dict(orient="records"),
    )


def folhas(df, tipo):
    """Linhas de um tipo de folha com nome <conjunto>/<particao>/<classe>/<arquivo>, mais essas colunas.

    Nomes fora desse formato (a demo pelo bucket, lotes antigos) não têm gabarito e saem.
    """
    f = df[df.tipo == tipo]
    if tipo.startswith("folha_classificador"):
        f = f[f.campo == "classe"]
    partes = f.arquivo.map(ler_nome_folha)
    f = f[partes.notna()].copy()
    partes = list(partes[partes.notna()])
    f["conjunto"] = [p[0] for p in partes]
    f["particao"] = [p[1] for p in partes]
    f["real"] = [p[2] for p in partes]
    return f


def limiar_validacao(f, conjunto):
    """Limiar escolhido na validação do conjunto, com o critério de analise_limiar. None sem validação."""
    v = f[(f.conjunto == conjunto) & (f.particao == "val")]
    if v.empty:
        return None
    return analise_limiar(v.confidence.values.astype(float), (v.valor == v.real).values)[1]


def avalia_baseline(df, conjunto, sufixo="", titulo="Linha de base"):
    f = folhas(df, "folha_baseline")
    b = f[(f.conjunto == conjunto) & (f.particao == "teste")].copy()
    if b.empty:
        return None
    b["praga"] = b.valor.str.lower().str.contains("|".join(TERMOS_PRAGA))
    b["planta"] = b.valor.str.lower().str.contains("|".join(TERMOS_PLANTA))
    por_img = b.groupby("arquivo").agg(algum_praga=("praga", "any"), algum_planta=("planta", "any"),
                                       score_top1=("confidence", "max"))
    top1 = b[b.campo == "rotulo_1"]
    freq = top1.valor.value_counts().head(10)

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    freq[::-1].plot.barh(ax=ax)
    ax.set(xlabel="imagens de teste", title=f"{titulo}: rótulo top-1 mais frequente")
    salvar(fig, f"baseline_rotulos{sufixo}.png")

    tab = pd.DataFrame({"Rótulo top-1": freq.index, "Imagens": freq.values,
                        "Score médio": top1.groupby("valor").confidence.mean().reindex(freq.index).values})
    latex_tabela(tab, f"baseline_rotulos{sufixo}", f"{titulo}: rótulos genéricos mais devolvidos.",
                 f"tab:baseline{sufixo.replace('_', '-')}")
    return dict(n_imagens=int(por_img.shape[0]),
                frac_identifica_praga=float(por_img.algum_praga.mean()),
                frac_menciona_planta=float(por_img.algum_planta.mean()),
                score_top1_medio=float(por_img.score_top1.mean()),
                top_rotulos=freq.to_dict())


def avalia_classificador(df, tipo, conjunto, limiar, sufixo="", titulo="Classificador de folhas", gravar=True):
    """Um modelo (tipo) no teste de um conjunto, com o limiar que veio da validação.

    As métricas por classe usam as classes presentes no teste (3 no campo, sem saudável);
    prever uma classe ausente conta como erro e aparece na matriz, que tem as 4 classes
    nas colunas. gravar=False não escreve figuras nem tabelas.
    """
    f = folhas(df, tipo)
    c = f[(f.conjunto == conjunto) & (f.particao == "teste")].copy()
    if c.empty:
        return None
    limiar = 0.0 if limiar is None else float(limiar)
    c["certo"] = c.valor == c.real
    classes = sorted(c.real.unique())
    rep = classification_report(c.real, c.valor, labels=classes, output_dict=True, zero_division=0)
    cm = pd.crosstab(c.real, c.valor).reindex(index=classes, columns=CLASSES, fill_value=0).values
    conf_cls = c.groupby("real").agg(conf_media=("confidence", "mean"), acerto=("certo", "mean"))
    conf, certo = c.confidence.values.astype(float), c.certo.values
    limiar_df, _ = analise_limiar(conf, certo)  # só descreve o efeito; o limiar não é escolhido aqui
    aceito = conf >= limiar

    if gravar:
        fig, ax = plt.subplots(figsize=(4.4, 3.8))
        ax.imshow(cm, cmap="Greens")
        for i in range(len(classes)):
            for j in range(len(CLASSES)):
                ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
        ax.set_xticks(range(len(CLASSES)), CLASSES, rotation=30, ha="right")
        ax.set_yticks(range(len(classes)), classes)
        ax.set(xlabel="previsto", ylabel="real", title=f"Matriz de confusão ({titulo.lower()})")
        salvar(fig, f"folhas_matriz_confusao{sufixo}.png")

        # diagrama de confiabilidade
        edges = np.linspace(0, 1, 11)
        mids, accs, ns = [], [], []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (c.confidence > a) & (c.confidence <= b)
            if m.any():
                mids.append(c.confidence[m].mean())
                accs.append(c.certo[m].mean())
                ns.append(int(m.sum()))
        fig, ax = plt.subplots(figsize=(4.2, 3.6))
        ax.plot([0, 1], [0, 1], ls="--", c="gray", lw=0.8, label="calibração perfeita")
        ax.scatter(mids, accs, s=[20 + n * 3 for n in ns], zorder=3, label="faixas de confidence")
        ax.set(xlabel="confidence médio da faixa", ylabel="acerto medido", xlim=(0, 1.02), ylim=(0, 1.02),
               title=f"Confidence vs. acerto ({titulo.lower()})")
        ax.legend(fontsize=7, loc="upper left")
        salvar(fig, f"folhas_calibracao{sufixo}.png")
        grafico_limiar(limiar_df, limiar, f"{titulo}: efeito do limiar", f"folhas_limiar{sufixo}.png")

        tab = pd.DataFrame([dict(Classe=k, Precisão=rep[k]["precision"], Recall=rep[k]["recall"],
                                 F1=rep[k]["f1-score"], **{"Conf. média": conf_cls.conf_media[k]})
                            for k in classes])
        latex_tabela(tab, f"folhas_por_classe{sufixo}", f"{titulo}: métricas por classe no conjunto de teste.",
                     f"tab:folhas-classe{sufixo.replace('_', '-')}")
    return dict(n_imagens=int(len(c)), acuracia=float(certo.mean()),
                f1_macro=float(rep["macro avg"]["f1-score"]),
                por_classe={k: {m: round(rep[k][m], 3) for m in ("precision", "recall", "f1-score")}
                            | {"conf_media": round(float(conf_cls.conf_media[k]), 3)} for k in classes},
                matriz_confusao=dict(reais=classes, previstas=CLASSES, valores=cm.tolist()),
                conf_media_certos=float(conf[certo].mean()) if certo.any() else None,
                conf_media_errados=float(conf[~certo].mean()) if (~certo).any() else None,
                ece=ece(conf, certo.astype(float)),
                limiar=limiar,
                com_limiar=dict(aceitos=float(aceito.mean()),
                                precisao_aceitos=float(certo[aceito].mean()) if aceito.any() else None,
                                erros_barrados=int((~certo & ~aceito).sum()),
                                erros_passaram=int((~certo & aceito).sum()),
                                acertos_barrados=int((certo & ~aceito).sum())),
                limiar_tabela=limiar_df.round(3).to_dict(orient="records"))


def tabela_lab_vs_campo(m):
    """Uma linha por modelo × teste: quanto cada modelo cai do laboratório para o campo."""
    lab = m.get("classificador_lab") or {}
    casos = [("lab+campo (produto)", "laboratório", m.get("classificador")),
             ("lab+campo (produto)", "campo", m.get("classificador_campo")),
             ("só laboratório", "laboratório", lab.get("lab")),
             ("só laboratório", "campo", lab.get("campo"))]
    linhas = []
    for modelo, teste, r in casos:
        if not r:
            continue
        cl = r["com_limiar"]
        linhas.append({"Modelo": modelo, "Teste": teste, "Limiar": r["limiar"], "Acurácia": r["acuracia"],
                       "F1 macro": r["f1_macro"], "Conf. dos erros": r["conf_media_errados"], "ECE": r["ece"],
                       "Erros barrados": f"{cl['erros_barrados']} de {cl['erros_barrados'] + cl['erros_passaram']}"})
    return pd.DataFrame(linhas)


def tabela_disputa(d):
    return pd.DataFrame([{"Rede": c["rede"] + (" (escolhida)" if c["rede"] == d["vencedora"] else ""),
                          "Parâmetros (M)": c["n_parametros"] / 1e6, "F1 val. campo": c["f1_val_campo"],
                          "F1 val. lab": c["f1_val_lab"], "Treino (min)": c["tempo_treino_s"] / 60}
                         for c in d["candidatas"]])


def tempos(df):
    """Tempo médio de processamento por item (ms), por tipo."""
    return {b: g.groupby("tipo").apply(lambda t: t.groupby("arquivo").duracao_ms.first().mean(),
                                       include_groups=False).round(1).to_dict()
            for b, g in df.groupby("backend")}


def resumo_md(m):
    L = ["# Resultados (gerado por scripts/evaluate.py)", ""] + resumo_backend(m)
    if k := m.get("custos"):
        L += ["# Tempo", "", f"- tempo médio por item (ms): {k['tempo_medio_ms_por_item']}", ""]
    return "\n".join(L)


def resumo_backend(m):
    L = []
    for chave, titulo in [("notas", "Notas fiscais — desenvolvimento"),
                          ("notas_teste", "Notas fiscais — teste separado")]:
        if not (n := m.get(chave)):
            continue
        L += [f"## {titulo}", "",
              f"- {n['n_notas']} notas; acerto por campo **{n['acerto_campos']:.1%}**, "
              f"nota inteira certa **{n['acerto_nota_inteira']:.1%}**",
              f"- digital vs. escaneada: {n['por_tipo']}",
              f"- por layout: {n['por_layout']}",
              f"- confidence médio: certos {n['conf_media_certos']:.3f} / errados {n['conf_media_errados']}",
              f"- ECE {n['ece']:.3f}; limiar sugerido {n['limiar_escolhido']}", "",
              "| campo | acerto | conf. média | conf. certos | conf. errados |", "|---|---|---|---|---|"]
        for c, v in n["por_campo"].items():
            L.append(f"| {c} | {v['acerto']:.3f} | {v['conf_media']:.3f} | {v['conf_certos']} | {v['conf_errados']} |")
        if n["erros"]:
            L += ["", f"Erros ({len(n['erros'])}):", "",
                  "| arquivo | campo | esperado | extraído | conf. | fonte |", "|---|---|---|---|---|---|"]
            L += [f"| {e['arquivo']} | {e['campo']} | {e['esperado']} | {e['extraido']} | {e['confidence']} | {e['fonte']} |"
                  for e in n["erros"]]
        L.append("")
    for chave, titulo in [("baseline", "Linha de base (rótulos genéricos), teste de laboratório"),
                          ("baseline_campo", "Linha de base (rótulos genéricos), teste de campo")]:
        if b := m.get(chave):
            L += [f"## {titulo}", "",
                  f"- {b['frac_identifica_praga']:.1%} das imagens têm algum rótulo que identifica a doença",
                  f"- {b['frac_menciona_planta']:.1%} têm algum rótulo de planta/folha",
                  f"- top-1 mais comuns: {b['top_rotulos']}", ""]
    lab = m.get("classificador_lab") or {}
    for titulo, c in [("Classificador do produto (lab+campo), teste de laboratório", m.get("classificador")),
                      ("Classificador do produto (lab+campo), teste de campo", m.get("classificador_campo")),
                      ("Modelo só de laboratório, teste de laboratório", lab.get("lab")),
                      ("Modelo só de laboratório, teste de campo", lab.get("campo"))]:
        if c:
            L += secao_classificador(titulo, c)
    if d := m.get("disputa"):
        L += ["## Disputa entre redes (validação; o teste não entra na escolha)", "",
              "| rede | parâmetros (M) | F1 val. campo | F1 val. lab | treino (min) |", "|---|---|---|---|---|"]
        L += [f"| {c['rede']}{' **(escolhida)**' if c['rede'] == d['vencedora'] else ''} "
              f"| {c['n_parametros'] / 1e6:.1f} | {c['f1_val_campo']:.3f} | {c['f1_val_lab']:.3f} "
              f"| {c['tempo_treino_s'] / 60:.1f} |" for c in d["candidatas"]]
        L.append("")
    return L


def secao_classificador(titulo, c):
    cl = c["com_limiar"]
    certos = "--" if c["conf_media_certos"] is None else f"{c['conf_media_certos']:.3f}"
    L = [f"## {titulo}", "",
         f"- {c['n_imagens']} imagens; acurácia **{c['acuracia']:.1%}**, F1 macro **{c['f1_macro']:.3f}**",
         f"- confidence médio: certos {certos} / errados {c['conf_media_errados']}",
         f"- ECE {c['ece']:.3f}",
         f"- limiar {c['limiar']} (escolhido na validação): aceita {cl['aceitos']:.1%}; erros barrados "
         f"{cl['erros_barrados']}, erros que passam {cl['erros_passaram']}, acertos barrados {cl['acertos_barrados']}",
         "", "| classe | precisão | recall | F1 | conf. média |", "|---|---|---|---|---|"]
    L += [f"| {k} | {v['precision']} | {v['recall']} | {v['f1-score']} | {v['conf_media']} |"
          for k, v in c["por_classe"].items()]
    return L + [""]


def carregar():
    df = storage.load_dataframe()
    df["processado_em"] = pd.to_datetime(df.processado_em, utc=True, format="ISO8601")
    df = df[df.backend == "local"].sort_values("processado_em")
    return df.drop_duplicates(["arquivo", "tipo", "campo"], keep="last")


def main():
    df = carregar()
    # folhas fora do formato <conjunto>/<particao>/<classe>/<arquivo> vieram da demo e não têm gabarito
    df = df[(df.tipo == "nota") | df.arquivo.map(lambda a: ler_nome_folha(a) is not None)]
    lim_produto = limiar_validacao(folhas(df, "folha_classificador"), "campo")
    lim_lab = limiar_validacao(folhas(df, "folha_classificador_lab"), "lab")  # o modelo lab não vê campo
    m = dict(
        notas=avalia_notas(df, config.GABARITO_NOTAS, "", "", "Notas (desenv.)"),
        notas_teste=avalia_notas(df, config.GABARITO_NOTAS_TESTE, "teste/", "_teste", "Notas (teste)"),
        baseline=avalia_baseline(df, "lab"),
        baseline_campo=avalia_baseline(df, "campo", "_campo", "Linha de base (campo)"),
        classificador=avalia_classificador(df, "folha_classificador", "lab", lim_produto, "",
                                           "Classificador, laboratório"),
        classificador_campo=avalia_classificador(df, "folha_classificador", "campo", lim_produto, "_campo",
                                                 "Classificador, campo"),
        classificador_lab=dict(
            lab=avalia_classificador(df, "folha_classificador_lab", "lab", lim_lab, gravar=False),
            campo=avalia_classificador(df, "folha_classificador_lab", "campo", lim_lab, "_lab_no_campo",
                                       "Modelo lab, campo")),
        disputa=json.loads(config.DISPUTA.read_text(encoding="utf-8")) if config.DISPUTA.exists() else None,
        modelo_avaliado_sha256=sha256_arquivo(config.LEAF_MODEL) if config.LEAF_MODEL.exists() else None,
        custos=dict(tempo_medio_ms_por_item=tempos(df)),
    )
    if m["classificador"]:
        m["classificador"]["limiar_escolhido"] = m["classificador"]["limiar"]  # as telas leem esta chave
    if len(t := tabela_lab_vs_campo(m)):
        latex_tabela(t, "folhas_lab_vs_campo", "Classificadores de folha nos testes de laboratório e de campo; "
                     "o limiar de cada modelo foi escolhido na validação.", "tab:folhas-lab-vs-campo")
    if m["disputa"]:
        latex_tabela(tabela_disputa(m["disputa"]), "disputa_redes", "Disputa entre redes: F1 macro na validação "
                     "(o teste não entra na escolha).", "tab:disputa-redes")
    (config.RESULTS / "metricas.json").write_text(json.dumps(m, indent=2, ensure_ascii=False, default=str),
                                                  encoding="utf-8")
    md = resumo_md(m)
    (config.RESULTS / "resumo.md").write_text(md, encoding="utf-8")
    dst = config.REPORT / "figuras"
    dst.mkdir(parents=True, exist_ok=True)
    for f in FIG.glob("*.png"):
        shutil.copy(f, dst / f.name)
    print(md)


if __name__ == "__main__":
    main()
