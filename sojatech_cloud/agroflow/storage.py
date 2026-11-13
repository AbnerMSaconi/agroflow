"""Tabela de resultados no BigQuery (mesmo esquema do SQLite do sojatech_local).

Uma linha por (arquivo, campo). Para notas o campo é cnpj_emitente, numero...;
para folhas é "classe" (classificador) ou "rotulo_N" (linha de base).
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from . import config


@dataclass
class Row:
    arquivo: str
    tipo: str     # nota | folha_baseline | folha_classificador
    campo: str
    valor: str | None
    confidence: float | None
    backend: str = config.BACKEND
    duracao_ms: float | None = None
    processado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _client():
    from google.cloud import bigquery

    return bigquery.Client(project=config.GCP_PROJECT or None)


def save(rows: list[Row]) -> None:
    if not rows:
        return
    errors = _client().insert_rows_json(config.BQ_TABLE, [asdict(r) for r in rows])
    if errors:
        raise RuntimeError(f"BigQuery recusou linhas: {errors}")


def clear(tipo: str | None = None) -> None:
    """Não apaga nada: linhas recém-inseridas por streaming não aceitam DELETE,
    e a avaliação já fica com a gravação mais recente de cada campo."""


def load_dataframe():
    return _client().query(f"SELECT * FROM `{config.BQ_TABLE}`").to_dataframe()


def load_local_dataframe():
    """Resultados do sojatech_local (SQLite), para a comparação. Vazio se não houver."""
    import sqlite3

    import pandas as pd

    if not config.LOCAL_RESULTS_DB.exists():
        return pd.DataFrame()
    with sqlite3.connect(config.LOCAL_RESULTS_DB) as con:
        return pd.read_sql("SELECT * FROM resultados", con)
