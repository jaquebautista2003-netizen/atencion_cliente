"""API REST + WebSocket del sistema de turnos.

Ejecutar:  uvicorn app.main:app --reload --port 8000
Docs:      http://localhost:8000/docs
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import config
from .servicio import ErrorNegocio, ServicioTurnos


class GestorConexiones:
    """Mantiene los WebSockets abiertos y les envía el estado en tiempo real."""

    def __init__(self):
        self.activas: set[WebSocket] = set()

    async def conectar(self, ws: WebSocket):
        await ws.accept()
        self.activas.add(ws)

    def desconectar(self, ws: WebSocket):
        self.activas.discard(ws)

    async def difundir(self, mensaje: dict):
        caidas = []
        for ws in list(self.activas):
            try:
                await ws.send_json(mensaje)
            except Exception:
                caidas.append(ws)
        for ws in caidas:
            self.desconectar(ws)


def crear_app(servicio: ServicioTurnos | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.servicio = servicio or ServicioTurnos()
        yield

    app = FastAPI(
        title="Atención a Clientes - Sistema de Turnos",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    gestor = GestorConexiones()

    def svc(request: Request) -> ServicioTurnos:
        return request.app.state.servicio

    async def notificar(request: Request, evento: str, datos: dict | None = None):
        estado = await asyncio.to_thread(svc(request).estado)
        await gestor.difundir({"evento": evento, "datos": datos or {}, "estado": estado})

    @app.exception_handler(ErrorNegocio)
    async def manejar_error(_: Request, exc: ErrorNegocio):
        return JSONResponse(status_code=exc.status, content={"detail": exc.mensaje})

    # ------------------------------------------------------------- endpoints
    @app.get("/api/salud")
    async def salud():
        return {"ok": True}

    @app.get("/api/estado")
    async def estado(request: Request):
        return await asyncio.to_thread(svc(request).estado)

    @app.post("/api/turnos", status_code=201)
    async def tomar_turno(request: Request):
        turno = await asyncio.to_thread(svc(request).tomar_turno)
        await notificar(request, "turno_creado", {"turno": turno})
        return turno

    @app.get("/api/turnos/{turno_id}")
    async def consultar_turno(turno_id: int, request: Request):
        return await asyncio.to_thread(svc(request).consultar_turno, turno_id)

    @app.delete("/api/turnos/{turno_id}")
    async def cancelar_turno(turno_id: int, request: Request):
        res = await asyncio.to_thread(svc(request).cancelar_turno, turno_id)
        await notificar(request, "turno_cancelado", res)
        return res

    @app.post("/api/mesas/{mesa_id}/finalizar")
    async def finalizar(mesa_id: int, request: Request):
        res = await asyncio.to_thread(svc(request).finalizar_atencion, mesa_id)
        await notificar(request, "mesa_liberada", res)
        return res

    class CambioMesa(BaseModel):
        activa: bool

    @app.patch("/api/mesas/{mesa_id}")
    async def cambiar_mesa(mesa_id: int, cambio: CambioMesa, request: Request):
        res = await asyncio.to_thread(svc(request).cambiar_estado_mesa, mesa_id, cambio.activa)
        await notificar(request, "mesa_actualizada", res)
        return res

    @app.post("/api/reiniciar")
    async def reiniciar(request: Request):
        await asyncio.to_thread(svc(request).reiniciar)
        await notificar(request, "reinicio")
        return {"ok": True}

    @app.websocket("/ws")
    async def websocket(ws: WebSocket):
        await gestor.conectar(ws)
        try:
            estado = await asyncio.to_thread(ws.app.state.servicio.estado)
            await ws.send_json({"evento": "conectado", "datos": {}, "estado": estado})
            while True:
                await ws.receive_text()  # mantener viva la conexión (ping del cliente)
        except WebSocketDisconnect:
            pass
        finally:
            gestor.desconectar(ws)

    # ---------------------------------------- frontend compilado (opcional)
    dist = config.FRONTEND_DIST
    if dist.is_dir():
        raiz = dist.resolve()

        @app.get("/{ruta:path}", include_in_schema=False)
        async def spa(ruta: str):
            if ruta.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "No encontrado"})
            archivo = (raiz / ruta).resolve()
            if ruta and archivo.is_file() and raiz in archivo.parents:
                return FileResponse(archivo)
            return FileResponse(dist / "index.html")

    return app


app = crear_app()
