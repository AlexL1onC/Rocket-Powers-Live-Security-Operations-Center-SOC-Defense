import os
import pandas as pd
from hdbcli import dbapi
from cfenv import AppEnv
from dotenv import load_dotenv

load_dotenv()

def get_hana_connection():
    env = AppEnv()
    hana_service = env.get_service(label='hana')
    
    if not hana_service:
        print("⚠️ VCAP_SERVICES no encontrado, usando variables locales...")
        creds = {
            'host': os.getenv("HANA_HOST"),
            'port': os.getenv("HANA_PORT"),
            'user': os.getenv("HANA_USER"),
            'password': os.getenv("HANA_PASSWORD")
        }
    else:
        print(f"✅ Usando credenciales de servicio: {hana_service.name}")
        creds = hana_service.credentials

    return dbapi.connect(
        address=creds.get('host'),
        port=int(creds.get('port')),
        user=creds.get('user'),
        password=creds.get('password'),
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
    # 1. ESQUEMA UNIFICADO (Debe ser idéntico en CREATE e INSERT)
    expected_columns = [
        "EVENT_HASH", "ID", "SOURCE_IP", "DESTINATION_IP", "PROTOCOL", 
        "SOURCE_PORT", "DESTINATION_PORT", "PACKET_SIZE", "FLAGS", 
        "TIMESTAMP", "ANOMALY_SCORE", "LABEL", "LOCATION", 
        "USER_AGENT", "HTTP_STATUS_CODE"
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
        "ID" BIGINT,
        "SOURCE_IP" NVARCHAR(45),
        "DESTINATION_IP" NVARCHAR(45),
        "PROTOCOL" NVARCHAR(10),
        "SOURCE_PORT" INTEGER,
        "DESTINATION_PORT" INTEGER,
        "PACKET_SIZE" INTEGER,
        "FLAGS" NVARCHAR(20),
        "TIMESTAMP" TIMESTAMP,
        "ANOMALY_SCORE" DOUBLE,
        "LABEL" NVARCHAR(20),
        "LOCATION" NVARCHAR(100),
        "USER_AGENT" NVARCHAR(256),
        "HTTP_STATUS_CODE" INTEGER
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