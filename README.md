# Rocket Powers SOC Defense

Sistema SOC en tiempo real para monitorear, detectar y priorizar amenazas en tráfico de LLMs usando **SAP HANA Cloud**, **FastAPI**, **Machine Learning**, un **motor SOC interpretable** y un **Agente SOC con IA**.

> Enlace principal para abrir el dashboard desplegado en SAP BTP Cloud Foundry.
>
> **Dashboard:** `https://rocket-powers-soc.cfapps.us10-001.hana.ondemand.com/dashboard`
>
> **Link de Video del Demo:** `https://youtu.be/dN5IVqZOImc`
>

---

## 1. Resumen ejecutivo

Rocket Powers SOC Defense es una solución de defensa para un entorno de uso de LLMs. El sistema consume logs desde la API del hackathon SAP, los procesa, los almacena en **SAP HANA Cloud**, detecta anomalías mediante Machine Learning y separa los eventos entre:

- **Anomalías operativas:** latencia alta, timeouts, errores, uso elevado de tokens o comportamiento inusual de rendimiento.
- **Señales de seguridad:** accesos no autorizados, rate limit abuse, patrones de tráfico sospechosos o prompts potencialmente maliciosos.

La solución no envía una alerta por cada anomalía. Primero detecta desviaciones estadísticas y después aplica un **motor SOC de clasificación** para reducir falsos positivos y evitar *alert fatigue*.

---

## 2. Acceso rápido al dashboard

La forma más sencilla de revisar el proyecto es entrando directamente al dashboard:

```text
https://rocket-powers-soc.cfapps.us10-001.hana.ondemand.com/dashboard
```

Dentro del dashboard se puede revisar:

1. **Resumen ejecutivo del SOC**
2. **Embudo de decisión SOC**
3. **Vista principal de seguridad**
4. **Contexto operativo: latencia y tokens**
5. **Clasificación operación vs seguridad**
6. **Vista forense de eventos anómalos**
7. **Agente SOC con IA** en la barra lateral derecha

La barra izquierda permite navegar por las secciones principales del dashboard, mientras que la barra derecha contiene el agente de IA.

---

## 3. Diferenciador del proyecto

Este proyecto no es únicamente un notebook de Machine Learning. Es un sistema desplegado de extremo a extremo:

- Extracción automática de logs desde la API del reto.
- Backend **FastAPI** desplegado en **SAP BTP Cloud Foundry**.
- Persistencia de eventos en **SAP HANA Cloud**.
- Limpieza y normalización de datos en producción.
- Feature engineering para comportamiento LLM.
- Modelo no supervisado de detección de anomalías.
- Motor SOC interpretable para clasificar anomalías.
- Dashboard web con visualización de seguridad y operación.
- Agente SOC con IA generativa conectado a contexto real recuperado desde SAP HANA.
- Envío de alertas mediante POST a la API del concurso.

El diferenciador principal es la separación entre **detección de anomalías** y **decisión SOC**. El modelo detecta eventos inusuales; el motor SOC decide si esos eventos representan una señal de seguridad o solo un problema operativo.

---

## 4. Arquitectura general

```text
SAP Hackathon Logs API
        ↓
FastAPI Scheduler
        ↓
Extracción de logs
        ↓
Limpieza / normalización / feature engineering
        ↓
SAP HANA Cloud
        ↓
Modelo ML de detección de anomalías
        ↓
SOC Risk Engine
        ↓
Clasificación:
  - Operational
  - Access Security
  - Rate Limit / Abuse
  - Prompt Security
        ↓
Dashboard SOC + Agente SOC con IA
        ↓
SAP Alert API
```

---

## 5. Flujo del sistema

1. El backend ejecuta un ciclo SOC programado.
2. Se extraen logs desde la API del hackathon.
3. Los datos se guardan como JSON/raw data y se procesan.
4. Se estandarizan columnas clave como IP, timestamp, proveedor, modelo, status, tokens, latencia y código HTTP.
5. Se cargan los registros procesados en SAP HANA Cloud.
6. Se calculan features operativas y de comportamiento LLM.
7. El modelo ML identifica registros anómalos.
8. El motor SOC clasifica las anomalías como operativas o de seguridad.
9. El dashboard muestra el estado del SOC y los eventos priorizados.
10. El agente SOC con IA consulta el contexto del sistema y responde preguntas del analista.
11. Las señales relevantes pueden enviarse a la API de alertas del concurso.

---

## 6. Modelo de detección de anomalías

Se utiliza un modelo no supervisado, basado en **Isolation Forest**, para identificar eventos que se desvían del comportamiento esperado.

El modelo no se presenta como un clasificador absoluto de ataques. Su función es detectar patrones atípicos. Después, una capa SOC interpreta esas anomalías usando reglas de seguridad y señales operativas.

