import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Ruta de la base de datos SQLite (se puede cambiar con la variable DB_PATH)
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "turnos.db"))

# Número de mesas de atención
NUM_MESAS = int(os.getenv("NUM_MESAS", "4"))

# Prefijo de los turnos (A-001, A-002, ...)
PREFIJO_TURNO = os.getenv("PREFIJO_TURNO", "A")

# Orígenes permitidos para CORS (frontend de Angular en desarrollo)
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:4200,http://127.0.0.1:4200"
).split(",")

# Carpeta con el build de Angular (opcional) para servirlo desde el mismo backend
FRONTEND_DIST = Path(
    os.getenv(
        "FRONTEND_DIST",
        str(BASE_DIR.parent / "frontend" / "dist" / "atencion-cliente" / "browser"),
    )
)
