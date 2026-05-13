from fastapi import APIRouter
from core.hana import get_hana_connection
from soc.risk_engine import assign_severity, is_alert_worthy, get_risk_context
import pandas as pd


router = APIRouter()

def classify_alert_type(row):
    ctx = get_risk_context(row)

    if ctx.get("has_suspicious_prompt"):
        return "Prompt Security"

    if ctx.get("auth_or_access_risk"):
        return "Access Security"

    if ctx.get("rate_limit_or_abuse"):
        return "Rate Limit / Abuse"

    return "Operational"





@router.get("/soc_summary")
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


@router.get("/anomaly_score_distribution")
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

@router.get("/top_anomalies")
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


@router.get("/anomaly_risk_summary")
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





@router.get("/viz_data")
def viz_data(hours: int = 72, limit: int = 50000, anomaly_type: str = "security"):
    """
    Devuelve datos agregados para visualización:
    - comportamiento real por ventana de 10 minutos
    - puntos de anomalía sobre la serie real
    - filtro por tipo de anomalía: security, operational o all
    """

    allowed_types = ["security", "operational", "all"]
    if anomaly_type not in allowed_types:
        anomaly_type = "security"

    conn = get_hana_connection()

    query = f'''
    SELECT TOP {limit}
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
        "LABEL",
        "LLM_PROMPT"
    FROM "SOC_ANOMALY_LOGS"
    WHERE "TIMESTAMP" >= ADD_SECONDS(CURRENT_UTCTIMESTAMP, -{hours * 3600})
      AND "TIMESTAMP" IS NOT NULL
    ORDER BY "TIMESTAMP" DESC
    '''

    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        return {
            "series": [],
            "top_anomalies": [],
            "summary": {
                "total_events": 0,
                "total_anomalies": 0,
                "security_anomalies": 0,
                "operational_anomalies": 0,
                "visible_anomalies": 0,
                "active_filter": anomaly_type,
                "hours": hours,
            },
        }

    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
    df = df[df["TIMESTAMP"].notna()].copy()

    numeric_cols = [
        "LLM_RESPONSE_TIME_MS",
        "LLM_TOTAL_TOKENS",
        "ANOMALY_SCORE",
        "HTTP_STATUS_CODE",
        "LLM_COST_USD",
    ]

    for col in numeric_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    text_cols = [
        "SOURCE_IP",
        "LOCATION",
        "SERVICE_ID",
        "LLM_PROVIDER",
        "LLM_MODEL_ID",
        "LLM_STATUS",
        "LLM_PROMPT",
    ]

    for col in text_cols:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    df = df.sort_values("TIMESTAMP")
    df["bucket"] = df["TIMESTAMP"].dt.floor("10min")

    # Serie real: comportamiento observado por ventana
    base = (
        df.groupby("bucket")
        .agg(
            avg_latency=("LLM_RESPONSE_TIME_MS", "mean"),
            avg_tokens=("LLM_TOTAL_TOKENS", "mean"),
            total_events=("EVENT_HASH", "count"),
        )
        .reset_index()
    )

    anomalies = df[df["LABEL"] == "Anomalia"].copy()

    if not anomalies.empty:
        anomalies["SEVERITY"] = anomalies.apply(assign_severity, axis=1)
        anomalies["ALERT_TYPE"] = anomalies.apply(classify_alert_type, axis=1)
        anomalies["IS_SECURITY_ALERT"] = anomalies["ALERT_TYPE"].isin([
            "Prompt Security",
            "Access Security",
            "Rate Limit / Abuse",
        ])

        if anomaly_type == "security":
            anomalies_for_view = anomalies[anomalies["IS_SECURITY_ALERT"] == True].copy()
        elif anomaly_type == "operational":
            anomalies_for_view = anomalies[anomalies["IS_SECURITY_ALERT"] == False].copy()
        else:
            anomalies_for_view = anomalies.copy()

    else:
        anomalies_for_view = anomalies.copy()

    security_series = []

    if not anomalies.empty:
        security_only = anomalies[anomalies["IS_SECURITY_ALERT"] == True].copy()
    else:
        security_only = anomalies.copy()

    if not security_only.empty:
        security_group = (
            security_only.groupby("bucket")
            .agg(
                security_events=("EVENT_HASH", "count"),
                http_401=("HTTP_STATUS_CODE", lambda x: int((x == 401).sum())),
                http_403=("HTTP_STATUS_CODE", lambda x: int((x == 403).sum())),
                http_429=("HTTP_STATUS_CODE", lambda x: int((x == 429).sum())),
            )
            .reset_index()
        )

        for _, row in security_group.iterrows():
            security_series.append({
                "time": row["bucket"].strftime("%Y-%m-%d %H:%M"),
                "security_events": int(row["security_events"]),
                "http_401": int(row["http_401"]),
                "http_403": int(row["http_403"]),
                "http_429": int(row["http_429"]),
            })



    # Puntos anómalos filtrados por tipo seleccionado
    if not anomalies_for_view.empty:
        anomaly_points = (
            anomalies_for_view.groupby("bucket")
            .agg(
                anomaly_count=("EVENT_HASH", "count"),
                max_anomaly_latency=("LLM_RESPONSE_TIME_MS", "max"),
                max_anomaly_tokens=("LLM_TOTAL_TOKENS", "max"),
                worst_score=("ANOMALY_SCORE", "min"),
                security_count=("IS_SECURITY_ALERT", "sum"),
            )
            .reset_index()
        )
    else:
        anomaly_points = pd.DataFrame(
            columns=[
                "bucket",
                "anomaly_count",
                "max_anomaly_latency",
                "max_anomaly_tokens",
                "worst_score",
                "security_count",
            ]
        )

    merged = base.merge(anomaly_points, on="bucket", how="left")

    merged["anomaly_count"] = merged["anomaly_count"].fillna(0).astype(int)
    merged["security_count"] = merged["security_count"].fillna(0).astype(int)

    series = []

    for _, row in merged.iterrows():
        has_anomaly = row["anomaly_count"] > 0

        series.append({
            "time": row["bucket"].strftime("%Y-%m-%d %H:%M"),
            "avg_latency": round(float(row["avg_latency"]), 2),
            "avg_tokens": round(float(row["avg_tokens"]), 2),
            "total_events": int(row["total_events"]),
            "anomaly_count": int(row["anomaly_count"]),
            "security_count": int(row["security_count"]),
            "anomaly_latency": round(float(row["max_anomaly_latency"]), 2) if has_anomaly else None,
            "anomaly_tokens": round(float(row["max_anomaly_tokens"]), 2) if has_anomaly else None,
            "worst_score": round(float(row["worst_score"]), 6) if has_anomaly else None,
        })

    # Tabla forense de anomalías filtradas
    top_anomalies = []

    if not anomalies_for_view.empty:
        top = anomalies_for_view.sort_values("ANOMALY_SCORE", ascending=True).head(30).copy()

        for _, row in top.iterrows():
            ctx = get_risk_context(row)

            prompt_text = str(row.get("LLM_PROMPT", "") or "")
            prompt_preview = prompt_text[:380] + "..." if len(prompt_text) > 380 else prompt_text

            top_anomalies.append({
                "timestamp": row["TIMESTAMP"].strftime("%Y-%m-%d %H:%M:%S"),
                "provider": row.get("LLM_PROVIDER", ""),
                "model": row.get("LLM_MODEL_ID", ""),
                "status": row.get("LLM_STATUS", ""),
                "http": int(row.get("HTTP_STATUS_CODE", 0) or 0),
                "tokens": int(row.get("LLM_TOTAL_TOKENS", 0) or 0),
                "latency": int(row.get("LLM_RESPONSE_TIME_MS", 0) or 0),
                "score": round(float(row.get("ANOMALY_SCORE", 0)), 6),
                "severity": row.get("SEVERITY", ""),
                "alert_type": row.get("ALERT_TYPE", "Operational"),
                "location": row.get("LOCATION", ""),
                "service": row.get("SERVICE_ID", ""),
                "source_ip": row.get("SOURCE_IP", ""),
                "security_reasons": ", ".join(ctx.get("security_reasons", [])),
                "operational_reasons": ", ".join(ctx.get("operational_reasons", [])),
                "reasons": ", ".join(ctx.get("reasons", [])),
                "prompt_preview": prompt_preview,
            })

    if not anomalies.empty:
        security_count = int(anomalies["IS_SECURITY_ALERT"].sum())
        operational_count = int((~anomalies["IS_SECURITY_ALERT"]).sum())
    else:
        security_count = 0
        operational_count = 0

    summary = {
        "total_events": int(len(df)),
        "total_anomalies": int(len(anomalies)),
        "security_anomalies": security_count,
        "operational_anomalies": operational_count,
        "visible_anomalies": int(len(anomalies_for_view)),
        "active_filter": anomaly_type,
        "hours": hours,
    }

    return {
        "series": series,
        "security_series": security_series,
        "top_anomalies": top_anomalies,
        "summary": summary,
    }