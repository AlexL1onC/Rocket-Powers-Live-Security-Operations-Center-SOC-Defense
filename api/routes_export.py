from fastapi import APIRouter, Response
from core.hana import get_hana_connection
import pandas as pd

router = APIRouter()


@router.get("/export_datos_urgente")
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