import pandas as pd

from core.hana import get_hana_connection
from ml.model_loader import model, artifact
from ml.features import build_features
from soc.risk_engine import assign_severity
from soc.alerting import send_alerts



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

