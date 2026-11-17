"""Extrator local de DANFE, substituto do Document AI Invoice Parser.

1. Pega caixas de texto (x, y, texto, score): da camada de texto do PDF ou,
   se a página for só imagem, do OCR (RapidOCR).
2. Para cada campo procura o rótulo ("DATA DA EMISSÃO"...) e escolhe o valor
   mais próximo abaixo ou à direita que bate com o formato esperado.
3. O confidence combina o score do OCR com validações (dígito do CNPJ,
   coerência com a chave de acesso). É um número do *modelo*, não acerto
   medido; a Fase 4 compara os dois.
"""
import re
from dataclasses import dataclass

import pymupdf as fitz

OCR_DPI = 200


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    score: float

    @property
    def cx(self):
        return (self.x0 + self.x1) / 2


_ocr = None


def _ocr_engine():
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr = RapidOCR()
    return _ocr


def _boxes_e_tamanho(path) -> tuple[list[Box], str, tuple[float, float]]:
    with fitz.open(path) as doc:
        page = doc[0]
        tamanho = (float(page.rect.width), float(page.rect.height))
        boxes = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    t = span["text"].strip()
                    if t:
                        boxes.append(Box(*span["bbox"], t, 1.0))
        if len(boxes) > 20:
            return boxes, "texto", tamanho

        import numpy as np

        pix = page.get_pixmap(dpi=OCR_DPI, colorspace=fitz.csGRAY)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    result, _ = _ocr_engine()(img)
    k = 72 / OCR_DPI  # volta para coordenadas em pontos
    for quad, text, score in result or []:
        xs, ys = [p[0] for p in quad], [p[1] for p in quad]
        boxes.append(Box(min(xs) * k, min(ys) * k, max(xs) * k, max(ys) * k, text.strip(), float(score)))
    return boxes, "ocr", tamanho


def boxes_from_pdf(path) -> tuple[list[Box], str]:
    boxes, fonte, _ = _boxes_e_tamanho(path)
    return boxes, fonte


# ---------- normalização e validação ----------

RE_CNPJ = re.compile(r"\d{2}[.,]?\d{3}[.,]?\d{3}\s?/\s?\d{4}\s?-?\s?\d{2}")
RE_DATA = re.compile(r"\b(\d{2})[/.-](\d{2})[/.-](\d{4})\b")
RE_VALOR = re.compile(r"\b\d{1,3}(?:[.\s]\d{3})*[,.]\d{2}\b")  # OCR às vezes troca a vírgula por ponto
RE_NUMERO = re.compile(r"N[º°oO0]?\.?\s*:?\s*(\d{3}[.,]\d{3}[.,]\d{3})")  # OCR costuma perder o "º"


def digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def cnpj_valido(c: str) -> bool:
    c = digits(c)
    if len(c) != 14 or len(set(c)) == 1:
        return False

    def dv(base, pesos):
        r = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        return "0" if r < 2 else str(11 - r)

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return c[12] == dv(c[:12], p1) and c[13] == dv(c[:13], [6] + p1)


def fmt_cnpj(c: str) -> str:
    c = digits(c)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def valor_float(s: str) -> float:
    s = re.sub(r"\s", "", s)
    if re.search(r"\.\d{2}$", s) and not re.search(r",\d{2}$", s):  # decimal com ponto (OCR)
        return float(s.replace(",", ""))
    return float(re.sub(r"\.", "", s).replace(",", "."))


def achar_chave(boxes) -> str | None:
    """Chave de acesso: 44 dígitos, impressa em blocos de 4."""
    for i, b in enumerate(boxes):
        if re.search(r"CHAVE\s*DE\s*ACESSO", b.text, re.I):
            perto = sorted(boxes[i + 1:i + 6], key=lambda o: abs(o.y0 - b.y1))
            for o in perto:
                d = digits(o.text)
                if len(d) == 44:
                    return d
    for b in boxes:
        d = digits(b.text)
        if len(d) == 44:
            return d
    return None


# ---------- busca por rótulo ----------

def valor_perto(boxes, rotulo: re.Pattern, padrao: re.Pattern, max_dy=28):
    """Valor que casa com `padrao` logo abaixo (mesma coluna) ou à direita do rótulo."""
    melhores = []
    for lb in boxes:
        if not rotulo.search(lb.text):
            continue
        resto = rotulo.split(lb.text, maxsplit=1)[-1]
        m = padrao.search(resto)
        if m:  # "Emissão: 12/03/2026" na mesma caixa
            melhores.append((0.0, m, lb))
            continue
        for b in boxes:
            if b is lb:
                continue
            m = padrao.search(b.text)
            if not m:
                continue
            dy = b.y0 - lb.y0
            abaixo = 0 < dy < max_dy and b.x0 < lb.x1 + 10 and b.x1 > lb.x0 - 10
            direita = abs(dy) < 6 and 0 < b.x0 - lb.x1 < 120
            if abaixo or direita:
                melhores.append((abs(dy) + abs(b.x0 - lb.x0) * 0.2, m, b))
    if not melhores:
        return None, None
    _, m, b = min(melhores, key=lambda t: t[0])
    return m, b


