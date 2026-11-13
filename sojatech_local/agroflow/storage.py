"""Tabela de resultados em SQLite (results/agroflow.db).

Uma linha por (arquivo, campo). Para notas o campo é cnpj_emitente, numero...;
para folhas é "classe" (classificador) ou "rotulo_N" (linha de base).
"""
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS resultados (
    arquivo      TEXT NOT NULL,
    tipo         TEXT NOT NULL,   -- nota | folha_baseline | folha_classificador
    campo        TEXT NOT NULL,
    valor        TEXT,
    confidence   REAL,
    backend      TEXT NOT NULL,
    duracao_ms   REAL,
    processado_em TEXT NOT NULL
)
"""


@dataclass
class Row:
    arquivo: str
    tipo: str
    campo: str
    valor: str | None
    confidence: float | None
    backend: str = config.BACKEND
    duracao_ms: float | None = None
    processado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _sqlite():
    config.RESULTS.mkdir(exist_ok=True)
    con = sqlite3.connect(config.RESULTS_DB)
    con.execute(SCHEMA)
    return con


def save(rows: list[Row]) -> None:
    if not rows:
        return
    with _sqlite() as con:
        con.executemany(
            "INSERT INTO resultados VALUES (:arquivo, :tipo, :campo, :valor, :confidence,"
            " :backend, :duracao_ms, :processado_em)",
            [asdict(r) for r in rows],
        )


def clear(tipo: str | None = None) -> None:
    """Apaga resultados do backend atual (para reprocessar um lote do zero)."""
    with _sqlite() as con:
        if tipo:
            con.execute("DELETE FROM resultados WHERE tipo = ? AND backend = ?", (tipo, config.BACKEND))
        else:
            con.execute("DELETE FROM resultados WHERE backend = ?", (config.BACKEND,))


def load_dataframe():
    import pandas as pd

    with _sqlite() as con:
        return pd.read_sql("SELECT * FROM resultados", con)
