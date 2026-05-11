import json
import os
import threading
import joblib
import pandas as pd
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from cfenv import AppEnv
from hdbcli import dbapi
import numpy as np


# 1. CARGAR VARIABLES AL INICIO
load_dotenv()

# Importaciones de tus módulos
from data_ingestion.data_extraction import download_all_pages
from data_ingestion.processor import clean_and_convert_to_parquet
from data_ingestion.db_loader import load_data_to_hana


MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'soc_anomaly_ensemble.joblib')
artifact = joblib.load(MODEL_PATH)
model = artifact["iforest_model"]
MAX_ALERTS_PER_CYCLE = int(os.getenv("MAX_ALERTS_PER_CYCLE", "5"))
ALERT_SCORE_THRESHOLD = float(os.getenv("ALERT_SCORE_THRESHOLD", "-0.05"))

ALERT_API_URL = os.getenv("ALERT_API_URL")
API_TOKEN = os.getenv("ALERT_API_TOKEN")
TEAM_NAME = os.getenv("TEAM_NAME", "team_alpha")

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


def assign_severity(row):
    if row["LABEL"] != "Anomalia":
        return "Normal"

    ctx = get_risk_context(row)
    score = ctx["score"]

    if score <= -0.05 and ctx["risk_signal"]:
        return "High"

    if score <= -0.03 and ctx["risk_signal"]:
        return "Medium"

    return "Low"

def run_anomaly_detection():
    print("--- 🧠 Iniciando Detección de Anomalías ---", flush=True)
    conn = get_hana_connection()

    try:
        query = '''
        SELECT TOP 3000 *
        FROM "SOC_ANOMALY_LOGS"
        WHERE ("LABEL" IS NULL OR "LABEL" = '')
        AND "TIMESTAMP" >= ADD_SECONDS(CURRENT_UTCTIMESTAMP, -2400)
        ORDER BY "TIMESTAMP" DESC
        '''

        df = pd.read_sql(query, conn)

        if df.empty:
            print("No hay registros nuevos para analizar.", flush=True)
            return

        print(f"Analizando {len(df)} registros nuevos...", flush=True)

        df_processed, X = build_features(df)

        df_processed["ANOMALY_SCORE"] = model.decision_function(X)
        predictions = model.predict(X)

        df_processed["LABEL"] = [
            "Anomalia" if p == -1 else "Normal"
            for p in predictions
        ]

        df_processed["SEVERITY"] = df_processed.apply(assign_severity, axis=1)
        df_processed["MODEL_VERSION"] = artifact.get("model_version", "unknown")

        cursor = conn.cursor()

        update_sql = '''
        UPDATE "SOC_ANOMALY_LOGS"
        SET
            "ANOMALY_SCORE" = ?,
            "LABEL" = ?
        WHERE "EVENT_HASH" = ?
        '''

        for _, row in df_processed.iterrows():
            cursor.execute(
                update_sql,
                (
                    float(row["ANOMALY_SCORE"]),
                    row["LABEL"],
                    row["EVENT_HASH"],
                )
            )

        conn.commit()
        cursor.close()

        print(f"✅ Análisis completado. {len(df_processed)} registros actualizados.", flush=True)

        send_alerts(conn, df_processed)

    except Exception as e:
        conn.rollback()
        print(f"❌ Error en detección de anomalías: {e}", flush=True)

    finally:
        conn.close()



def build_alert_message(row):
    return (
        f"LLM prompt anomaly detected on service {row.get('SERVICE_ID', 'unknown')}. "
        f"Provider={row.get('LLM_PROVIDER', 'unknown')}; "
        f"Model={row.get('LLM_MODEL_ID', 'unknown')}; "
        f"Location={row.get('LOCATION', 'unknown')}; "
        f"Status={row.get('LLM_STATUS', 'unknown')}; "
        f"HTTP={row.get('HTTP_STATUS_CODE', 'unknown')}; "
        f"Tokens={row.get('LLM_TOTAL_TOKENS', 'unknown')}; "
        f"LatencyMs={row.get('LLM_RESPONSE_TIME_MS', 'unknown')}; "
        f"Severity={row.get('SEVERITY', 'unknown')}; "
        f"Score={float(row.get('ANOMALY_SCORE', 0)):.6f}"
    )


