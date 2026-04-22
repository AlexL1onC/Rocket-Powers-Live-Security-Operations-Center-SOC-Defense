import os
from pathlib import Path
from dotenv import load_dotenv
from cfenv import AppEnv
from hdbcli import dbapi

# 1. Buscador Absoluto del .env (A prueba de errores de ruta)
# Busca el .env en la misma carpeta del script, o en la carpeta superior
env_path = Path(__file__).resolve().parent / '.env'
if not env_path.exists():
    env_path = Path(__file__).resolve().parent.parent / '.env'

print(f"Buscando .env en: {env_path}")
load_dotenv(dotenv_path=env_path)

# 2. Diagnóstico Inmediato
vcap_raw = os.getenv("VCAP_SERVICES")
if not vcap_raw:
    print("❌ ERROR: VCAP_SERVICES sigue vacío. El archivo .env no se está leyendo.")
else:
    print("✅ VCAP_SERVICES detectado en memoria local.")

env = AppEnv()

def get_db_connection():
    # ... (El resto de tu código queda exactamente igual a partir de aquí)
    hana_service = env.get_service(label='hana')
    if not hana_service:
        raise ValueError("Credenciales no encontradas en VCAP_SERVICES.")
    
    creds = hana_service.credentials
    return dbapi.connect(
        address=creds['host'],
        port=int(creds['port']),
        user=creds['user'],
        password=creds['password'],
        encrypt="true",
        sslValidateCertificate="false"
    )

def create_master_table(conn):
    cursor = conn.cursor()
    table_name = "SOC_ANOMALY_LOGS"
    
    # 1. Idempotencia: Verificar si la tabla ya existe en el esquema del contenedor HDI
    # CURRENT_SCHEMA es el esquema aislado que te dio el servicio HDI
    check_sql = f"""
        SELECT COUNT(*) 
        FROM SYS.TABLES 
        WHERE SCHEMA_NAME = CURRENT_SCHEMA 
        AND TABLE_NAME = '{table_name}'
    """
    cursor.execute(check_sql)
    table_exists = cursor.fetchone()[0] > 0
    
    if table_exists:
        print(f"✅ La tabla {table_name} ya existe. Omitiendo creación (Idempotencia activa).")
    return
    
    drop_sql = f"DROP TABLE {table_name}"
    try:
        cursor.execute(drop_sql) #Temporalmente dejamos esto para limpiar la versión anterior de la tabla, pero en producción lo ideal es manejar esto con migraciones o versiones de tablas.
        print("Limpiando versión anterior de la tabla...")
    except:
        pass # Si no existe, no pasa nada

    # El nuevo DDL con todos tus campos + los requeridos por la IA
    ddl_sql = f"""
        CREATE COLUMN TABLE {table_name} (
            EVENT_HASH NVARCHAR(128) PRIMARY KEY,
            REQUEST_TIME_UTC TIMESTAMP,
            HEADERS_CONTENT_TYPE NVARCHAR(100),
            CLIENT_IP NVARCHAR(45),
            REGION_NAME NVARCHAR(50),
            SERVICE_ID NVARCHAR(100),
            LLM_PROVIDER NVARCHAR(50),
            LLM_MODEL_ID NVARCHAR(100),
            LLM_PROMPT_CATEGORY NVARCHAR(50),
            LLM_PROMPT NCLOB,
            LLM_TOTAL_TOKENS INTEGER,
            LLM_RESPONSE_TIME_MS INTEGER,
            LLM_COST_USD DECIMAL(10, 5),
            LLM_STATUS NVARCHAR(50),
            HTTP_STATUS_CODE INTEGER,
            
            -- Columnas de IA y Monitoreo Interno (NO BORRAR)
            PROMPT_VECTOR REAL_VECTOR(1536), 
            IS_ANOMALY TINYINT DEFAULT 0,
            DETECTION_LATENCY_MS INTEGER
        )
    """
    
    try:
        print(f"⚙️ Creando la tabla columnar {table_name}...")
        cursor.execute(ddl_sql)
        print("✅ ¡Tabla maestra creada exitosamente con soporte para Vector Engine!")
    except Exception as e:
        print(f"❌ Error al crear la tabla: {e}")
    finally:
        cursor.close()

if __name__ == "__main__":
    print("Iniciando setup de Base de Datos SAP HANA...")
    try:
        connection = get_db_connection()
        create_master_table(connection)
        connection.close()
    except Exception as err:
        print(f"Error crítico de conexión: {err}")