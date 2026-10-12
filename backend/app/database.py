"""Capa de acceso a datos con dos motores:

* SQLite  – por defecto (desarrollo local).
* Postgres – si existe DATABASE_URL / POSTGRES_URL (producción, p. ej. Vercel + Neon).

Las consultas se escriben con marcadores `?`; el adaptador de Postgres los
convierte a `%s`. Toda escritura va dentro de `transaccion()`, que en Postgres
toma un candado global (pg_advisory_xact_lock) para que varias instancias
serverless nunca asignen el mismo turno a dos mesas.
"""

import sqlite3
import threading
from contextlib import contextmanager

from . import config

ESQUEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS turnos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    numero        INTEGER NOT NULL,
    codigo        TEXT    NOT NULL,
    estado        TEXT    NOT NULL CHECK (estado IN ('espera', 'atendiendo', 'finalizado')),
    mesa_id       INTEGER,
    creado_en     TEXT    NOT NULL,
    llamado_en    TEXT,
    finalizado_en TEXT
);
CREATE INDEX IF NOT EXISTS idx_turnos_estado ON turnos (estado, id);
CREATE TABLE IF NOT EXISTS mesas (
    id       INTEGER PRIMARY KEY,
    nombre   TEXT    NOT NULL,
    activa   INTEGER NOT NULL DEFAULT 1,
    turno_id INTEGER REFERENCES turnos (id)
);
"""

ESQUEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS turnos (
    id            SERIAL  PRIMARY KEY,
    numero        INTEGER NOT NULL,
    codigo        TEXT    NOT NULL,
    estado        TEXT    NOT NULL CHECK (estado IN ('espera', 'atendiendo', 'finalizado')),
    mesa_id       INTEGER,
    creado_en     TEXT    NOT NULL,
    llamado_en    TEXT,
    finalizado_en TEXT
);
CREATE INDEX IF NOT EXISTS idx_turnos_estado ON turnos (estado, id);
CREATE TABLE IF NOT EXISTS mesas (
    id       INTEGER PRIMARY KEY,
    nombre   TEXT    NOT NULL,
    activa   INTEGER NOT NULL DEFAULT 1,
    turno_id INTEGER REFERENCES turnos (id)
);
"""


class BaseDatos:
    motor = "base"

    def execute(self, sql: str, params: tuple = ()):
        raise NotImplementedError

    def insertar(self, sql: str, params: tuple = ()) -> int:
        """INSERT que devuelve el id generado."""
        raise NotImplementedError

    @contextmanager
    def transaccion(self):
        raise NotImplementedError

    @contextmanager
    def lectura(self):
        raise NotImplementedError

    def inicializar(self, num_mesas: int) -> None:
        raise NotImplementedError


# --------------------------------------------------------------------- SQLite
class SQLite(BaseDatos):
    motor = "sqlite"

    def __init__(self, ruta: str):
        self.conn = sqlite3.connect(ruta, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._lock = threading.RLock()

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def insertar(self, sql, params=()):
        return self.conn.execute(sql, params).lastrowid

    @contextmanager
    def transaccion(self):
        with self._lock:
            try:
                yield self
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    @contextmanager
    def lectura(self):
        with self._lock:
            yield self

    def inicializar(self, num_mesas):
        with self._lock:
            self.conn.executescript(ESQUEMA_SQLITE)
            for i in range(1, num_mesas + 1):
                self.conn.execute(
                    "INSERT OR IGNORE INTO mesas (id, nombre, activa) VALUES (?, ?, 1)",
                    (i, f"Mesa {i}"),
                )
            self.conn.commit()


# ------------------------------------------------------------------- Postgres
class Postgres(BaseDatos):
    motor = "postgres"
    CANDADO = 727001  # id arbitrario del advisory lock

    def __init__(self, url: str):
        import psycopg
        from psycopg.rows import dict_row

        self._psycopg = psycopg
        self._dict_row = dict_row
        self.url = url
        self.conn = None
        self._lock = threading.RLock()

    def _conectar(self):
        if self.conn is None or self.conn.closed:
            self.conn = self._psycopg.connect(
                self.url, row_factory=self._dict_row, autocommit=False, prepare_threshold=None
            )
        return self.conn

    @staticmethod
    def _sql(sql: str) -> str:
        return sql.replace("?", "%s")

    def execute(self, sql, params=()):
        return self.conn.execute(self._sql(sql), params)

    def insertar(self, sql, params=()):
        return self.conn.execute(self._sql(sql) + " RETURNING id", params).fetchone()["id"]

    @contextmanager
    def _con_reintento(self, escribir: bool):
        with self._lock:
            for intento in range(2):
                try:
                    conn = self._conectar()
                    if escribir:
                        conn.execute("SELECT pg_advisory_xact_lock(%s)", (self.CANDADO,))
                    break
                except self._psycopg.OperationalError:
                    # conexión caída (p. ej. instancia serverless "congelada"): reconectar
                    self.conn = None
                    if intento:
                        raise
            try:
                yield self
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @contextmanager
    def transaccion(self):
        with self._con_reintento(escribir=True) as db:
            yield db

    @contextmanager
    def lectura(self):
        with self._con_reintento(escribir=False) as db:
            yield db

    def inicializar(self, num_mesas):
        with self.transaccion():
            for sentencia in ESQUEMA_POSTGRES.split(";"):
                if sentencia.strip():
                    self.conn.execute(sentencia)
            for i in range(1, num_mesas + 1):
                self.conn.execute(
                    "INSERT INTO mesas (id, nombre, activa) VALUES (%s, %s, 1) "
                    "ON CONFLICT (id) DO NOTHING",
                    (i, f"Mesa {i}"),
                )


def crear(db_path: str | None = None, database_url: str | None = None) -> BaseDatos:
    url = database_url if database_url is not None else config.DATABASE_URL
    if url:
        return Postgres(url)
    return SQLite(db_path or config.DB_PATH)
