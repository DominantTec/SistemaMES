from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.health import router as health_router
from api.routers.line import router as lines_router
from api.routers.machine import router as machines_router
from api.routers.overview import router as overview_router
from api.routers.config import router as config_router

app = FastAPI(title="PCP API")

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