### Variables usadas por el modelo

El sistema genera y utiliza variables como:

- Longitud del prompt
- Densidad de tokens
- Latencia por token
- Intensidad de costo
- Hora del evento
- Día de la semana
- Indicadores nocturnos o de fin de semana
- Solicitudes por minuto
- Errores por minuto
- Latencia promedio por minuto
- Tokens por minuto
- Código HTTP
- Proveedor LLM
- Modelo LLM
- Estado de respuesta LLM
- Categoría del prompt

---

## 7. Motor SOC de clasificación

El motor SOC separa las anomalías en categorías interpretables:

```text
Operational
Access Security
Rate Limit / Abuse
Prompt Security
```

### Operational

Eventos anómalos relacionados con operación, rendimiento o disponibilidad:

- Latencia alta
- Timeouts
- Errores del proveedor
- Consumo elevado de tokens
- Eventos con status `success`, `error` o `timeout` sin evidencia adicional de seguridad

Estos eventos no se escalan como amenazas por sí solos.

### Access Security

Eventos con señales de acceso no autorizado o prohibido:

```text
HTTP 401 → no autorizado / autenticación fallida
HTTP 403 → acceso prohibido / sin permisos
```

Estos eventos pueden aparecer con tokens, prompt, proveedor y latencia en cero porque probablemente fueron bloqueados antes de llegar al modelo LLM.

### Rate Limit / Abuse

Eventos asociados a rate limit o posible abuso de tráfico:

```text
HTTP 429 → demasiadas solicitudes / rate limit
```

No se interpreta automáticamente como DDoS confirmado. Se considera una señal de posible abuso que requiere investigación SOC.

### Prompt Security

Eventos donde el prompt contiene señales explícitas de riesgo, por ejemplo:

- Intentos de prompt injection
- Intentos de revelar el system prompt
- Solicitudes de credenciales o secretos
- Patrones de exfiltración
- Indicadores de bypass o abuso del modelo

---

## 8. Estrategia anti alert fatigue

El sistema evita enviar todas las anomalías como alertas.

```text
Modelo ML → detecta anomalía
Motor SOC → interpreta la anomalía
Alert Engine → decide si se escala
```

Esto permite conservar eventos operativos para análisis forense sin saturar el canal de alertas.

Frase clave del proyecto:

> El modelo detecta desviaciones, pero el SOC solo escala eventos con evidencia adicional de seguridad.

---

## 9. Dashboard SOC

El dashboard está disponible en:

```text
https://rocket-powers-soc.cfapps.us10-001.hana.ondemand.com/dashboard
```

### Elementos principales

- **Menú lateral izquierdo:** permite desplazarse por las secciones del dashboard.
- **Panel central:** contiene las métricas, gráficas y tabla forense.
- **Agente SOC derecho:** permite consultar el estado del SOC usando IA generativa.

### Secciones del dashboard

1. **Resumen ejecutivo del SOC**  
   Muestra eventos totales, anomalías, anomalías visibles y señales de seguridad.

2. **Embudo de decisión SOC**  
   Muestra cómo se reduce el volumen desde eventos totales hasta anomalías operativas y señales de seguridad.

3. **Vista principal de seguridad**  
   Grafica eventos de seguridad por tiempo y distribución de códigos HTTP 401, 403 y 429.

4. **Contexto operativo**  
   Muestra latencia y tokens reales frente a puntos anómalos.

5. **Clasificación operación vs seguridad**  
   Compara anomalías operativas y señales de seguridad.

6. **Vista forense**  
   Tabla con timestamp, tipo, servicio, IP, ubicación, HTTP, score, evidencia security, contexto operativo y prompt.

---

## 10. Agente SOC con IA

El dashboard incluye un agente SOC con IA generativa. El agente funciona de la siguiente forma:

```text
Pregunta del usuario
        ↓
Backend consulta SAP HANA
        ↓
Se construye contexto SOC
        ↓
Modelo Gemini interpreta el contexto
        ↓
Respuesta como analista SOC
```

El agente puede responder preguntas como:

- ¿Cuál es el estado ejecutivo del SOC?
- ¿Qué alertas de seguridad debo revisar primero?
- ¿Qué significa HTTP 401, 403 o 429?
- ¿Por qué un timeout no es seguridad por sí solo?
- ¿Qué acciones recomiendas?
- ¿Cómo funciona el modelo y la clasificación SOC?

El agente no responde desde memoria general únicamente. Primero recupera métricas y eventos reales desde SAP HANA, y después genera una explicación con IA.

Si la cuota del proveedor de IA no está disponible, el sistema puede regresar una respuesta contextual de respaldo para que el SOC no quede sin respuesta.

---

## 11. API de alertas del concurso

La API del reto tiene dos funciones principales:

1. **Extracción**  
   Cada cierto intervalo se disponibilizan datos que deben ser extraídos y analizados.