def post_alert(row):
    if not ALERT_API_URL:
        raise RuntimeError("Falta ALERT_API_URL. Debe ser el endpoint POST real, no /docs.")

    timestamp = pd.to_datetime(row["TIMESTAMP"], errors="coerce")

    if pd.isna(timestamp):
        timestamp = pd.Timestamp.utcnow()
    elif timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")

    payload = {
        "status": "alert received",
        "team_name": TEAM_NAME,
        "message": build_alert_message(row),
        "timestamp_utc": timestamp.isoformat(),
    }

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"

    response = requests.post(
        ALERT_API_URL,
        json=payload,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    try:
        return response.json()
    except Exception:
        return {"raw_response": response.text}


def send_alerts(conn, df):
    anomalies = df[df["LABEL"] == "Anomalia"].copy()

    if anomalies.empty:
        print("Sin anomalías nuevas para alertar.", flush=True)
        return


    anomalies = anomalies[anomalies.apply(is_alert_worthy, axis=1)]

    if anomalies.empty:
        print("Hay anomalías, pero ninguna cumple criterios de amenaza probable.", flush=True)
        return

    anomalies = anomalies.sort_values("ANOMALY_SCORE", ascending=True)
    anomalies = anomalies.head(MAX_ALERTS_PER_CYCLE)

    for _, row in anomalies.iterrows():
        try:
            result = post_alert(row)
            print(f"🚨 Alerta enviada para EVENT_HASH={row['EVENT_HASH']}: {result}", flush=True)
        except Exception as e:
            print(f"❌ Error enviando alerta EVENT_HASH={row.get('EVENT_HASH')}: {e}", flush=True)

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
        print(f"Registros listos: {len(registros)}", flush=True)
        
        # Paso 3: Carga a HANA
        print("Paso 3: Cargando a SAP HANA...", flush=True)
        load_data_to_hana(registros)
        
        run_anomaly_detection()


        print("--- ✅ Ciclo completado con éxito ---", flush=True)
    except Exception as e:
        print(f"❌ Error crítico en el ciclo: {e}", flush=True)

def classify_prompt(prompt):
    if pd.isna(prompt):
        return "other"

    text = str(prompt).lower()

    if any(x in text for x in ["summarize", "summarise", "resumen", "resume"]):
        return "summarization"
    if any(x in text for x in ["generate", "draft", "write", "crear", "genera", "redacta"]):
        return "generation"
    if any(x in text for x in ["error", "failure", "exception", "fallo", "timeout"]):
        return "system_task"

    return "other"


def get_expected_feature_columns():
    if hasattr(model, "feature_names_in_"):
        return list(model.feature_names_in_)

    return artifact["feature_columns"]

def get_risk_context(row):
    score = float(row.get("ANOMALY_SCORE", 0) or 0)
    http = int(row.get("HTTP_STATUS_CODE", 0) or 0)
    status = str(row.get("LLM_STATUS", "") or "").lower()
    tokens = float(row.get("LLM_TOTAL_TOKENS", 0) or 0)
    latency = float(row.get("LLM_RESPONSE_TIME_MS", 0) or 0)
    provider = str(row.get("LLM_PROVIDER", "") or "").strip()
    model_id = str(row.get("LLM_MODEL_ID", "") or "").strip()
    prompt = str(row.get("LLM_PROMPT", "") or "").lower()

    suspicious_keywords = [
        "ignore previous instructions",
        "ignore all previous instructions",
        "system prompt",
        "developer message",
        "jailbreak",
        "bypass",
        "dan",
        "reveal",
        "exfiltrate",
        "credentials",
        "api key",
        "token",
        "password",
        "sql injection",
        "union select",
        "drop table",
        "rm -rf",
        "base64",
        "curl",
        "wget",
        "reverse shell",
    ]

    has_suspicious_prompt = any(keyword in prompt for keyword in suspicious_keywords)

    is_incomplete_generic_event = (
        http in [200, 201, 204, 301, 302]
        and tokens == 0
        and latency == 0
        and provider == ""
        and model_id == ""
    )

    http_risk = http in [400, 401, 403, 408, 429, 500, 502, 503]
    status_risk = status in ["error", "timeout", "blocked", "failed", "failure"]
    high_tokens = tokens >= 2500
    high_latency = latency >= 10000

    risk_signal = (
        http_risk
        or status_risk
        or high_tokens
        or high_latency
        or has_suspicious_prompt
    )

    return {
        "score": score,
        "http": http,
        "status": status,
        "tokens": tokens,
        "latency": latency,
        "has_suspicious_prompt": has_suspicious_prompt,
        "is_incomplete_generic_event": is_incomplete_generic_event,
        "http_risk": http_risk,
        "status_risk": status_risk,
        "high_tokens": high_tokens,
        "high_latency": high_latency,
        "risk_signal": risk_signal,
    }




def is_alert_worthy(row):
    ctx = get_risk_context(row)
    severity = str(row.get("SEVERITY", "") or "")

    # Ignorar eventos incompletos/genéricos.
    if ctx["is_incomplete_generic_event"]:
        return False

    # High siempre se escala.
    if severity == "High":
        return True

    # Medium se escala si tiene señal real de riesgo.
    if severity == "Medium" and ctx["risk_signal"]:
        return True

    # Low solo se escala si tiene evidencia explícita de prompt sospechoso.
    if severity == "Low" and ctx["has_suspicious_prompt"]:
        return True

    return False




def build_features(df_raw):
    df = df_raw.copy()

    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
    df = df[df["TIMESTAMP"].notna()].copy()

    numeric_base = [
        "LLM_TOTAL_TOKENS",
        "LLM_COST_USD",
        "LLM_RESPONSE_TIME_MS",
        "HTTP_STATUS_CODE",
    ]

    for col in numeric_base:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in ["LOCATION", "LLM_PROVIDER", "LLM_PROMPT_CATEGORY", "LLM_STATUS", "LLM_PROMPT"]:
        if col not in df.columns:
            df[col] = "Unknown"
        df[col] = df[col].fillna("Unknown").astype(str)

    df["hour"] = df["TIMESTAMP"].dt.hour
    df["day_of_week"] = df["TIMESTAMP"].dt.dayofweek
    df["day_of_month"] = df["TIMESTAMP"].dt.day
    df["month"] = df["TIMESTAMP"].dt.month
    df["is_night"] = df["hour"].between(0, 5).astype(int)
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["minute_window"] = df["TIMESTAMP"].dt.floor("min")

    df["requests_per_minute"] = df.groupby("minute_window")["EVENT_HASH"].transform("count")

    error_status = df["LLM_STATUS"].str.lower().isin(["error", "timeout", "failed", "failure"])
    http_error = df["HTTP_STATUS_CODE"] >= 400
    df["_is_error"] = (error_status | http_error).astype(int)

    df["errors_per_minute"] = df.groupby("minute_window")["_is_error"].transform("sum")
    df["avg_latency_per_minute"] = df.groupby("minute_window")["LLM_RESPONSE_TIME_MS"].transform("mean")
    df["tokens_per_minute"] = df.groupby("minute_window")["LLM_TOTAL_TOKENS"].transform("sum")

    df["prompt_length"] = df["LLM_PROMPT"].astype(str).str.len().replace(0, 1)
    df["latency_per_token"] = df["LLM_RESPONSE_TIME_MS"] / df["LLM_TOTAL_TOKENS"].replace(0, 1)
    df["cost_intensity"] = df["LLM_COST_USD"] / df["LLM_TOTAL_TOKENS"].replace(0, 1)
    df["token_density"] = df["LLM_TOTAL_TOKENS"] / df["prompt_length"].replace(0, 1)
    df["task_type"] = df["LLM_PROMPT"].apply(classify_prompt)

    num_features = artifact["num_features"]
    cat_features = artifact["cat_features"]

    X_num = df[num_features].copy()
    X_cat = pd.get_dummies(df[cat_features], drop_first=True)

    X = pd.concat([X_num, X_cat], axis=1)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

    expected_columns = get_expected_feature_columns()

    # Importante: aquí se rellenan también las columnas TDA h0/h1 que tu modelo espera.
    X = X.reindex(columns=expected_columns, fill_value=0)

    return df, X

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

@app.get("/export_datos_urgente")
def exportar_datos():
    conn = get_hana_connection()

    query = '''
    SELECT TOP 10000
        "EVENT_HASH",
        "TIMESTAMP",
        "SOURCE_IP",
        "LOCATION",
        "SERVICE_ID",
        "LLM_PROVIDER",
        "LLM_MODEL_ID",
        "LLM_PROMPT",
        "LLM_TOTAL_TOKENS",
        "LLM_COST_USD",
        "LLM_RESPONSE_TIME_MS",
        "HTTP_STATUS_CODE",
        "ANOMALY_SCORE",
        "LABEL",
        "HEADERS_CONTENT_TYPE",
        "LLM_PROMPT_CATEGORY",
        "LLM_STATUS"
    FROM "SOC_ANOMALY_LOGS"
    WHERE "LLM_TOTAL_TOKENS" > 0
      AND "LLM_PROMPT" IS NOT NULL
      AND "LLM_PROVIDER" IS NOT NULL
      AND "LLM_STATUS" IS NOT NULL
      AND "TIMESTAMP" IS NOT NULL
    ORDER BY "TIMESTAMP" DESC
    '''

    df = pd.read_sql(query, conn)
    conn.close()

    return Response(
        content=df.to_csv(index=False),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=datos_entrenamiento.csv"}
    )


@app.get("/soc_summary")
def soc_summary():
    conn = get_hana_connection()

    query = '''
    SELECT
        COUNT(*) AS TOTAL_LOGS,
        SUM(CASE WHEN "LABEL" = 'Normal' THEN 1 ELSE 0 END) AS TOTAL_NORMAL,
        SUM(CASE WHEN "LABEL" = 'Anomalia' THEN 1 ELSE 0 END) AS TOTAL_ANOMALIAS,
        SUM(CASE WHEN "LABEL" IS NULL OR "LABEL" = '' THEN 1 ELSE 0 END) AS TOTAL_PENDING,
        MIN("ANOMALY_SCORE") AS MIN_SCORE,
        MAX("ANOMALY_SCORE") AS MAX_SCORE,
        AVG("ANOMALY_SCORE") AS AVG_SCORE
    FROM "SOC_ANOMALY_LOGS"
    '''

    df = pd.read_sql(query, conn)
    conn.close()

    return df.to_dict(orient="records")[0]


@app.get("/anomaly_score_distribution")
def anomaly_score_distribution():
    conn = get_hana_connection()

    query = '''
    SELECT
        ROUND("ANOMALY_SCORE", 2) AS SCORE_BUCKET,
        COUNT(*) AS TOTAL
    FROM "SOC_ANOMALY_LOGS"
    WHERE "LABEL" = 'Anomalia'
      AND "ANOMALY_SCORE" IS NOT NULL
    GROUP BY ROUND("ANOMALY_SCORE", 2)
    ORDER BY SCORE_BUCKET ASC
    '''

    df = pd.read_sql(query, conn)
    conn.close()

    return df.to_dict(orient="records")

@app.get("/top_anomalies")
def top_anomalies():
    conn = get_hana_connection()

    query = '''
    SELECT TOP 50
        "TIMESTAMP",
        "EVENT_HASH",
        "SOURCE_IP",
        "LOCATION",
        "SERVICE_ID",
        "LLM_PROVIDER",
        "LLM_MODEL_ID",
        "LLM_STATUS",
        "HTTP_STATUS_CODE",
        "LLM_TOTAL_TOKENS",
        "LLM_RESPONSE_TIME_MS",
        "LLM_COST_USD",
        "ANOMALY_SCORE",
        "LABEL"
    FROM "SOC_ANOMALY_LOGS"
    WHERE "LABEL" = 'Anomalia'
      AND "ANOMALY_SCORE" IS NOT NULL
    ORDER BY "ANOMALY_SCORE" ASC
    '''

    df = pd.read_sql(query, conn)
    conn.close()

    return df.to_dict(orient="records")


@app.get("/anomaly_risk_summary")
def anomaly_risk_summary():
    conn = get_hana_connection()

    query = '''
    SELECT
        COUNT(*) AS TOTAL_ANOMALIAS,
        SUM(CASE WHEN "HTTP_STATUS_CODE" IN (400, 401, 403, 408, 429, 500, 502, 503) THEN 1 ELSE 0 END) AS HTTP_RISK,
        SUM(CASE WHEN LOWER("LLM_STATUS") IN ('error', 'timeout', 'blocked', 'failed', 'failure') THEN 1 ELSE 0 END) AS STATUS_RISK,
        SUM(CASE WHEN "LLM_TOTAL_TOKENS" >= 2500 THEN 1 ELSE 0 END) AS HIGH_TOKENS,
        SUM(CASE WHEN "LLM_RESPONSE_TIME_MS" >= 10000 THEN 1 ELSE 0 END) AS HIGH_LATENCY,
        SUM(CASE WHEN "ANOMALY_SCORE" <= -0.05 THEN 1 ELSE 0 END) AS SCORE_LE_NEG_005,
        SUM(CASE WHEN "ANOMALY_SCORE" <= -0.10 THEN 1 ELSE 0 END) AS SCORE_LE_NEG_010,
        SUM(CASE WHEN "ANOMALY_SCORE" <= -0.15 THEN 1 ELSE 0 END) AS SCORE_LE_NEG_015
    FROM "SOC_ANOMALY_LOGS"
    WHERE "LABEL" = 'Anomalia'
    '''

    df = pd.read_sql(query, conn)
    conn.close()

    return df.to_dict(orient="records")[0]

@app.get("/debug_hana_connection")
def debug_hana_connection():
    conn = get_hana_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT CURRENT_USER, CURRENT_SCHEMA FROM DUMMY")
    current_user, current_schema = cursor.fetchone()

    cursor.execute("""
        SELECT SCHEMA_NAME, TABLE_NAME, RECORD_COUNT
        FROM M_TABLES
        WHERE TABLE_NAME = 'SOC_ANOMALY_LOGS'
        ORDER BY RECORD_COUNT DESC
    """)
    tables = cursor.fetchall()

    cursor.close()
    conn.close()

    return {
        "current_user": current_user,
        "current_schema": current_schema,
        "soc_tables_found": [
            {
                "schema_name": row[0],
                "table_name": row[1],
                "record_count": row[2],
            }
            for row in tables
        ],
    }