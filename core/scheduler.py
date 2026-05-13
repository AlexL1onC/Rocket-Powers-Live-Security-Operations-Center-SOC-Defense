import os

from core.hana_autostart import start_hana_if_needed, wait_for_hana_ready
from data_ingestion.data_extraction import download_all_pages
from data_ingestion.processor import clean_and_convert_to_parquet
from data_ingestion.db_loader import load_data_to_hana
from ml.detector import run_anomaly_detection



def scheduled_ingestion():
    # Paso 0: Asegurar que la carpeta de trabajo exista en el contenedor de SAP
    os.makedirs("shared_data", exist_ok=True) 

    json_path = "shared_data/raw_logs.json"
    parquet_path = "shared_data/processed_logs.parquet"
    print("--- ⚡ Iniciando ciclo de Defensa SOC ---")
    try:

        start_hana_if_needed()

        if not wait_for_hana_ready():
            print("❌ Se cancela el ciclo porque HANA no está disponible.", flush=True)
            return
        
        # Paso 1: Extracción
        print("Paso 1: Extrayendo datos de la API...")
        download_all_pages()
        
        # Paso 2: Procesamiento
        print("Paso 2: Procesando y mapeando columnas...")
        registros = clean_and_convert_to_parquet(json_path, parquet_path)
        print(f"Registros listos: {len(registros)}", flush=True)
        
        # Paso 3: Carga a HANA
        print("Paso 3: Cargando a SAP HANA...", flush=True)
        load_data_to_hana(registros)
        
        run_anomaly_detection()


        print("--- ✅ Ciclo completado con éxito ---", flush=True)
    except Exception as e:
        print(f"❌ Error crítico en el ciclo: {e}", flush=True)
