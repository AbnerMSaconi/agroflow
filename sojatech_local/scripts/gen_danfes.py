"""Gera DANFEs fictícias em PDF e a planilha de gabarito.

Todos os dados são inventados (CNPJ/CPF com dígitos válidos, chave de acesso
coerente), então nada precisa ser anonimizado antes de subir para a nuvem.

Variações para o extrator não ter vida fácil:
  - layout "padrao" (próximo do DANFE oficial) e "compacto" (rótulos diferentes)
  - só no conjunto de teste: layout "variante", com rótulos de outros emissores
    ("DATA DE EMISSÃO", "VALOR TOTAL DA NF-e", "C.N.P.J.") e outra fonte
  - parte das notas vira imagem com rotação, ruído e JPEG ("escaneada")
  - destinatário com CNPJ ou CPF, data de saída diferente da emissão

Uso: python scripts/gen_danfes.py --n 40                    # desenvolvimento
     python scripts/gen_danfes.py --n 40 --conjunto teste    # teste separado
"""
import argparse
import csv
import io
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agroflow import config  # noqa: E402

W, H = A4
M = 20  # margem

EMPRESAS = [
    "AGRO INSUMOS CERRADO LTDA", "SEMENTES PLANALTO S.A.", "FERTIVALE COMERCIO DE ADUBOS LTDA",
    "DEFENSIVOS MATO GROSSO LTDA", "COOPERATIVA AGRICOLA RIO VERDE", "MAQAGRO PECAS E SERVICOS LTDA",
    "NUTRISOLO FERTILIZANTES LTDA", "GRAOS DO SUL ARMAZENS GERAIS", "BIOCAMPO INOCULANTES LTDA",
    "TRANSAGRO LOGISTICA RURAL LTDA",
]
DESTINATARIOS = [
    "SOJATECH AGRICOLA LTDA", "FAZENDA BOA ESPERANCA", "JOAO PEREIRA DA SILVA",
    "MARIA APARECIDA SOUZA", "FAZENDA SANTA LUZIA", "AGROPECUARIA TRES IRMAOS LTDA",
]
PRODUTOS = [
    ("SEMENTE SOJA RR2 PRO SC 40KG", "12010090", "SC", 180, 420),
    ("FERTILIZANTE NPK 04-14-08 BIG BAG", "31052000", "TON", 2900, 3600),
    ("HERBICIDA GLIFOSATO 480 G/L GL 20L", "38089329", "GL", 310, 520),
    ("FUNGICIDA AZOXISTROBINA 250 SC 5L", "38089219", "UN", 480, 760),
    ("INOCULANTE BRADYRHIZOBIUM 1L", "30029000", "UN", 35, 70),
    ("INSETICIDA TIAMETOXAM 1L", "38089119", "UN", 190, 330),
    ("CALCARIO DOLOMITICO A GRANEL", "25210000", "TON", 110, 190),
    ("OLEO MINERAL ADJUVANTE 5L", "27101932", "UN", 60, 120),
]
CIDADES = [("RIO VERDE", "GO", "52"), ("SORRISO", "MT", "51"), ("CASCAVEL", "PR", "41"),
           ("LUIS EDUARDO MAGALHAES", "BA", "29"), ("DOURADOS", "MS", "50"), ("PASSO FUNDO", "RS", "43")]


# ---------- números com dígito verificador ----------

def _dv(digits: list[int], weights: list[int]) -> int:
    r = sum(d * w for d, w in zip(digits, weights)) % 11
    return 0 if r < 2 else 11 - r


def gera_cnpj(rng) -> str:
    base = [rng.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]
    base.append(_dv(base, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]))
    base.append(_dv(base, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]))
    return "".join(map(str, base))


def gera_cpf(rng) -> str:
    base = [rng.randint(0, 9) for _ in range(9)]
    base.append(_dv(base, list(range(10, 1, -1))))
    base.append(_dv(base, list(range(11, 1, -1))))
    return "".join(map(str, base))


