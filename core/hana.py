import os
from cfenv import AppEnv
from hdbcli import dbapi



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