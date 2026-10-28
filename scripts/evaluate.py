"""Fase 4: lê a tabela de resultados + gabaritos e gera métricas, gráficos e tabelas.

Saídas:
  results/metricas.json          números para o relatório
  results/resumo.md              resumo legível
  results/figures/*.png          gráficos (copiados para report/figuras)
  report/tabelas/*.tex           tabelas prontas para \\input no LaTeX

A tese do trabalho: confidence do modelo e acerto medido são números diferentes.

Uso: python scripts/evaluate.py [--volume-notas 2000 --volume-imagens 5000]
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import classification_report, confusion_matrix  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sojatech import config, storage  # noqa: E402

FIG = config.RESULTS / "figures"
TAB = config.ROOT / "report" / "tabelas"
CAMPOS = ["cnpj_emitente", "numero", "data_emissao", "valor_total"]
# rótulo da linha de base que "identifica a praga" de verdade
TERMOS_PRAGA = ["rust", "blight", "spot", "fung", "disease", "mildew", "mold", "lesion", "pest"]
TERMOS_PLANTA = ["leaf", "plant", "corn", "maize", "ear", "vegetation", "grass", "flora", "botany"]

# Preços de referência em USD. CONFERIR em cloud.google.com/pricing antes de citar.
PRECOS = {
    "docai_invoice_por_pagina": 10 / 1000,
    "vision_label_por_imagem": 1.50 / 1000,
    "vertex_treino_hora_no": 3.465,
    "vertex_endpoint_hora_no": 1.375,
}

plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9})


def salvar(fig, nome):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / nome)
    plt.close(fig)


def latex_tabela(df: pd.DataFrame, nome, legenda, rotulo):
    TAB.mkdir(parents=True, exist_ok=True)
    corpo = df.to_latex(index=False, escape=True, float_format="%.3f")
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


def avalia_notas(df):
    gab = pd.read_csv(config.GABARITO_NOTAS, dtype=str)
    notas = df[df.tipo == "nota"]
    fonte = notas[notas.campo == "_fonte"].set_index("arquivo").valor
    pred = notas[notas.campo.isin(CAMPOS)]
    linhas = []
    for _, g in gab.iterrows():
        for c in CAMPOS:
            p = pred[(pred.arquivo == g.arquivo) & (pred.campo == c)]
            valor = p.valor.iloc[0] if len(p) else None
            linhas.append(dict(arquivo=g.arquivo, campo=c, esperado=g[c], extraido=valor,
                               confidence=float(p.confidence.iloc[0]) if len(p) else 0.0,
                               certo=valor == g[c], escaneada=g.escaneada == "1", layout=g.layout,
                               fonte=fonte.get(g.arquivo)))
    d = pd.DataFrame(linhas)
    if d.extraido.isna().all():
        return None
    d.to_csv(config.RESULTS / "notas_comparacao.csv", index=False)

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
    latex_tabela(tab, "notas_por_campo", "Extração de notas: acerto medido vs. confidence por campo.",
                 "tab:notas-campo")

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    x = np.arange(len(CAMPOS))
    ax.bar(x - 0.2, por_campo.acerto, 0.4, label="acerto medido")
    ax.bar(x + 0.2, por_campo.conf_media, 0.4, label="confidence médio")
    ax.set_xticks(x, CAMPOS)
    ax.set(ylim=(0, 1.05), title="Notas fiscais: acerto vs. confidence por campo")
    ax.legend(fontsize=7)
    salvar(fig, "notas_acerto_vs_confidence.png")

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    ax.hist([d[d.certo].confidence, d[~d.certo].confidence], bins=np.linspace(0, 1, 21),
            label=["campos certos", "campos errados"], stacked=True)
    ax.set(xlabel="confidence", ylabel="campos", title="Distribuição do confidence (notas)")
    ax.legend(fontsize=7)
    salvar(fig, "notas_hist_confidence.png")
    grafico_limiar(limiar_df, limiar, "Notas: efeito do limiar", "notas_limiar.png")

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


def avalia_baseline(df):
    b = df[df.tipo == "folha_baseline"].copy()
    if b.empty:
        return None
    b["classe_real"] = b.arquivo.str.split("/").str[0]
    b["praga"] = b.valor.str.lower().str.contains("|".join(TERMOS_PRAGA))
    b["planta"] = b.valor.str.lower().str.contains("|".join(TERMOS_PLANTA))
    por_img = b.groupby("arquivo").agg(algum_praga=("praga", "any"), algum_planta=("planta", "any"),
                                       score_top1=("confidence", "max"))
    top1 = b[b.campo == "rotulo_1"]
    freq = top1.valor.value_counts().head(10)

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    freq[::-1].plot.barh(ax=ax)
    ax.set(xlabel="imagens de teste", title="Linha de base: rótulo top-1 mais frequente")
    salvar(fig, "baseline_rotulos.png")

    tab = pd.DataFrame({"Rótulo top-1": freq.index, "Imagens": freq.values,
                        "Score médio": top1.groupby("valor").confidence.mean().reindex(freq.index).values})
    latex_tabela(tab, "baseline_rotulos", "Linha de base: rótulos genéricos mais devolvidos.",
                 "tab:baseline")
    return dict(n_imagens=int(por_img.shape[0]),
                frac_identifica_praga=float(por_img.algum_praga.mean()),
                frac_menciona_planta=float(por_img.algum_planta.mean()),
                score_top1_medio=float(por_img.score_top1.mean()),
                top_rotulos=freq.to_dict())


def avalia_classificador(df):
    c = df[(df.tipo == "folha_classificador") & (df.campo == "classe")].copy()
    if c.empty:
        return None
    c["real"] = c.arquivo.str.split("/").str[0]
    c["certo"] = c.valor == c.real
    classes = sorted(c.real.unique())
    rep = classification_report(c.real, c.valor, labels=classes, output_dict=True, zero_division=0)
    cm = confusion_matrix(c.real, c.valor, labels=classes)
    conf_cls = c.groupby("real").agg(conf_media=("confidence", "mean"), acerto=("certo", "mean"))
    limiar_df, limiar = analise_limiar(c.confidence.values, c.certo.values)

    fig, ax = plt.subplots(figsize=(4.4, 3.8))
    ax.imshow(cm, cmap="Greens")
    for i in range(len(classes)):
        for j in range(len(classes)):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_xticks(range(len(classes)), classes, rotation=30, ha="right")
    ax.set_yticks(range(len(classes)), classes)
    ax.set(xlabel="previsto", ylabel="real", title="Matriz de confusão (teste)")
    salvar(fig, "folhas_matriz_confusao.png")

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
           title="Confidence vs. acerto (folhas)")
    ax.legend(fontsize=7, loc="upper left")
    salvar(fig, "folhas_calibracao.png")
    grafico_limiar(limiar_df, limiar, "Folhas: efeito do limiar", "folhas_limiar.png")

    tab = pd.DataFrame([dict(Classe=k, Precisão=rep[k]["precision"], Recall=rep[k]["recall"],
                             F1=rep[k]["f1-score"], **{"Conf. média": conf_cls.conf_media[k]})
                        for k in classes])
    latex_tabela(tab, "folhas_por_classe", "Classificador de folhas: métricas por classe no conjunto de teste.",
                 "tab:folhas-classe")
    return dict(n_imagens=int(len(c)), acuracia=float(rep["accuracy"]),
                f1_macro=float(rep["macro avg"]["f1-score"]),
                por_classe={k: {m: round(rep[k][m], 3) for m in ("precision", "recall", "f1-score")}
                            | {"conf_media": round(float(conf_cls.conf_media[k]), 3)} for k in classes},
                matriz_confusao=dict(classes=classes, valores=cm.tolist()),
                conf_media_certos=float(c[c.certo].confidence.mean()),
                conf_media_errados=float(c[~c.certo].confidence.mean()) if (~c.certo).any() else None,
                ece=ece(c.confidence.values, c.certo.values.astype(float)),
                limiar_escolhido=limiar, limiar_tabela=limiar_df.round(3).to_dict(orient="records"))


def custos(df, vol_notas, vol_imgs):
    tempo = df.groupby("tipo").apply(lambda g: g.groupby("arquivo").duracao_ms.first().mean(),
                                     include_groups=False).round(1).to_dict()
    mensal = dict(
        document_ai=vol_notas * PRECOS["docai_invoice_por_pagina"],
        vision_api=vol_imgs * PRECOS["vision_label_por_imagem"],
        vertex_endpoint_24x7=730 * PRECOS["vertex_endpoint_hora_no"],
    )
    tab = pd.DataFrame([
        ("Document AI (Invoice Parser)", f"{vol_notas} páginas/mês", mensal["document_ai"]),
        ("Vision API (label detection)", f"{vol_imgs} imagens/mês", mensal["vision_api"]),
        ("Vertex AI endpoint ligado 24x7", "1 nó, 730 h/mês", mensal["vertex_endpoint_24x7"]),
        ("Vertex AI treino AutoML (uma vez)", "8 horas de nó", 8 * PRECOS["vertex_treino_hora_no"]),
    ], columns=["Serviço", "Volume", "USD"])
    latex_tabela(tab, "custos", "Estimativa de custo mensal no GCP para o volume informado "
                 "(preços de referência; conferir a tabela oficial).", "tab:custos")
    return dict(tempo_medio_ms_por_item=tempo, precos_referencia=PRECOS,
                volume=dict(notas=vol_notas, imagens=vol_imgs), estimativa_mensal_usd=mensal)


def resumo_md(m):
    L = ["# Resultados (gerado por scripts/evaluate.py)", "", f"Backend: `{config.BACKEND}`", ""]
    if n := m.get("notas"):
        L += ["## Notas fiscais", "",
              f"- {n['n_notas']} notas; acerto por campo **{n['acerto_campos']:.1%}**, "
              f"nota inteira certa **{n['acerto_nota_inteira']:.1%}**",
              f"- digital vs. escaneada: {n['por_tipo']}",
              f"- confidence médio: certos {n['conf_media_certos']:.3f} / errados {n['conf_media_errados']}",
              f"- ECE {n['ece']:.3f}; limiar sugerido {n['limiar_escolhido']}", "",
              "| campo | acerto | conf. média | conf. certos | conf. errados |", "|---|---|---|---|---|"]
        for c, v in n["por_campo"].items():
            L.append(f"| {c} | {v['acerto']:.3f} | {v['conf_media']:.3f} | {v['conf_certos']} | {v['conf_errados']} |")
        L.append("")
    if b := m.get("baseline"):
        L += ["## Linha de base (rótulos genéricos)", "",
              f"- {b['frac_identifica_praga']:.1%} das imagens têm algum rótulo que identifica a doença",
              f"- {b['frac_menciona_planta']:.1%} têm algum rótulo de planta/folha",
              f"- top-1 mais comuns: {b['top_rotulos']}", ""]
    if c := m.get("classificador"):
        L += ["## Classificador de folhas", "",
              f"- acurácia **{c['acuracia']:.1%}**, F1 macro **{c['f1_macro']:.3f}**",
              f"- confidence médio: certos {c['conf_media_certos']:.3f} / errados {c['conf_media_errados']}",
              f"- ECE {c['ece']:.3f}; limiar sugerido {c['limiar_escolhido']}", "",
              "| classe | precisão | recall | F1 | conf. média |", "|---|---|---|---|---|"]
        for k, v in c["por_classe"].items():
            L.append(f"| {k} | {v['precision']} | {v['recall']} | {v['f1-score']} | {v['conf_media']} |")
        L.append("")
    if k := m.get("custos"):
        L += ["## Tempo e custo", "", f"- tempo médio por item (ms): {k['tempo_medio_ms_por_item']}",
              f"- estimativa mensal GCP (USD): { {a: round(v, 2) for a, v in k['estimativa_mensal_usd'].items()} }", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--volume-notas", type=int, default=2000)
    ap.add_argument("--volume-imagens", type=int, default=5000)
    args = ap.parse_args()

    df = storage.load_dataframe().sort_values("processado_em")
    df = df.drop_duplicates(["arquivo", "tipo", "campo"], keep="last")
    # folhas sem "<classe>/" no nome vieram da demo pelo bucket e não têm gabarito
    df = df[(df.tipo == "nota") | df.arquivo.str.contains("/")]
    m = dict(backend=config.BACKEND, notas=avalia_notas(df), baseline=avalia_baseline(df),
             classificador=avalia_classificador(df),
             custos=custos(df, args.volume_notas, args.volume_imagens))
    (config.RESULTS / "metricas.json").write_text(json.dumps(m, indent=2, ensure_ascii=False, default=str),
                                                  encoding="utf-8")
    md = resumo_md(m)
    (config.RESULTS / "resumo.md").write_text(md, encoding="utf-8")
    dst = config.ROOT / "report" / "figuras"
    dst.mkdir(parents=True, exist_ok=True)
    for f in FIG.glob("*.png"):
        shutil.copy(f, dst / f.name)
    print(md)


if __name__ == "__main__":
    main()