R_EMISSAO = re.compile(r"(DATA\s*DA\s*EMISS[ÃA]O|D[Tt]\.?\s*EMISS[ÃA]O|EMISS[ÃA]O)", re.I)
R_TOTAL = re.compile(r"(VALOR\s*TOTAL\s*DA\s*(NOTA|NF-?e?)|V\.?\s*TOTAL\s*(DA\s*)?(NOTA|NF-?e?))", re.I)
R_CNPJ_EMIT = re.compile(r"^CNPJ(?!\s*/)(\s*EMITENTE)?\s*:?\s*", re.I)  # não pega "CNPJ / CPF"


def _caixa_pct(b: Box, largura: float, altura: float) -> dict[str, float] | None:
    if largura <= 0 or altura <= 0:
        return None
    x0 = max(0.0, min(b.x0, largura))
    y0 = max(0.0, min(b.y0, altura))
    x1 = max(x0, min(b.x1, largura))
    y1 = max(y0, min(b.y1, altura))
    return {
        "x": round(x0 / largura * 100, 2),
        "y": round(y0 / altura * 100, 2),
        "w": round((x1 - x0) / largura * 100, 2),
        "h": round((y1 - y0) / altura * 100, 2),
    }


def extract_detalhado(path) -> tuple[dict, str, tuple[float, float]]:
    """Devolve ({campo: (valor, confidence, caixa_pct)}, fonte, (largura_pt, altura_pt))."""
    boxes, fonte, tamanho = _boxes_e_tamanho(path)
    largura, altura = tamanho
    boxes.sort(key=lambda b: (round(b.y0 / 4), b.x0))
    chave = achar_chave(boxes)
    out = {}

    # CNPJ do emitente: rótulo "CNPJ" sozinho (o do destinatário é "CNPJ / CPF");
    # se não achar, o primeiro CNPJ válido da página.
    m, b = valor_perto(boxes, R_CNPJ_EMIT, RE_CNPJ)
    if not m:
        cands = [(RE_CNPJ.search(x.text), x) for x in boxes]
        cands = [(mm, x) for mm, x in cands if mm and cnpj_valido(mm.group())]
        m, b = cands[0] if cands else (None, None)
    if m:
        conf = b.score * (1.0 if cnpj_valido(m.group()) else 0.4)
        if chave and chave[6:20] == digits(m.group()):
            conf = min(1.0, conf + 0.15)
        out["cnpj_emitente"] = (fmt_cnpj(m.group()), round(conf * 0.85, 3), _caixa_pct(b, largura, altura))
    elif chave:  # recupera pela chave de acesso
        out["cnpj_emitente"] = (fmt_cnpj(chave[6:20]), 0.5, None)

    # Número da nota: "Nº 000.012.345"
    for x in boxes:
        mm = RE_NUMERO.search(x.text)
        if mm:
            num = str(int(digits(mm.group(1))))
            conf = x.score * 0.8
            if chave and int(chave[25:34]) == int(num):
                conf = min(1.0, conf + 0.15)
            out["numero"] = (num, round(conf, 3), _caixa_pct(x, largura, altura))
            break
    else:
        if chave:
            out["numero"] = (str(int(chave[25:34])), 0.5, None)

    # Data de emissão
    m, b = valor_perto(boxes, R_EMISSAO, RE_DATA)
    if m:
        d, mo, a = m.groups()
        conf = b.score * 0.85
        if chave and chave[2:6] == a[2:] + mo:
            conf = min(1.0, conf + 0.1)
        out["data_emissao"] = (f"{a}-{mo}-{d}", round(conf, 3), _caixa_pct(b, largura, altura))

    # Valor total
    m, b = valor_perto(boxes, R_TOTAL, RE_VALOR)
    if m:
        out["valor_total"] = (f"{valor_float(m.group()):.2f}", round(b.score * 0.9, 3), _caixa_pct(b, largura, altura))

    return out, fonte, tamanho


def extract(path) -> tuple[dict, str]:
    """Devolve ({campo: (valor, confidence)}, fonte) para um PDF de DANFE."""
    campos, fonte, _ = extract_detalhado(path)
    return {c: (v, conf) for c, (v, conf, _) in campos.items()}, fonte
