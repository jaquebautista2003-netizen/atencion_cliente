import sqlite3
from contextlib import contextmanager

from . import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS turnos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    numero      INTEGER NOT NULL,
    codigo      TEXT    NOT NULL,
    estado      TEXT    NOT NULL CHECK (estado IN ('espera', 'atendiendo', 'finalizado')),
    mesa_id     INTEGER,
    creado_en   TEXT    NOT NULL,
    llamado_en  TEXT,
    finalizado_en TEXT
);

CREATE INDEX IF NOT EXISTS idx_turnos_estado ON turnos (estado, id);

CREATE TABLE IF NOT EXISTS mesas (
    id        INTEGER PRIMARY KEY,
    nombre    TEXT    NOT NULL,
    activa    INTEGER NOT NULL DEFAULT 1,
    turno_id  INTEGER REFERENCES turnos (id)
);
"""


def conectar(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def inicializar(conn: sqlite3.Connection, num_mesas: int) -> None:
    conn.executescript(ESQUEMA)
    for i in range(1, num_mesas + 1):
        conn.execute(
            "INSERT OR IGNORE INTO mesas (id, nombre, activa) VALUES (?, ?, 1)",
            (i, f"Mesa {i}"),
        )
    conn.commit()


@contextmanager
def transaccion(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
