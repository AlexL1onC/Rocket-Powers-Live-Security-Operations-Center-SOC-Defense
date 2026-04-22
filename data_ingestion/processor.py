import pandas as pd
import json
import os

def clean_and_convert_to_parquet(json_file_path, parquet_output_path):
    print(f"Leyendo archivo JSON: {json_file_path}...")
    
    # 1. Carga de datos
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # 2. LIMPIEZA CRÍTICA
    print("Iniciando limpieza de datos...")
    
    # Convertir timestamps (Importante hacerlo antes del rename)
    date_cols = ["@timestamp", "request_time_utc"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Manejo de Nulos
    string_cols = df.select_dtypes(include=['object']).columns
    df[string_cols] = df[string_cols].fillna("Unknown")
    
    numeric_cols = df.select_dtypes(include=['number']).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)

    # --- NUEVO PASO: MAPEO PARA SAP HANA ---
    print("Estandarizando columnas para SAP HANA...")
    
    # Mapeamos los nombres del JSON (izquierda) a los de tu DDL en HANA (derecha)
    column_mapping = {
        "event_hash": "EVENT_HASH",
        "request_time_utc": "REQUEST_TIME_UTC",
        "client_ip": "CLIENT_IP",
        "region_name": "REGION_NAME",
        "service_id": "SERVICE_ID",
        "llm_provider": "LLM_PROVIDER",
        "llm_model_id": "LLM_MODEL_ID",
        "llm_prompt_category": "LLM_PROMPT_CATEGORY",
        "llm_prompt": "LLM_PROMPT",
        "llm_total_tokens": "LLM_TOTAL_TOKENS",
        "llm_response_time_ms": "LLM_RESPONSE_TIME_MS",
        "llm_cost_usd": "LLM_COST_USD",
        "llm_status": "LLM_STATUS",
        "http_status_code": "HTTP_STATUS_CODE"
    }
    
    # Renombramos las que existan
    df.rename(columns=column_mapping, inplace=True)

    # Creamos las columnas que falten como nulas para que el db_loader no truene
    db_columns = [
        "EVENT_HASH", "REQUEST_TIME_UTC", "HEADERS_CONTENT_TYPE", "CLIENT_IP", 
        "REGION_NAME", "SERVICE_ID", "LLM_PROVIDER", "LLM_MODEL_ID", 
        "LLM_PROMPT_CATEGORY", "LLM_PROMPT", "LLM_TOTAL_TOKENS", 
        "LLM_RESPONSE_TIME_MS", "LLM_COST_USD", "LLM_STATUS", "HTTP_STATUS_CODE"
    ]
    
    for col in db_columns:
        if col not in df.columns:
            df[col] = None
    
    # Aseguramos que HTTP_STATUS_CODE sea numérico
    if "HTTP_STATUS_CODE" in df.columns:
        # Convertimos a número, los errores se vuelven NaN, y luego los NaN se vuelven 0
        df["HTTP_STATUS_CODE"] = pd.to_numeric(df["HTTP_STATUS_CODE"], errors='coerce').fillna(0).astype(int)

    # Aseguramos que LLM_TOTAL_TOKENS y LLM_RESPONSE_TIME_MS también sean enteros
    for col in ["LLM_TOTAL_TOKENS", "LLM_RESPONSE_TIME_MS"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    # Y para los decimales (Costos)
    if "LLM_COST_USD" in df.columns:
        df["LLM_COST_USD"] = pd.to_numeric(df["LLM_COST_USD"], errors='coerce').fillna(0.0)

    # Seleccionamos solo las columnas que van a la BD para el Parquet final
    df = df[db_columns]
    # ---------------------------------------

    # 4. EXPORTAR A PARQUET
    df.to_parquet(parquet_output_path, engine='pyarrow', compression='snappy', index=False)
    
    print(f"Conversión completada. Archivo guardado en: {parquet_output_path}")
    print(f"Registros procesados: {len(df)}")
    return df

if __name__ == "__main__":
    # Ruta del JSON que ya descargaste
    input_json = os.getenv("OUTPUT_FOLDER")
    output_parquet = os.getenv("OUTPUT_PARQUET_FOLDER")
    
    clean_and_convert_to_parquet(input_json, output_parquet)