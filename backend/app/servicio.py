"""Lógica de negocio: fila de turnos y asignación automática a mesas.

Reglas:
  * "Tomar turno" agrega un turno al final de la fila (FIFO).
  * Cada vez que una mesa activa queda libre, toma automáticamente el
    turno más antiguo que esté en espera.
  * Si hay varias mesas libres se asignan en orden de número de mesa.
  * Una mesa pausada no recibe turnos nuevos, pero puede terminar el que tiene.
"""

import sqlite3
import threading
from datetime import datetime, timezone

from . import config, database


class ErrorNegocio(Exception):
    def __init__(self, mensaje: str, status: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _segundos(inicio: str | None, fin: str | None) -> float | None:
    if not inicio or not fin:
        return None
    return (datetime.fromisoformat(fin) - datetime.fromisoformat(inicio)).total_seconds()


class ServicioTurnos:
    def __init__(self, db_path: str | None = None, num_mesas: int | None = None):
        self.num_mesas = num_mesas or config.NUM_MESAS
        self.conn = database.conectar(db_path)
        database.inicializar(self.conn, self.num_mesas)
        # Un solo candado garantiza que dos mesas nunca tomen el mismo turno
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ util
    def _turno_dict(self, row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return {
            "id": row["id"],
            "numero": row["numero"],
            "codigo": row["codigo"],
            "estado": row["estado"],
            "mesa_id": row["mesa_id"],
            "creado_en": row["creado_en"],
            "llamado_en": row["llamado_en"],
            "finalizado_en": row["finalizado_en"],
        }

    def _asignar_pendientes(self) -> list[dict]:
        """Llena todas las mesas activas libres con los turnos en espera."""
        asignados = []
        mesas_libres = self.conn.execute(
            "SELECT id FROM mesas WHERE activa = 1 AND turno_id IS NULL ORDER BY id"
        ).fetchall()
        for mesa in mesas_libres:
            turno = self.conn.execute(
                "SELECT * FROM turnos WHERE estado = 'espera' ORDER BY id LIMIT 1"
            ).fetchone()
            if turno is None:
                break
            ahora = _ahora()
            self.conn.execute(
                "UPDATE turnos SET estado = 'atendiendo', mesa_id = ?, llamado_en = ? WHERE id = ?",
                (mesa["id"], ahora, turno["id"]),
            )
            self.conn.execute(
                "UPDATE mesas SET turno_id = ? WHERE id = ?", (turno["id"], mesa["id"])
            )
            asignados.append({"turno": turno["codigo"], "mesa_id": mesa["id"]})
        return asignados

    def _posicion_en_fila(self, turno_id: int) -> int | None:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM turnos WHERE estado = 'espera' AND id <= ?",
            (turno_id,),
        ).fetchone()
        return row["n"]

    def _obtener_turno(self, turno_id: int) -> dict:
        row = self.conn.execute("SELECT * FROM turnos WHERE id = ?", (turno_id,)).fetchone()
        if row is None:
            raise ErrorNegocio("El turno no existe", 404)
        turno = self._turno_dict(row)
        turno["posicion"] = (
            self._posicion_en_fila(turno_id) if turno["estado"] == "espera" else None
        )
        return turno

    # ------------------------------------------------------------- acciones
    def tomar_turno(self) -> dict:
        with self._lock, database.transaccion(self.conn):
            ultimo = self.conn.execute("SELECT MAX(numero) AS n FROM turnos").fetchone()["n"]
            numero = (ultimo or 0) + 1
            codigo = f"{config.PREFIJO_TURNO}-{numero:03d}"
            cur = self.conn.execute(
                "INSERT INTO turnos (numero, codigo, estado, creado_en) VALUES (?, ?, 'espera', ?)",
                (numero, codigo, _ahora()),
            )
            turno_id = cur.lastrowid
            self._asignar_pendientes()
            return self._obtener_turno(turno_id)

    def finalizar_atencion(self, mesa_id: int) -> dict:
        """La mesa termina con su cliente y automáticamente llama al siguiente."""
        with self._lock, database.transaccion(self.conn):
            mesa = self._mesa_o_error(mesa_id)
            if mesa["turno_id"] is None:
                raise ErrorNegocio(f"La {mesa['nombre']} no está atendiendo a nadie", 409)
            self.conn.execute(
                "UPDATE turnos SET estado = 'finalizado', finalizado_en = ? WHERE id = ?",
                (_ahora(), mesa["turno_id"]),
            )
            self.conn.execute("UPDATE mesas SET turno_id = NULL WHERE id = ?", (mesa_id,))
            asignados = self._asignar_pendientes()
            return {"mesa_id": mesa_id, "asignados": asignados}

    def cambiar_estado_mesa(self, mesa_id: int, activa: bool) -> dict:
        with self._lock, database.transaccion(self.conn):
            self._mesa_o_error(mesa_id)
            self.conn.execute(
                "UPDATE mesas SET activa = ? WHERE id = ?", (1 if activa else 0, mesa_id)
            )
            asignados = self._asignar_pendientes() if activa else []
            return {"mesa_id": mesa_id, "activa": activa, "asignados": asignados}

    def cancelar_turno(self, turno_id: int) -> dict:
        """Quita de la fila un turno que no se presentó."""
        with self._lock, database.transaccion(self.conn):
            turno = self._obtener_turno(turno_id)
            if turno["estado"] != "espera":
                raise ErrorNegocio("Solo se pueden cancelar turnos en espera", 409)
            self.conn.execute(
                "UPDATE turnos SET estado = 'finalizado', finalizado_en = ? WHERE id = ?",
                (_ahora(), turno_id),
            )
            return {"cancelado": turno["codigo"]}

    def reiniciar(self) -> None:
        with self._lock, database.transaccion(self.conn):
            self.conn.execute("UPDATE mesas SET turno_id = NULL, activa = 1")
            self.conn.execute("DELETE FROM turnos")
            self.conn.execute("DELETE FROM sqlite_sequence WHERE name = 'turnos'")

    # ------------------------------------------------------------- consultas
    def consultar_turno(self, turno_id: int) -> dict:
        with self._lock:
            return self._obtener_turno(turno_id)

    def _mesa_o_error(self, mesa_id: int) -> sqlite3.Row:
        mesa = self.conn.execute("SELECT * FROM mesas WHERE id = ?", (mesa_id,)).fetchone()
        if mesa is None:
            raise ErrorNegocio("La mesa no existe", 404)
        return mesa

    def estado(self) -> dict:
        with self._lock:
            mesas = []
            for m in self.conn.execute("SELECT * FROM mesas ORDER BY id"):
                turno = None
                if m["turno_id"] is not None:
                    turno = self._turno_dict(
                        self.conn.execute(
                            "SELECT * FROM turnos WHERE id = ?", (m["turno_id"],)
                        ).fetchone()
                    )
                mesas.append(
                    {
                        "id": m["id"],
                        "nombre": m["nombre"],
                        "activa": bool(m["activa"]),
                        "ocupada": turno is not None,
                        "turno": turno,
                    }
                )

            fila = [
                self._turno_dict(r)
                for r in self.conn.execute(
                    "SELECT * FROM turnos WHERE estado = 'espera' ORDER BY id"
                )
            ]

            llamados = [
                {"codigo": r["codigo"], "mesa_id": r["mesa_id"], "llamado_en": r["llamado_en"]}
                for r in self.conn.execute(
                    "SELECT * FROM turnos WHERE llamado_en IS NOT NULL "
                    "ORDER BY llamado_en DESC, id DESC LIMIT 6"
                )
            ]

            atendidos = self.conn.execute(
                "SELECT creado_en, llamado_en, finalizado_en FROM turnos "
                "WHERE estado = 'finalizado' AND llamado_en IS NOT NULL"
            ).fetchall()
            esperas = [_segundos(r["creado_en"], r["llamado_en"]) for r in atendidos]
            atenciones = [_segundos(r["llamado_en"], r["finalizado_en"]) for r in atendidos]

            def promedio(valores):
                valores = [v for v in valores if v is not None]
                return round(sum(valores) / len(valores), 1) if valores else None

            return {
                "mesas": mesas,
                "fila": fila,
                "ultimos_llamados": llamados,
                "estadisticas": {
                    "en_espera": len(fila),
                    "en_atencion": sum(1 for m in mesas if m["ocupada"]),
                    "atendidos": len(atendidos),
                    "espera_promedio_seg": promedio(esperas),
                    "atencion_promedio_seg": promedio(atenciones),
                },
                "actualizado_en": _ahora(),
            }
