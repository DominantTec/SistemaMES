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