def fmt_cnpj(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def fmt_cpf(c: str) -> str:
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"


def chave_acesso(cuf, emissao: date, cnpj, serie, numero, rng) -> str:
    corpo = f"{cuf}{emissao:%y%m}{cnpj}55{serie:03d}{numero:09d}1{rng.randint(0, 99999999):08d}"
    pesos = [2, 3, 4, 5, 6, 7, 8, 9] * 6
    soma = sum(int(d) * p for d, p in zip(reversed(corpo), pesos))
    r = soma % 11
    return corpo + str(0 if r < 2 else 11 - r)


def brl(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------- desenho ----------

def campo(c, x, y, w, h, rotulo, valor="", size=9, font="Helvetica"):
    """Caixa com rótulo pequeno no topo e valor embaixo, como no DANFE."""
    c.rect(x, y, w, h)
    c.setFont("Helvetica", 5.5)
    c.drawString(x + 2, y + h - 7, rotulo)
    if valor:
        c.setFont(font, size)
        c.drawString(x + 3, y + 4, valor)


def desenha(c, n, layout):
    c.setLineWidth(0.6)
    y = H - M
    lbl = {
        "padrao": dict(emissao="DATA DA EMISSÃO", total="VALOR TOTAL DA NOTA", cnpj="CNPJ"),
        "compacto": dict(emissao="DT. EMISSÃO", total="V. TOTAL NF-e", cnpj="CNPJ EMITENTE"),
        "variante": dict(emissao="DATA DE EMISSÃO", total="VALOR TOTAL DA NF-e", cnpj="C.N.P.J."),
    }[layout]
    font = {"padrao": "Helvetica", "compacto": "Courier", "variante": "Times-Roman"}[layout]

    # canhoto
    y -= 34
    c.rect(M, y, W - 2 * M - 110, 34)
    c.setFont("Helvetica", 6)
    c.drawString(M + 3, y + 24, f"RECEBEMOS DE {n['emitente']} OS PRODUTOS/SERVIÇOS CONSTANTES DA NOTA FISCAL INDICADA AO LADO")
    campo(c, M, y, 120, 18, "DATA DE RECEBIMENTO")
    campo(c, M + 120, y, W - 2 * M - 230, 18, "IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR")
    c.rect(W - M - 110, y, 110, 34)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(W - M - 100, y + 20, "NF-e")
    c.setFont("Helvetica", 8)
    c.drawString(W - M - 100, y + 9, f"Nº {n['numero_fmt']}  SÉRIE {n['serie']:03d}")

    # cabeçalho: emitente | DANFE | chave
    y -= 92
    c.rect(M, y, 220, 88)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(M + 5, y + 70, n["emitente"][:38])
    c.setFont("Helvetica", 7)
    c.drawString(M + 5, y + 56, f"ROD. BR-{n['br']} KM {n['km']}, ZONA RURAL")
    c.drawString(M + 5, y + 46, f"{n['cidade']} - {n['uf']}  CEP {n['cep']}")
    c.drawString(M + 5, y + 36, f"FONE (64) 3{n['fone']}")
    if layout == "compacto":
        c.drawString(M + 5, y + 20, f"{lbl['cnpj']}: {fmt_cnpj(n['cnpj'])}")

    x = M + 220
    c.rect(x, y, 110, 88)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x + 30, y + 70, "DANFE")
    c.setFont("Helvetica", 6)
    c.drawString(x + 8, y + 60, "DOCUMENTO AUXILIAR DA")
    c.drawString(x + 8, y + 52, "NOTA FISCAL ELETRÔNICA")
    c.drawString(x + 8, y + 40, "0 - ENTRADA   1 - SAÍDA   [1]")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 8, y + 26, f"Nº {n['numero_fmt']}")
    c.drawString(x + 8, y + 16, f"SÉRIE {n['serie']:03d}")
    c.setFont("Helvetica", 7)
    c.drawString(x + 8, y + 6, "FOLHA 1/1")

    x = M + 330
    wr = W - M - x
    c.rect(x, y, wr, 88)
    c.setFont("Helvetica", 5.5)
    c.drawString(x + 3, y + 80, "CHAVE DE ACESSO")
    c.setFont("Courier", 6.8)
    ch = n["chave"]
    c.drawString(x + 3, y + 66, " ".join(ch[i:i + 4] for i in range(0, 44, 4)))
    c.setFont("Helvetica", 6)
    c.drawString(x + 3, y + 40, "Consulta de autenticidade no portal nacional da NF-e")
    c.drawString(x + 3, y + 32, "www.nfe.fazenda.gov.br/portal ou no site da Sefaz Autorizadora")

    # natureza / protocolo
    y -= 20
    campo(c, M, y, 330, 20, "NATUREZA DA OPERAÇÃO", "VENDA DE MERCADORIA", font=font)
    campo(c, M + 330, y, W - 2 * M - 330, 20, "PROTOCOLO DE AUTORIZAÇÃO DE USO",
          f"{n['protocolo']} {n['emissao']:%d/%m/%Y} {n['hora']}", font=font)
    y -= 20
    campo(c, M, y, 180, 20, "INSCRIÇÃO ESTADUAL", n["ie"], font=font)
    campo(c, M + 180, y, 180, 20, "INSC. ESTADUAL DO SUBST. TRIB.", font=font)
    if layout != "compacto":
        campo(c, M + 360, y, W - 2 * M - 360, 20, lbl["cnpj"], fmt_cnpj(n["cnpj"]), font=font)
    else:
        campo(c, M + 360, y, W - 2 * M - 360, 20, "INSCRIÇÃO MUNICIPAL", n["im"], font=font)

    # destinatário
    y -= 12
    c.setFont("Helvetica-Bold", 7)
    c.drawString(M, y + 3, "DESTINATÁRIO / REMETENTE")
    y -= 20
    campo(c, M, y, 300, 20, "NOME / RAZÃO SOCIAL", n["dest"], font=font)
    campo(c, M + 300, y, 145, 20, "CNPJ / CPF", n["dest_doc"], font=font)
    campo(c, M + 445, y, W - 2 * M - 445, 20, lbl["emissao"], f"{n['emissao']:%d/%m/%Y}", font=font)
    y -= 20
    campo(c, M, y, 300, 20, "ENDEREÇO", "ESTRADA VICINAL KM 12", font=font)
    campo(c, M + 300, y, 145, 20, "BAIRRO / DISTRITO", "ZONA RURAL", font=font)
    campo(c, M + 445, y, W - 2 * M - 445, 20, "DATA DA SAÍDA/ENTRADA", f"{n['saida']:%d/%m/%Y}", font=font)

    # cálculo do imposto
    y -= 12
    c.setFont("Helvetica-Bold", 7)
    c.drawString(M, y + 3, "CÁLCULO DO IMPOSTO")
    w6 = (W - 2 * M) / 6
    y -= 20
    for i, (r, v) in enumerate([("BASE DE CÁLC. DO ICMS", n["base_icms"]), ("VALOR DO ICMS", n["icms"]),
                                ("BASE CÁLC. ICMS S.T.", 0), ("VALOR DO ICMS SUBST.", 0),
                                ("V. TOTAL TRIBUTOS", n["tributos"]), ("VALOR TOTAL DOS PRODUTOS", n["produtos"])]):
        campo(c, M + i * w6, y, w6, 20, r, brl(v), font=font)
    y -= 20
    for i, (r, v) in enumerate([("VALOR DO FRETE", n["frete"]), ("VALOR DO SEGURO", n["seguro"]),
                                ("DESCONTO", n["desconto"]), ("OUTRAS DESPESAS", 0),
                                ("VALOR TOTAL DO IPI", 0), (lbl["total"], n["total"])]):
        campo(c, M + i * w6, y, w6, 20, r, brl(v), size=9 if i < 5 else 10, font=font)

    # transportador
    y -= 12
    c.setFont("Helvetica-Bold", 7)
    c.drawString(M, y + 3, "TRANSPORTADOR / VOLUMES TRANSPORTADOS")
    y -= 20
    campo(c, M, y, 250, 20, "RAZÃO SOCIAL", "O MESMO", font=font)
    campo(c, M + 250, y, 90, 20, "FRETE POR CONTA", "0-EMITENTE", font=font)
    campo(c, M + 340, y, W - 2 * M - 340, 20, "PLACA DO VEÍCULO / UF", f"{n['placa']} {n['uf']}", font=font)

    # itens
    y -= 12
    c.setFont("Helvetica-Bold", 7)
    c.drawString(M, y + 3, "DADOS DOS PRODUTOS / SERVIÇOS")
    cols = [("CÓDIGO", 45), ("DESCRIÇÃO DO PRODUTO / SERVIÇO", 200), ("NCM/SH", 50), ("CFOP", 35),
            ("UN", 30), ("QUANT.", 50), ("V. UNITÁRIO", 70), ("V. TOTAL", W - 2 * M - 480)]
    y -= 14
    x = M
    for r, w in cols:
        c.rect(x, y, w, 14)
        c.setFont("Helvetica", 5.5)
        c.drawString(x + 2, y + 5, r)
        x += w
    c.setFont(font, 7)
    for it in n["itens"]:
        y -= 13
        x = M
        vals = [it["cod"], it["desc"], it["ncm"], "5102", it["un"], brl(it["qtd"]), brl(it["vu"]), brl(it["vt"])]
        for (_, w), v in zip(cols, vals):
            c.rect(x, y, w, 13)
            c.drawString(x + 2, y + 4, v)
            x += w

    # dados adicionais
    y -= 70
    c.rect(M, y, W - 2 * M, 60)
    c.setFont("Helvetica", 5.5)
    c.drawString(M + 2, y + 52, "INFORMAÇÕES COMPLEMENTARES")
    c.setFont("Helvetica", 6.5)
    c.drawString(M + 4, y + 40, f"PEDIDO {n['pedido']}. DOCUMENTO FICTÍCIO GERADO PARA FINS ACADÊMICOS - SEM VALOR FISCAL.")
    c.drawString(M + 4, y + 30, f"Vencimento duplicata: {n['vencimento']:%d/%m/%Y}  Valor: R$ {brl(n['total'])}")


