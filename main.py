# main.py
import os

from dotenv import load_dotenv

from data_ingestion.data_extraction import download_all_pages
from data_ingestion.processor import clean_and_convert_to_parquet

load_dotenv()

def run_pipeline():
    print("Iniciando Pipeline de Defensa SOC...")
    
    # 1. Captura (Tu misión actual)
    #raw_data = download_all_pages() 
    raw_data = os.getenv('OUTPUT_FOLDER')# Ya descargaste el JSON gigante, así que vamos directo a procesar ese archivo

    # 2. Procesamiento (Siguiente paso)
    #clean_df = clean_and_convert_to_parquet(raw_data, os.getenv("OUTPUT_PARQUET_FOLDER"))
    parquet_data = os.getenv("OUTPUT_PARQUET_FOLDER") # Ya procesaste el Parquet, así que vamos directo a ese archivo
    # 3. Alerta (Webhook - Se activa el 27 de abril) [cite: 438]
    # send_alert_if_needed(clean_df)

if __name__ == "__main__":
    run_pipeline()