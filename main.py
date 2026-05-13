import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from core.scheduler import scheduled_ingestion
from api.routes_health import router as health_router
from api.routes_export import router as export_router
from api.routes_metrics import router as metrics_router
from api.routes_visualization import router as visualization_router
from api.routes_assistant import router as assistant_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("shared_data", exist_ok=True)
    print("🚀 Servidor iniciado. Configurando planificador...", flush=True)

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        scheduled_ingestion,
        "interval",
        minutes=30,
        max_instances=1,
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=300,
    )
    scheduler.start()

    print("⚡ Lanzando ingesta inicial en segundo plano...", flush=True)
    thread = threading.Thread(target=scheduled_ingestion, daemon=True)
    thread.start()

    yield

    print("🛑 Apagando planificador...", flush=True)
    scheduler.shutdown()


app = FastAPI(title="Live SOC Defense Backend", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(health_router)
app.include_router(export_router)
app.include_router(metrics_router)
app.include_router(visualization_router)
app.include_router(assistant_router)