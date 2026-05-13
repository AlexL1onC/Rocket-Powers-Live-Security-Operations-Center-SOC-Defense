from fastapi import APIRouter
from core.hana import get_hana_connection

router = APIRouter()



@router.get("/")
def health_check():
    return {"status": "SOC Ingestion Service is RUNNING"}


@router.get("/debug_hana_connection")
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
