"""Roteamento: olha a extensão, chama o extrator certo e grava na tabela.

Chamado pelo watcher (scripts/watch_bucket.py) e pelos lotes (scripts/run_batch.py).
"""
import logging
import time
from pathlib import Path

from . import config, invoices, leaves
from .storage import Row, save

log = logging.getLogger("agroflow")


class ArquivoInvalido(Exception):
    pass


def process_invoice(path, nome=None) -> list[Row]:
    nome = nome or Path(path).name
    t = time.perf_counter()
    campos, fonte = invoices.extract(path)
    ms = (time.perf_counter() - t) * 1000
    if not campos:
        raise ArquivoInvalido(f"nenhum campo de DANFE encontrado em {nome}")
    rows = [Row(nome, "nota", c, v, conf, duracao_ms=ms) for c, (v, conf) in campos.items()]
    rows.append(Row(nome, "nota", "_fonte", fonte, None, duracao_ms=ms))
    return rows


def process_leaf(path, nome=None, baseline=True, classificador=None) -> list[Row]:
    """classificador=None: usa o classificador se houver um disponível (ver leaves)."""
    if classificador is None:
        classificador = leaves.classificador_disponivel()
    nome = nome or Path(path).name
    rows = []
    if baseline:
        t = time.perf_counter()
        labels = leaves.baseline(path)
        ms = (time.perf_counter() - t) * 1000
        rows += [Row(nome, "folha_baseline", f"rotulo_{i}", l, s, duracao_ms=ms)
                 for i, (l, s) in enumerate(labels, 1)]
    if classificador:
        t = time.perf_counter()
        classe, conf, _ = leaves.classify(path)
        rows.append(Row(nome, "folha_classificador", "classe", classe, conf,
                        duracao_ms=(time.perf_counter() - t) * 1000))
    return rows


def process_file(path, nome=None) -> list[Row]:
    """Processa um arquivo do bucket e grava o resultado. Levanta ArquivoInvalido."""
    ext = Path(nome or path).suffix.lower()
    if ext in config.PDF_EXT:
        rows = process_invoice(path, nome)
    elif ext in config.IMAGE_EXT:
        try:
            rows = process_leaf(path, nome)
        except OSError as e:  # PIL não conseguiu abrir
            raise ArquivoInvalido(str(e)) from e
    else:
        raise ArquivoInvalido(f"extensão não suportada: {ext or '(nenhuma)'}")
    save(rows)
    return rows