def gera_nota(i, rng):
    emissao = date(2026, 1, 1) + timedelta(days=rng.randint(0, 270))
    cidade, uf, cuf = rng.choice(CIDADES)
    cnpj = gera_cnpj(rng)
    numero = rng.randint(1000, 250000)
    serie = rng.choice([1, 1, 1, 2, 3])
    itens = []
    for j, (desc, ncm, un, lo, hi) in enumerate(rng.sample(PRODUTOS, rng.randint(1, 5))):
        qtd = rng.choice([1, 2, 5, 10, 20, 40, 100]) if un != "TON" else rng.randint(1, 30)
        vu = round(rng.uniform(lo, hi), 2)
        itens.append(dict(cod=f"{rng.randint(100, 9999):05d}", desc=desc, ncm=ncm, un=un,
                          qtd=qtd, vu=vu, vt=round(qtd * vu, 2)))
    produtos = round(sum(it["vt"] for it in itens), 2)
    frete = round(rng.choice([0, 0, rng.uniform(150, 2500)]), 2)
    seguro = round(rng.choice([0, 0, 0, rng.uniform(50, 300)]), 2)
    desconto = round(rng.choice([0, 0, produtos * rng.choice([0.02, 0.05])]), 2)
    total = round(produtos + frete + seguro - desconto, 2)
    dest_cpf = rng.random() < 0.35
    return dict(
        i=i, emitente=rng.choice(EMPRESAS), cnpj=cnpj, numero=numero,
        numero_fmt=f"{numero:09d}"[:3] + "." + f"{numero:09d}"[3:6] + "." + f"{numero:09d}"[6:],
        serie=serie, emissao=emissao, saida=emissao + timedelta(days=rng.randint(0, 3)),
        hora=f"{rng.randint(7, 18):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}",
        cidade=cidade, uf=uf, cep=f"{rng.randint(70000, 99999)}-{rng.randint(0, 999):03d}",
        fone=f"{rng.randint(100, 999)}-{rng.randint(1000, 9999)}", br=rng.choice([60, 163, 364, 242, 277]),
        km=rng.randint(1, 900), ie=f"{rng.randint(10, 99)}.{rng.randint(100, 999)}.{rng.randint(100, 999)}-{rng.randint(0, 9)}",
        im=str(rng.randint(10000, 99999)),
        dest=rng.choice(DESTINATARIOS[2:4]) if dest_cpf else rng.choice(DESTINATARIOS[:2] + DESTINATARIOS[4:]),
        dest_doc=fmt_cpf(gera_cpf(rng)) if dest_cpf else fmt_cnpj(gera_cnpj(rng)),
        chave=chave_acesso(cuf, emissao, cnpj, serie, numero, rng),
        protocolo=f"1{cuf}{rng.randint(10**11, 10**12 - 1)}",
        base_icms=round(produtos * 0.6, 2), icms=round(produtos * 0.6 * 0.07, 2),
        tributos=round(produtos * 0.11, 2), produtos=produtos, frete=frete, seguro=seguro,
        desconto=desconto, total=total, itens=itens,
        placa=f"{''.join(rng.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=3))}{rng.randint(0, 9)}{rng.choice('ABCDEFGHIJ')}{rng.randint(10, 99)}",
        pedido=rng.randint(1000, 99999), vencimento=emissao + timedelta(days=rng.choice([30, 60, 90])),
    )


