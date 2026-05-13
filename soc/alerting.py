import pandas as pd
import requests

from config import ALERT_API_URL, API_TOKEN, TEAM_NAME, MAX_ALERTS_PER_CYCLE
from soc.risk_engine import get_risk_context, is_alert_worthy



def build_alert_message(row):
    ctx = get_risk_context(row)
    reasons = ", ".join(ctx["reasons"]) if ctx["reasons"] else "security_policy_match"

    return (
        f"Security anomaly detected in LLM traffic. "
        f"AlertType=SECURITY; "
        f"Reasons={reasons}; "
        f"Service={row.get('SERVICE_ID', 'unknown')}; "
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