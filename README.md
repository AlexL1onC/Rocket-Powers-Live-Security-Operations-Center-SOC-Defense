# Rocket-Powers-Live-Security-Operations-Center-SOC-Defense
Repositorio para el SAP Hackathon




Pipeline de Arquitectura: GenAI SOC Real-Time Defense
Este pipeline describe el flujo desde el aprovisionamiento de infraestructura hasta la ingesta de datos en tiempo real en SAP BTP.

1. Capa de Infraestructura y Gobernanza (Control Plane)
Suscripción: Activación de SAP HANA Cloud (Plan tools) para gestión vía Central Dashboard.

RBAC (Security): Asignación de la colección de roles SAP HANA Cloud Administrator al usuario de la Subcuenta para desbloquear privilegios de aprovisionamiento.

Entorno de Ejecución: Configuración de Cloud Foundry Runtime y creación del espacio lógico (dev) para el despliegue del backend.

2. Capa de Persistencia (SAP HANA Cloud)
Motor de Base de Datos: Creación de instancia SAP HANA Database (hana-free).

Networking: Configuración de reglas de firewall permitiendo All IP addresses para garantizar conectividad del backend externo y herramientas locales.

Advanced Features: Habilitación de Natural Language Processing (NLP) para soporte nativo de Vector Engine (almacenamiento y búsqueda de similitud de embeddings de prompts).

3. Capa de Integración y Abstracción (HDI)
Instance Mapping: Mapeo lógico de la instancia física de HANA hacia la Organización y Espacio de Cloud Foundry.

Contenedor HDI: Creación de servicio SAP HANA Schemas & HDI Containers (Plan hdi-shared). Esto aísla el esquema del proyecto y permite la gestión de artefactos de base de datos de forma declarativa.

Credenciales: Generación de Service Keys para la extracción de metadatos de conexión (host, port, user, password) requeridos por el driver hdbcli.

4. Modelado de Datos y Backend (Data Engineering)
Esquema Físico: Definición de tablas columnares optimizadas para series de tiempo y vectores en SAP HANA Database Explorer.

Pipeline de Ingesta (Python): * Consumo asíncrono de API SOC.

Evaluación In-Memory: Detección de anomalías inmediata para minimizar el MTTD (Mean Time To Detect).

Micro-batching: Inserción eficiente en HANA mediante executemany para reducir el overhead de red.





☁️ Configuración "Cloud-Ready" (Gestión de Credenciales)
Para garantizar la seguridad y escalabilidad del SOC, este backend sigue la metodología Twelve-Factor App. Estrictamente, ninguna credencial o IP está "hardcodeada" en el código fuente. El despliegue está diseñado para consumir las variables de entorno de infraestructura que SAP BTP Cloud Foundry inyecta dinámicamente (VCAP_SERVICES).

1. Requisitos de Entorno
Para que el script de Python sea agnóstico (funcione igual en tu computadora local durante el desarrollo y en la nube de SAP en producción), utilizamos las librerías cfenv y python-dotenv:

Bash
pip install cfenv python-dotenv hdbcli
2. Desarrollo Local (Simulación de BTP)
Para probar el código localmente sin alterar la lógica de producción, crea un archivo .env en la raíz del proyecto. (Nota: Este archivo está en el .gitignore y jamás debe subirse al repositorio).

Dentro del .env, pega el JSON exacto de la Service Key que generaste en el contenedor HDI de SAP HANA, asignándolo a la variable VCAP_SERVICES:

Fragmento de código
# Archivo: .env
VCAP_SERVICES={"hana": [{"credentials": {"host": "tu-host.hana.ondemand.com", "password": "tu-password", "port": "443", "user": "tu-usuario"}}]}
3. Implementación en Python
El siguiente patrón de diseño permite que el backend busque primero las credenciales inyectadas por el entorno de SAP BTP y, si no las encuentra (es decir, estás corriendo el script en tu laptop), recurra al archivo local .env.

Python
import os
from dotenv import load_dotenv
from cfenv import AppEnv
from hdbcli import dbapi

# 1. Cargar variables locales si existen (Ignorado en la nube)
load_dotenv()

# 2. Inicializar el entorno de Cloud Foundry
env = AppEnv()

def get_hana_connection():
    # 3. Buscar el servicio enlazado de HANA (HDI Container)
    hana_service = env.get_service(label='hana')
    
    if not hana_service:
        raise ValueError("Error Crítico: No se encontraron las credenciales de SAP HANA en VCAP_SERVICES.")
    
    creds = hana_service.credentials

    # 4. Establecer conexión segura in-memory
    try:
        conn = dbapi.connect(
            address=creds['host'],
            port=int(creds['port']),
            user=creds['user'],
            password=creds['password'],
            encrypt="true",
            sslValidateCertificate="false" 
        )
        return conn
    except Exception as e:
        print(f"Falla de Ingesta SOC: Imposible conectar a la base de datos columnar. Detalle: {e}")
        raise
Ventaja Arquitectónica: Cuando subas este código a BTP usando cf push, no tendrás que cambiar ni una sola línea de código. La plataforma enlazará el backend con la base de datos automáticamente.