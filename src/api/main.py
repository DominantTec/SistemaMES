import asyncio
import json
import math

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers.health import router as health_router
from api.routers.line import router as lines_router
from api.routers.machine import router as machines_router
from api.routers.overview import router as overview_router
from api.routers.config import router as config_router
from api.routers.historico import router as historico_router
from api.routers.ordens import router as ordens_router
from api.routers.alertas import router as alertas_router
from api.routers.manutencao import router as manutencao_router
from api.services.queries import ensure_ordens_table, recalcular_turno_ordens_ativas, setup_ghost_data


class SafeJSONResponse(JSONResponse):
    """JSONResponse que converte NaN/Inf para null antes de serializar."""

    @staticmethod
    def _sanitize(obj):
        if isinstance(obj, dict):
            return {k: SafeJSONResponse._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [SafeJSONResponse._sanitize(v) for v in obj]
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj

    def render(self, content) -> bytes:
        return json.dumps(
            self._sanitize(content),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")


app = FastAPI(title="PCP API", default_response_class=SafeJSONResponse)


async def _background_recalc():
    """Roda recalcular_turno_ordens_ativas a cada 2 s independente de WebSockets abertos."""
    while True:
        try:
            recalcular_turno_ordens_ativas()
        except Exception:
            pass
        await asyncio.sleep(2)


@app.on_event("startup")
async def startup():
    try:
        ensure_ordens_table()
    except Exception:
        pass  # Não bloqueia o boot caso DB ainda esteja subindo
    try:
        setup_ghost_data()
    except Exception:
        pass
    asyncio.create_task(_background_recalc())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # DEV
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(lines_router)
app.include_router(machines_router)
app.include_router(overview_router)
app.include_router(config_router)
app.include_router(historico_router)
app.include_router(ordens_router)
app.include_router(alertas_router)
app.include_router(manutencao_router)