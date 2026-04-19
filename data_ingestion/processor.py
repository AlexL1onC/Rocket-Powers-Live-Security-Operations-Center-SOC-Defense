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
    
    # Eliminar columnas totalmente vacías o irrelevantes (como _ignored o _score si son nulas)
    cols_to_drop = [col for col in ["_ignored", "_score"] if col in df.columns]
    df.drop(columns=cols_to_drop, inplace=True, errors='ignore')
    
    # Convertir timestamps a objetos datetime reales de Python
    # Esto es vital para que SAP HANA lo reconozca como fecha y no como texto
    date_cols = ["@timestamp", "@event_time_requested", "request_time_utc"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Manejo de Nulos: 
    # Para strings, mejor usar un texto vacío o 'N/A' para evitar errores en el modelo de IA
    string_cols = df.select_dtypes(include=['object']).columns
    df[string_cols] = df[string_cols].fillna("Unknown")
    
    # Para números (costos, tokens), llenar con 0
    numeric_cols = df.select_dtypes(include=['number']).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)
    
    # 3. OPTIMIZACIÓN DE TIPOS
    # Reducir el tamaño de memoria convirtiendo columnas repetitivas en 'category'
    categorical_candidates = ["llm_provider", "llm_status", "region_name", "sap_source_type"]
    for col in categorical_candidates:
        if col in df.columns:
            df[col] = df[col].astype('category')

    # 4. EXPORTAR A PARQUET
    # Usamos compresión 'snappy' que es el estándar balanceado entre velocidad y tamaño
    df.to_parquet(parquet_output_path, engine='pyarrow', compression='snappy', index=False)
    
    print(f"Conversión completada. Archivo guardado en: {parquet_output_path}")
    print(f"Registros procesados: {len(df)}")
    return df

if __name__ == "__main__":
    # Ruta del JSON que ya descargaste
    input_json = os.getenv("OUTPUT_FOLDER")
    output_parquet = os.getenv("OUTPUT_PARQUET_FOLDER")
    
    clean_and_convert_to_parquet(input_json, output_parquet)