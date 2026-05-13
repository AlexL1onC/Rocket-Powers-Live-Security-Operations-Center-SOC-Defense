import requests
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Load API configuration from environment
API_URL = os.getenv("API_URL")

headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {os.getenv('API_KEY')}"
}

API_URL = os.getenv("API_URL")

def download_all_pages():
    all_records = []
    current_page = 1
    total_pages = 1  # Empezamos con 1, el API nos dirá el resto
    
    while current_page <= total_pages:
        print(f"Consultando página {current_page}...")
        
        params = {"page": current_page}
        response = requests.get(API_URL, headers=headers, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            break
            
        json_response = response.json()
        
        # ACTUALIZACIÓN DE METADATOS:
        # El API te dice cuántas páginas existen realmente en cada respuesta
        total_pages = json_response.get("total_pages", 1)
        
        # EXTRACCIÓN DE DATOS REALES:
        # Aquí es donde estaba tu error. Debes entrar a la llave 'data'
        records = json_response.get("data", [])
        all_records.extend(records)
        
        print(f"Capturados {len(records)} registros. (Total acumulado: {len(all_records)})")
        
        current_page += 1
        time.sleep(0.3) # Cortesía con el servidor de SAP

    # Guardar el JSON gigante final
    with open(f"{os.getenv('OUTPUT_FOLDER')}", "w") as f:
        json.dump(all_records, f)