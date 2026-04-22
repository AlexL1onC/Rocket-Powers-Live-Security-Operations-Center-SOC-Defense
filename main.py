import os
import threading
import pandas as pd
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from cfenv import AppEnv
from hdbcli import dbapi


# 1. CARGAR VARIABLES AL INICIO
load_dotenv()

# Importaciones de tus módulos
from data_ingestion.data_extraction import download_all_pages
from data_ingestion.processor import clean_and_convert_to_parquet
from data_ingestion.db_loader import load_data_to_hana

def get_hana_connection():
    """Establece conexión usando cfenv para compatibilidad con SAP BTP."""
    env = AppEnv()
    hana_service = env.get_service(label='hana')
    
    if hana_service:
        # Modo Producción (BTP)
        creds = hana_service.credentials
        host = creds.get('host')
        port = creds.get('port')
        user = creds.get('user')
        password = creds.get('password')
    else:
        # Modo Local (Fallback)
        host = os.getenv("HANA_HOST") or os.getenv("host")
        port = os.getenv("HANA_PORT") or os.getenv("port")
        user = os.getenv("HANA_USER") or os.getenv("user")
        password = os.getenv("HANA_PASSWORD") or os.getenv("password")

    return dbapi.connect(
        address=host,
        port=int(port),
        user=user,
        password=password,
        encrypt="true",
        sslValidateCertificate="false"
    )


def scheduled_ingestion():
    # Paso 0: Asegurar que la carpeta de trabajo exista en el contenedor de SAP
    os.makedirs("shared_data", exist_ok=True) 

    json_path = "shared_data/raw_logs.json"
    parquet_path = "shared_data/processed_logs.parquet"
    print("--- ⚡ Iniciando ciclo de Defensa SOC ---")
    try:
        # Paso 1: Extracción
        print("Paso 1: Extrayendo datos de la API...")
        download_all_pages()
        
        # Paso 2: Procesamiento
        print("Paso 2: Procesando y mapeando columnas...")
        registros = clean_and_convert_to_parquet(json_path, parquet_path)
        print(f"Registros listos: {registros}", flush=True)
        
        # Paso 3: Carga a HANA
        print("Paso 3: Cargando a SAP HANA...", flush=True)
        load_data_to_hana(registros)
        
        print("--- ✅ Ciclo completado con éxito ---", flush=True)
    except Exception as e:
        print(f"❌ Error crítico en el ciclo: {e}", flush=True)



@asynccontextmanager
async def lifespan(app: FastAPI):
# 1. Preparación inicial
    os.makedirs("shared_data", exist_ok=True)
    print("🚀 Servidor iniciado. Configurando planificador...", flush=True)
    
    # 2. Configuración del Scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        scheduled_ingestion, 
        'interval', 
        minutes=30, 
        max_instances=1,
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=300  # Dejamos solo uno
    )
    scheduler.start()
    
    # 3. Lanzamiento en Hilo (Thread) para no bloquear el Health Check de SAP
    print("⚡ Lanzando ingesta inicial en segundo plano...", flush=True)
    thread = threading.Thread(target=scheduled_ingestion, daemon=True)
    thread.start()

    yield  # El servidor FastAPI corre aquí
    
    # Lógica al APAGAR
    print("🛑 Apagando planificador...")
    scheduler.shutdown()

# VINCULAR EL LIFESPAN AQUÍ (Crucial)
app = FastAPI(title="Live SOC Defense Backend", lifespan=lifespan)

@app.get("/")
def health_check():
    return {"status": "SOC Ingestion Service is RUNNING"}