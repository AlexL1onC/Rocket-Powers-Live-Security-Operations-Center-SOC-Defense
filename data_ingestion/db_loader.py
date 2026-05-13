import os
import pandas as pd
from hdbcli import dbapi
from cfenv import AppEnv
from dotenv import load_dotenv

load_dotenv()

def get_hana_connection():
    """Establece conexión usando cfenv para compatibilidad con SAP BTP."""
    env = AppEnv()
    hana_service_name = os.getenv("HANA_SERVICE_NAME")

    if hana_service_name:
        hana_service = env.get_service(name=hana_service_name)
    else:
        hana_service = env.get_service(label="hana")

    if hana_service:
        creds = hana_service.credentials
        host = creds.get("host")
        port = creds.get("port")
        user = creds.get("user")
        password = creds.get("password")
    else:
        # Solo para ejecución local sin VCAP_SERVICES
        host = os.getenv("HANA_HOST") or os.getenv("host")
        port = os.getenv("HANA_PORT") or os.getenv("port")
        user = os.getenv("HANA_USER") or os.getenv("user")
        password = os.getenv("HANA_PASSWORD") or os.getenv("password")

    if not all([host, port, user, password]):
        raise RuntimeError(
            "No se pudieron obtener credenciales de HANA. "
            "En Cloud Foundry revisa el binding del servicio; "
            "en local revisa HANA_HOST, HANA_PORT, HANA_USER y HANA_PASSWORD."
        )

    return dbapi.connect(
        address=host,
        port=int(port),
        user=user,
        password=password,
        encrypt="true",
        sslValidateCertificate="false"
    )

def load_data_to_hana(df):
    if df.empty:
        print("El DataFrame está vacío.")
        return

    mapeo = {
        "CLIENT_IP": "SOURCE_IP",
        "REQUEST_TIME_UTC": "TIMESTAMP",
        "REGION_NAME": "LOCATION",
        # Agrega aquí cualquier otro nombre que necesite traducirse
    }
    
    # Aplicamos el renombre (ignore_errors=True por si ya tienen el nombre correcto)
    df = df.rename(columns=mapeo)

    if "TIMESTAMP" in df.columns:
        df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
    # 1. ESQUEMA UNIFICADO (Debe ser idéntico en CREATE e INSERT)
    expected_columns = [
        "EVENT_HASH", "HEADERS_CONTENT_TYPE", 
        "SERVICE_ID", "LLM_PROVIDER", "LLM_MODEL_ID", 
        "LLM_PROMPT_CATEGORY", "LLM_PROMPT", "LLM_TOTAL_TOKENS", 
        "LLM_RESPONSE_TIME_MS", "LLM_COST_USD", "LLM_STATUS", "HTTP_STATUS_CODE",
        "SOURCE_IP", "TIMESTAMP", "LOCATION"
    ]

    for col in expected_columns:
        if col not in df.columns:
            print(f"⚠️ Columna faltante en el DataFrame: {col}. Se llenará con nulos.")
            df[col] = None

    df_to_insert = df[expected_columns].copy()
    df_to_insert = df_to_insert.where(pd.notnull(df_to_insert), None)
    data_tuples = list(df_to_insert.itertuples(index=False, name=None))

    # 2. SQL DE CREACIÓN (Solo si no existe)
    create_table_sql = f"""
    CREATE COLUMN TABLE "SOC_ANOMALY_LOGS" (
        "EVENT_HASH" NVARCHAR(64) PRIMARY KEY,
        "TIMESTAMP" TIMESTAMP,
        "SOURCE_IP" NVARCHAR(45),
        "LOCATION" NVARCHAR(100),
        "SERVICE_ID" NVARCHAR(50),
        "LLM_PROVIDER" NVARCHAR(50),
        "LLM_MODEL_ID" NVARCHAR(50),
        "LLM_PROMPT" NCLOB,
        "LLM_TOTAL_TOKENS" INTEGER,
        "LLM_COST_USD" DOUBLE,
        "LLM_RESPONSE_TIME_MS" INTEGER,
        "HTTP_STATUS_CODE" INTEGER,
        "ANOMALY_SCORE" DOUBLE,
        "LABEL" NVARCHAR(20),
        "HEADERS_CONTENT_TYPE" NVARCHAR(100),
        "LLM_PROMPT_CATEGORY" NVARCHAR(50),
        "LLM_STATUS" NVARCHAR(50)
    )
    """

    sql_upsert = f"""
        UPSERT "SOC_ANOMALY_LOGS" ({', '.join(df_to_insert.columns)})
        VALUES ({', '.join(['?'] * len(df_to_insert.columns))})
        WITH PRIMARY KEY
    """

    conn = get_hana_connection()
    cursor = conn.cursor()

    try:
        print(f"Iniciando Batch Insert de {len(data_tuples)} registros...", flush=True)
        # INTENTO 1: Insertar directamente
        try:
            cursor.executemany(sql_upsert, data_tuples)
            conn.commit()
            print("--- ✅ CICLO COMPLETADO CON ÉXITO ---", flush=True)
        except Exception as e:
            # Si falla, intentamos crear la tabla por si acaso no existe
            print(f"⚠️ Posible falta de tabla o error de esquema. Intentando crear/verificar tabla...", flush=True)
            try:
                cursor.execute(create_table_sql)
                conn.commit()
                print("✅ Tabla creada o verificada.", flush=True)
            except Exception:
                print("ℹ️ La tabla ya existía o no se pudo crear, reintentando insert...", flush=True)
            
            # INTENTO 2: Después de intentar crearla
            cursor.executemany(sql_upsert, data_tuples)
            conn.commit()
            print("--- ✅ CICLO COMPLETADO TRAS REPARACIÓN ---", flush=True)

    except Exception as final_error:
        conn.rollback()
        print(f"❌ Error definitivo en la base de datos: {final_error}", flush=True)
    finally:
        cursor.close()
        conn.close()