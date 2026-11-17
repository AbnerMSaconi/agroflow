"""Tabela de resultados em SQLite (results/agroflow.db).

Uma linha por (arquivo, campo). Para notas o campo é cnpj_emitente, numero...;
para folhas é "classe" (classificador) ou "rotulo_N" (linha de base).
"""
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from . import config

SCHEMA_RESULTADOS = """
CREATE TABLE IF NOT EXISTS resultados (
    arquivo       TEXT NOT NULL,
    tipo          TEXT NOT NULL,   -- nota | folha_baseline | folha_classificador
    campo         TEXT NOT NULL,
    valor         TEXT,
    confidence    REAL,
    backend       TEXT NOT NULL,
    duracao_ms    REAL,
    processado_em TEXT NOT NULL,
    origem        TEXT NOT NULL DEFAULT 'lote'
)
"""

SCHEMA_ITENS = """
CREATE TABLE IF NOT EXISTS itens (
    id           INTEGER PRIMARY KEY,
    arquivo      TEXT NOT NULL,
    tipo         TEXT NOT NULL,
    estado       TEXT NOT NULL,
    resumo       TEXT NOT NULL,
    motivo       TEXT,
    recebido_em  TEXT NOT NULL,
    duracao_ms   REAL,
    midia        TEXT,
    detalhe_json TEXT
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
    origem: str = "lote"


def _sqlite():
    config.RESULTS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.RESULTS_DB)
    con.execute(SCHEMA_RESULTADOS)
    cols = {row[1] for row in con.execute("PRAGMA table_info(resultados)").fetchall()}
    if "origem" not in cols:
        con.execute("ALTER TABLE resultados ADD COLUMN origem TEXT NOT NULL DEFAULT 'lote'")
    con.execute(SCHEMA_ITENS)
    return con


def save(rows: list[Row]) -> None:
    if not rows:
        return
    with _sqlite() as con:
        con.executemany(
            "INSERT INTO resultados "
            "(arquivo, tipo, campo, valor, confidence, backend, duracao_ms, processado_em, origem) "
            "VALUES (:arquivo, :tipo, :campo, :valor, :confidence, :backend, :duracao_ms, :processado_em, :origem)",
            [asdict(r) for r in rows],
        )


def clear(tipo: str | None = None) -> None:
    """Apaga resultados de lote do backend atual (para reprocessar um lote do zero)."""
    with _sqlite() as con:
        if tipo:
            con.execute(
                "DELETE FROM resultados WHERE tipo = ? AND backend = ? AND origem = 'lote'",
                (tipo, config.BACKEND),
            )
        else:
            con.execute("DELETE FROM resultados WHERE backend = ? AND origem = 'lote'", (config.BACKEND,))


def salvar_item(item: dict) -> None:
    """Persiste um item finalizado do fluxo na tabela `itens`."""
    detalhe = json.dumps(
        {"nota": item.get("nota"), "folha": item.get("folha")},
        ensure_ascii=False,
    )
    with _sqlite() as con:
        con.execute(
            "INSERT OR REPLACE INTO itens "
            "(id, arquivo, tipo, estado, resumo, motivo, recebido_em, duracao_ms, midia, detalhe_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(item["id"]),
                item["arquivo"],
                item["tipo"],
                item["estado"],
                item["resumo"],
                item.get("motivo"),
                item["recebido_em"],
                item.get("duracao_ms"),
                item.get("midia"),
                detalhe,
            ),
        )


def listar_itens(limite: int = 200) -> list[dict]:
    """Carrega os itens finalizados mais recentes (ordenados do mais novo para o mais antigo)."""
    with _sqlite() as con:
        rows = con.execute(
            "SELECT id, arquivo, tipo, estado, resumo, motivo, recebido_em, duracao_ms, midia, detalhe_json "
            "FROM itens ORDER BY id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    out = []
    for row in rows:
        det = json.loads(row[9]) if row[9] else {}
        out.append(
            {
                "id": row[0],
                "arquivo": row[1],
                "tipo": row[2],
                "estado": row[3],
                "resumo": row[4],
                "motivo": row[5],
                "recebido_em": row[6],
                "duracao_ms": row[7],
                "midia": row[8],
                "nota": det.get("nota"),
                "folha": det.get("folha"),
            }
        )
    return out


def proximo_item_id() -> int:
    """Devolve o próximo ID livre na tabela `itens`."""
    with _sqlite() as con:
        row = con.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM itens").fetchone()
    return int(row[0])


def limpar_fluxo() -> None:
    """Apaga os itens das telas e as linhas de resultados geradas pelo fluxo."""
    with _sqlite() as con:
        con.execute("DELETE FROM itens")
        con.execute("DELETE FROM resultados WHERE origem = 'fluxo'")


def load_dataframe():
    import pandas as pd

    with _sqlite() as con:
        return pd.read_sql("SELECT * FROM resultados", con)