def escanear(pdf_bytes: bytes, rng) -> bytes:
    """Transforma o PDF em imagem torta e suja, sem camada de texto."""
    page = fitz.open(stream=pdf_bytes, filetype="pdf")[0]
    pix = page.get_pixmap(dpi=rng.choice([150, 200]), colorspace=fitz.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    img = img.rotate(rng.uniform(-1.5, 1.5), expand=False, fillcolor=255, resample=Image.BICUBIC)
    if rng.random() < 0.5:
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.8)))
    noise = Image.effect_noise(img.size, rng.uniform(8, 20))
    img = Image.blend(img, noise, 0.08)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=rng.randint(45, 75))
    out = fitz.open()
    p = out.new_page(width=W, height=H)
    p.insert_image(p.rect, stream=buf.getvalue())
    return out.tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--escaneadas", type=float, default=0.35, help="fração de notas escaneadas")
    ap.add_argument("--seed", type=int, help="padrão: 2026 (dev) ou 7 (teste)")
    ap.add_argument("--conjunto", choices=["dev", "teste"], default="dev")
    args = ap.parse_args()

    teste = args.conjunto == "teste"
    rng = random.Random(args.seed if args.seed is not None else (7 if teste else 2026))
    base = config.INVOICES_TEST_DIR if teste else config.INVOICES_DIR
    gabarito = config.GABARITO_NOTAS_TESTE if teste else config.GABARITO_NOTAS
    pdf_dir = base / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    linhas = []
    for i in range(1, args.n + 1):
        n = gera_nota(i, rng)
        if teste:
            layout = rng.choice(["padrao", "compacto", "variante"])
        else:
            layout = "padrao" if rng.random() < 0.65 else "compacto"
        escaneada = rng.random() < args.escaneadas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.setTitle(f"DANFE {n['numero_fmt']}")
        desenha(c, n, layout)
        c.save()
        data = escanear(buf.getvalue(), rng) if escaneada else buf.getvalue()
        nome = f"nota_{i:03d}.pdf"
        (pdf_dir / nome).write_bytes(data)
        linhas.append(dict(arquivo=nome, cnpj_emitente=fmt_cnpj(n["cnpj"]), numero=str(n["numero"]),
                           data_emissao=n["emissao"].isoformat(), valor_total=f"{n['total']:.2f}",
                           layout=layout, escaneada=int(escaneada)))

    with open(gabarito, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    esc = sum(r["escaneada"] for r in linhas)
    print(f"{len(linhas)} notas em {pdf_dir} ({esc} escaneadas); gabarito em {gabarito}")


if __name__ == "__main__":
    main()