2. **POST de alertas**  
   Las alertas detectadas se envían con un formato como:

```json
{
  "status": "alert received",
  "team_name": "ROCKET_POWERS",
  "message": "LLM prompt anomaly detected on service llm-proxy...",
  "timestamp_utc": "2026-04-26T17:41:00.000000+00:00"
}
```

---

## 12. Endpoints principales

### Interfaz

```text
GET /dashboard
```

### Salud y diagnóstico

```text
GET /
GET /debug_hana_connection
```

### Métricas SOC

```text
GET /soc_summary
GET /anomaly_risk_summary
GET /anomaly_score_distribution
GET /top_anomalies
GET /viz_data
```

Ejemplo:

```text
GET /viz_data?hours=72&limit=50000&anomaly_type=security
```

### Agente SOC con IA

```text
POST /soc_assistant
```

Ejemplo de body:

```json
{
  "question": "Qué alertas de seguridad debo revisar primero y por qué",
  "hours": 72
}
```

---

## 13. Estructura del proyecto

```text
.
├── main.py
├── config.py
├── manifest.yml
├── requirements.txt
├── api/
│   ├── routes_assistant.py
│   ├── routes_export.py
│   ├── routes_health.py
│   ├── routes_metrics.py
│   └── routes_visualization.py
├── core/
│   ├── hana.py
│   ├── hana_autostart.py
│   └── scheduler.py
├── data_ingestion/
│   ├── db_loader.py
│   ├── data_extraction.py
│   └── processor.py
├── ml/
│   ├── detector.py
│   ├── features.py
│   └── model_loader.py
├── soc/
│   ├── alerting.py
│   └── risk_engine.py
├── templates/
│   └── soc_dashboard.html
├── static/
│   ├── css/
│   │   └── soc_dashboard.css
│   └── js/
│       └── soc_dashboard.js
├── shared_data/
└── models/
```

---

## 14. Variables de entorno

Configurar localmente con `.env` o en SAP BTP Cloud Foundry con `cf set-env`.

Variables principales:

```env
API_URL=https://sap-api-b4.674318.xyz/logs/current?page=1
API_BASE_URL=https://sap-api-b4.674318.xyz/logs/current?page=1
API_KEY=your_api_key
OUTPUT_FOLDER=shared_data/raw_logs.json
OUTPUT_PARQUET_FOLDER=shared_data/processed_logs.parquet
MAX_ALERTS_PER_CYCLE=5
ALERT_SCORE_THRESHOLD=-0.05
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash-lite
```

No subir `.env` al repositorio.

---

## 15. Despliegue en SAP BTP Cloud Foundry

### Login

```bash
cf login
```

### Desplegar

```bash
cf push
```

### Revisar estado

```bash
cf apps
```

La app debe aparecer como:

```text
rocket-powers-soc   started   1/1
```

### Revisar logs

```bash
cf logs rocket-powers-soc --recent
```

### Revisar variables de entorno

```bash
cf env rocket-powers-soc
```

---

## 16. Cómo correr localmente

Crear ambiente virtual:

```bash
python -m venv venv_sap
```

Activar ambiente en Windows:

```bash
venv_sap\Scripts\activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

Ejecutar FastAPI:

```bash
uvicorn main:app --reload
```

Abrir:

```text
http://localhost:8000/dashboard
```

---

## 17. Validación rápida

Antes de desplegar:

```bash
python -m py_compile main.py api/routes_assistant.py api/routes_metrics.py api/routes_visualization.py soc/risk_engine.py
python -c "import main; print('main import OK')"
```

Después del despliegue:

```text
/dashboard
/soc_summary
/viz_data?hours=72&limit=50000&anomaly_type=security
/soc_assistant
```

---

## 18. Limitaciones conocidas

- El modelo detecta anomalías, no confirma ataques por sí solo.
- HTTP 401, 403 y 429 son señales de seguridad, no necesariamente ataques confirmados.
- Eventos con tokens y latencia en cero pueden haber sido bloqueados antes de llegar al LLM.
- La calidad del agente IA depende de la disponibilidad y cuota del proveedor LLM.
- El sistema prioriza señales de seguridad para investigación SOC, no reemplaza la validación de un analista.

---

## 19. Próximos pasos

- Mejorar correlación por IP, servicio y ventana temporal.
- Agregar persistencia dedicada de alertas enviadas.
- Construir vistas históricas por severidad y tipo de evento.
- Integrar SAP Analytics Cloud o dashboards ejecutivos adicionales.
- Agregar evaluación continua del modelo.
- Crear reglas específicas para prompt injection avanzado.
- Implementar confirmación manual de incidentes por analista.

---

## 20. Equipo

**Rocket Powers**

Live Security Operation Center Defense Hackathon — SAP
