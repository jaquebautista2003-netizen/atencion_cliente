# Atención a Clientes · Sistema de turnos

Aplicación de gestión de atención a clientes con **fila de turnos** y **4 mesas**.
El cliente presiona **Tomar turno**; conforme cada mesa se desocupa, toma automáticamente
el siguiente turno de la fila (orden de llegada). Todo se actualiza en tiempo real.

- **Backend:** Python 3.11+ · FastAPI · SQLite · WebSocket
- **Frontend:** Angular 20 (standalone components + signals)

## Vistas

| Ruta        | Para quién            | Qué hace |
|-------------|-----------------------|----------|
| `/`         | Operador / encargado  | Botón *Tomar turno*, las 4 mesas con *Finalizar atención* y *Pausar*, fila de espera, estadísticas y reinicio de jornada |
| `/kiosco`   | Cliente               | Botón grande para sacar turno; muestra el ticket, su posición en la fila o la mesa asignada |
| `/pantalla` | TV de la sala         | Qué turno está en cada mesa, próximos turnos y aviso con sonido + voz ("Turno A 5, pase a la mesa 2") |

## Reglas de asignación

1. *Tomar turno* genera `A-001`, `A-002`, … y lo agrega al final de la fila.
2. Si hay una mesa libre, el turno pasa directo a ella (se llenan en orden Mesa 1 → 4).
3. Al presionar **Finalizar atención** la mesa queda libre y toma el siguiente turno de la fila.
4. Una mesa **pausada** termina a su cliente actual pero no recibe turnos nuevos.
5. Un turno en espera que no se presentó se puede quitar de la fila (×).

## Ejecutar en desarrollo

### 1. Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Documentación interactiva de la API: http://localhost:8000/docs

### 2. Frontend
```bash
cd frontend
npm install
npm start
```
Abrir http://localhost:4200 (el proxy de Angular redirige `/api` y `/ws` al backend).

## Ejecutar en producción (un solo servidor)

```bash
cd frontend && npm install && npm run build
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```
El backend detecta `frontend/dist/atencion-cliente/browser` y sirve la app en http://localhost:8000.
Desde otras computadoras / la TV de la misma red: `http://IP-DEL-SERVIDOR:8000/pantalla`.

## API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET    | `/api/estado` | Mesas, fila, últimos llamados y estadísticas |
| POST   | `/api/turnos` | Tomar turno |
| GET    | `/api/turnos/{id}` | Consultar un turno (incluye posición en fila) |
| DELETE | `/api/turnos/{id}` | Quitar de la fila un turno en espera |
| POST   | `/api/mesas/{id}/finalizar` | La mesa termina y llama al siguiente |
| PATCH  | `/api/mesas/{id}` | `{"activa": false}` pausa / `true` reanuda |
| POST   | `/api/reiniciar` | Borra turnos y reinicia numeración |
| WS     | `/ws` | Envía el estado completo en cada cambio |

## Configuración (variables de entorno del backend)

| Variable | Default | |
|----------|---------|---|
| `NUM_MESAS` | `4` | Número de mesas |
| `PREFIJO_TURNO` | `A` | Letra de los turnos |
| `DB_PATH` | `backend/turnos.db` | Archivo SQLite |
| `CORS_ORIGINS` | `http://localhost:4200` | Orígenes permitidos |

## Pruebas
```bash
cd backend && pytest -q
```

## Estructura
```
backend/
  app/
    main.py       API REST + WebSocket (+ sirve el build de Angular)
    servicio.py   Lógica de fila y asignación a mesas
    database.py   Esquema SQLite
    config.py     Configuración
  tests/          Pruebas (pytest)
frontend/
  src/app/
    core/         Servicio de turnos (HTTP + WebSocket), modelos, utilidades
    paginas/
      panel/      Panel del operador
      kiosco/     Pantalla para que el cliente tome turno
      pantalla/   Pantalla de TV con anuncio por voz
```
