import os
import time
import base64
import requests
from core.hana import get_hana_connection



def get_service_manager_token():
    """
    Obtiene token OAuth de SAP Service Manager.
    Requiere:
    - SM_UAA_URL
    - SM_CLIENT_ID
    - SM_CLIENT_SECRET
    """
    uaa_url = os.getenv("SM_UAA_URL")
    client_id = os.getenv("SM_CLIENT_ID")
    client_secret = os.getenv("SM_CLIENT_SECRET")

    if not all([uaa_url, client_id, client_secret]):
        print("ℹ️ Service Manager no configurado. Se omite auto-start de HANA.", flush=True)
        return None

    credentials = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = requests.get(
        f"{uaa_url}/oauth/token?grant_type=client_credentials",
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()
    return response.json()["access_token"]


def start_hana_if_needed():
    """
    Solicita a SAP Service Manager prender HANA Cloud.
    Si HANA ya está prendida, no debería afectar.
    Requiere:
    - SM_URL
    - HANA_INSTANCE_ID
    """
    sm_url = os.getenv("SM_URL")
    hana_instance_id = os.getenv("HANA_INSTANCE_ID")

    if not all([sm_url, hana_instance_id]):
        print("ℹ️ SM_URL o HANA_INSTANCE_ID no configurado. Se omite auto-start de HANA.", flush=True)
        return

    try:
        token = get_service_manager_token()

        if not token:
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "parameters": {
                "data": {
                    "serviceStopped": False
                }
            }
        }

        response = requests.patch(
            f"{sm_url}/v1/service_instances/{hana_instance_id}",
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.status_code in [200, 202]:
            print("🚀 Solicitud enviada para iniciar SAP HANA Cloud.", flush=True)
        else:
            print(
                f"⚠️ No se pudo iniciar HANA. "
                f"Status={response.status_code}, body={response.text}",
                flush=True,
            )

    except Exception as e:
        print(f"⚠️ Error en auto-start de HANA: {e}", flush=True)


def wait_for_hana_ready(max_attempts=12, sleep_seconds=20):
    """
    Espera hasta que HANA responda.
    Máximo default: 12 intentos * 20 segundos = 4 minutos.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            conn = get_hana_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT CURRENT_UTCTIMESTAMP FROM DUMMY")
            cursor.fetchone()
            cursor.close()
            conn.close()

            print("✅ SAP HANA Cloud está disponible.", flush=True)
            return True

        except Exception as e:
            print(
                f"⏳ HANA aún no está lista. "
                f"Intento {attempt}/{max_attempts}. Error: {e}",
                flush=True,
            )
            time.sleep(sleep_seconds)

    print("❌ HANA no estuvo disponible después de esperar.", flush=True)
    return False

