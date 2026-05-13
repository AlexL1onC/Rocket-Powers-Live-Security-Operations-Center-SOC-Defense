# Reporte técnico de arquitectura
# Rocket Powers SOC Defense

**Proyecto:** Live Security Operation Center Defense Hackathon  
**Equipo:** Rocket Powers  
**Dashboard:** https://rocket-powers-soc.cfapps.us10-001.hana.ondemand.com/dashboard  
**Repositorio:** agregar URL pública de GitHub  
**Fecha:** 12 de mayo de 2026  

---

## 1. Resumen ejecutivo

Rocket Powers SOC Defense es una solución de monitoreo y defensa para tráfico asociado al uso de modelos de lenguaje grande, LLMs. El sistema consume logs del reto SAP, los almacena en SAP HANA Cloud, detecta eventos anómalos mediante Machine Learning y prioriza únicamente aquellos eventos que presentan señales relevantes para investigación SOC.

La solución está desplegada en SAP BTP Cloud Foundry mediante FastAPI. Ejecuta ciclos automáticos de ingesta, procesa los datos, los almacena en SAP HANA Cloud, aplica un modelo de detección de anomalías, clasifica los eventos mediante un motor SOC interpretable y expone un dashboard web con visualización forense y un agente con IA generativa.

El diferenciador principal es la separación entre anomalías operativas y señales de seguridad. El modelo detecta desviaciones estadísticas, pero el sistema no escala automáticamente todas las anomalías como alertas. Una segunda capa SOC clasifica los eventos como operativos, acceso no autorizado, rate limit abuse o prompt security. Esto reduce falsos positivos y evita alert fatigue.

---

## 2. Problema a resolver

El reto consiste en construir un sistema capaz de analizar logs generados por servicios relacionados con LLMs y enviar reportes de alertas a una API proporcionada por el hackathon.

La API del reto tiene dos funciones principales:

1. **Extracción de datos:** cada 30 minutos se publican nuevos registros que deben ser extraídos y analizados.
2. **Envío de alertas:** cuando el sistema detecta un evento relevante, debe enviar un POST con un formato específico:

```json
{
  "status": "alert received",
  "team_name": "ROCKET_POWERS",
  "message": "LLM prompt anomaly detected...",
  "timestamp_utc": "2026-04-26T17:41:00.000000+00:00"
}
```

El reto principal no es solamente detectar anomalías, sino decidir cuáles anomalías merecen ser investigadas como señales de seguridad. En un SOC real, enviar demasiadas alertas de baja calidad genera alert fatigue y dificulta la investigación.

---

## 3. Objetivos del sistema

### Objetivo general

Diseñar e implementar un sistema SOC en la nube que detecte anomalías en logs de uso de LLMs, clasifique los eventos según su relevancia operativa o de seguridad, visualice los hallazgos y escale alertas relevantes mediante la API del reto.

### Objetivos específicos

- Extraer automáticamente logs desde la API del reto cada 30 minutos.
- Normalizar y almacenar los registros en SAP HANA Cloud.
- Aplicar un modelo de detección de anomalías sobre variables operativas y de uso LLM.
- Separar anomalías operativas de señales de seguridad.
- Enviar alertas únicamente cuando exista evidencia suficiente.
- Construir un dashboard SOC para monitoreo y análisis forense.
- Integrar un agente con IA generativa que interprete datos reales del SOC y recomiende acciones.
- Desplegar la solución en SAP BTP Cloud Foundry.

---

## 4. Arquitectura general

```text
SAP Hackathon Logs API
        ↓
FastAPI Scheduler
        ↓
Data Extraction
        ↓
Data Processing / Feature Engineering
        ↓
SAP HANA Cloud
        ↓
ML Anomaly Detection
        ↓
SOC Risk Engine
        ↓
Security / Operational Classification
        ↓
SAP Alert API
        ↓
Dashboard + SOC AI Agent
```

### Componentes principales

| Componente | Descripción |
|---|---|
| API del reto | Fuente de logs que publica nuevos datos cada 30 minutos. |
| FastAPI | Backend principal del sistema SOC. |
| APScheduler | Planificador encargado de ejecutar ciclos automáticos de ingesta y análisis. |
| SAP HANA Cloud | Base de datos persistente para almacenar logs, scores, etiquetas y resultados. |
| Modelo ML | Detector no supervisado de anomalías. |
| Motor SOC | Capa de reglas interpretables que clasifica anomalías. |
| API de alertas | Endpoint del reto donde se envían eventos relevantes. |
| Dashboard web | Visualización ejecutiva y forense del estado del SOC. |
| Agente SOC con IA | Asistente que consulta contexto real y responde como analista SOC. |

---

## 5. Stack tecnológico

- Python
- FastAPI
- SAP BTP Cloud Foundry
- SAP HANA Cloud
- hdbcli
- pandas / NumPy
- scikit-learn
- APScheduler
- HTML, CSS y JavaScript
- Chart.js
- Gemini API
- REST APIs

---

## 6. Flujo de datos

1. **Inicio del ciclo SOC:** FastAPI inicia el servidor y configura el scheduler.
2. **Extracción:** el sistema consulta la API del reto y descarga logs recientes.
3. **Procesamiento:** se limpian columnas, se normalizan tipos de datos y se generan campos estándar.
4. **Persistencia:** los registros se almacenan en SAP HANA Cloud.
5. **Análisis ML:** el modelo evalúa registros pendientes y asigna `ANOMALY_SCORE` y `LABEL`.
6. **Clasificación SOC:** se interpreta cada anomalía para determinar si es operativa o de seguridad.
7. **Envío de alertas:** solo eventos relevantes se envían a la API del concurso.
8. **Visualización:** el dashboard consulta métricas y eventos desde SAP HANA.
9. **Agente IA:** el agente recupera contexto del SOC y genera explicaciones o recomendaciones.

---

## 7. Modelo de datos

La tabla principal utilizada por el sistema es:

```text
SOC_ANOMALY_LOGS
```

Campos relevantes:

| Campo | Descripción |
|---|---|
| `EVENT_HASH` | Identificador único del evento. |
| `TIMESTAMP` | Fecha y hora del evento. |
| `SOURCE_IP` | IP origen del evento. |
| `LOCATION` | Ubicación asociada al evento. |
| `SERVICE_ID` | Servicio afectado. |
| `LLM_PROVIDER` | Proveedor del modelo LLM. |
| `LLM_MODEL_ID` | Modelo utilizado. |
| `LLM_PROMPT` | Prompt asociado al evento, cuando existe. |
| `LLM_TOTAL_TOKENS` | Consumo total de tokens. |
| `LLM_RESPONSE_TIME_MS` | Latencia del servicio LLM. |
| `LLM_COST_USD` | Costo asociado al evento. |
| `HTTP_STATUS_CODE` | Código HTTP del evento. |
| `LLM_STATUS` | Estado del servicio LLM. |
| `ANOMALY_SCORE` | Score generado por el modelo. |
| `LABEL` | Clasificación ML: normal, anomalía o pendiente. |
| `SEVERITY` | Severidad asignada por el motor SOC. |

---

## 8. Feature engineering

El sistema genera variables para capturar comportamiento de uso, rendimiento y patrones temporales:

- Longitud del prompt.
- Densidad de tokens.
- Latencia por token.
- Intensidad de costo.
- Hora del día.
- Día de la semana.
- Indicador de horario nocturno.
- Indicador de fin de semana.
- Solicitudes por minuto.
- Errores por minuto.
- Latencia promedio por minuto.
- Tokens por minuto.
- Variables categóricas codificadas para proveedor, modelo, estado, servicio y ubicación.

---

## 9. Modelo de detección de anomalías

El sistema utiliza un enfoque no supervisado para detectar eventos que se desvían del comportamiento esperado. El modelo genera un score de anomalía para cada evento procesado.

### Interpretación del score

- Scores más negativos indican eventos más inusuales.
- El score no confirma ataques por sí solo.
- El score es una señal inicial que alimenta al motor SOC.

El modelo responde a la pregunta:

> ¿Este evento se comporta de forma inusual respecto al resto de los logs?

No responde directamente:

> ¿Este evento es un ataque confirmado?

Por esa razón se agregó una segunda capa de interpretación SOC.

---

## 10. Motor SOC de clasificación

El motor SOC es una capa posterior al modelo que interpreta las anomalías detectadas. Su propósito es reducir falsos positivos y priorizar investigaciones.

| Categoría | Criterio general |
|---|---|
| `Operational` | Latencia alta, tokens altos, timeout, error o consumo anómalo sin evidencia security. |
| `Access Security` | Eventos con HTTP 401 o 403, asociados a posible acceso no autorizado o prohibido. |
| `Rate Limit / Abuse` | Eventos con HTTP 429, asociados a posible abuso de tráfico o rate limit. |
| `Prompt Security` | Prompts con patrones sospechosos como prompt injection o intento de exfiltración. |

### Reglas interpretables

```text
HTTP 401 → posible autenticación fallida o acceso no autorizado.
HTTP 403 → acceso prohibido o sin permisos suficientes.
HTTP 429 → rate limit o posible abuso volumétrico.
Timeout / success / tokens altos → anomalía operativa, no security por sí solo.
Prompt sospechoso → posible prompt injection o intento de extracción.
```

---

## 11. Estrategia anti alert fatigue

Un problema común en sistemas SOC es el exceso de alertas. Para evitarlo, el sistema no envía todos los eventos anómalos a la API del concurso.

La estrategia implementada es:

1. El modelo detecta anomalías.
2. El motor SOC revisa si la anomalía contiene evidencia adicional.
3. Solo eventos con señales de seguridad se consideran candidatos a escalamiento.
4. Las anomalías operativas se conservan para análisis forense, pero no se tratan como ataques confirmados.

---

## 12. Envío de alertas

Cuando un evento cumple criterios de seguridad, el sistema genera un mensaje contextual y lo envía a la API del concurso mediante POST.

Ejemplo:

```text
LLM prompt anomaly detected on service api-gateway.
Provider=OpenAI; Model=gpt-4o-mini; Location=Spain | Madrid;
Status=success; HTTP=429; Tokens=0; LatencyMs=0;
Severity=Medium; Score=-0.020973
```

Formato enviado:

```json
{
  "status": "alert received",
  "team_name": "ROCKET_POWERS",
  "message": "Mensaje generado por el SOC",
  "timestamp_utc": "timestamp en UTC"
}
```

---

## 13. Dashboard SOC

El dashboard web está disponible en:

```text
https://rocket-powers-soc.cfapps.us10-001.hana.ondemand.com/dashboard
```

### Estructura visual

El dashboard tiene tres columnas:

1. **Menú izquierdo:** navegación rápida entre secciones.
2. **Centro:** visualización principal del SOC.
3. **Barra derecha:** agente SOC con IA.

### Secciones

| Sección | Propósito |
|---|---|
| Resumen ejecutivo | KPIs principales de eventos, anomalías y señales de seguridad. |
| Embudo SOC | Flujo desde eventos totales hasta eventos de seguridad. |
| Vista de seguridad | Eventos por tiempo y distribución de códigos HTTP 401/403/429. |
| Contexto operativo | Latencia y tokens reales vs puntos anómalos. |
| Clasificación | Comparación entre anomalías operativas y seguridad. |
| Vista forense | Tabla detallada con timestamp, tipo, servicio, IP, ubicación, score, evidencia y prompt. |

### Interpretación clave

Algunos eventos de seguridad pueden aparecer con tokens, latencia y prompt en cero. Esto ocurre porque fueron bloqueados antes de llegar al modelo LLM. En esos casos, la evidencia principal es el código HTTP, la IP, el servicio y la frecuencia.

---

## 14. Agente SOC con IA

La solución incluye un agente SOC con IA generativa integrado en la barra derecha del dashboard.

### Funcionamiento

```text
Pregunta del usuario
        ↓
Consulta contexto real desde SAP HANA
        ↓
Construye resumen SOC con métricas y eventos relevantes
        ↓
Envía el contexto a un modelo generativo
        ↓
Devuelve interpretación como analista SOC
```

### Capacidades

El agente puede responder preguntas como:

- ¿Cuál es el estado general del SOC?
- ¿Qué señales de seguridad debo revisar primero?
- ¿Qué significa HTTP 401, 403 y 429?
- ¿Qué acciones recomiendas?
- ¿Por qué un timeout no es security?
- ¿Cómo funciona el modelo y la clasificación SOC?

### Seguridad del agente

Los prompts recuperados desde los logs se tratan como datos no confiables. El agente no debe seguir instrucciones contenidas dentro de los prompts analizados; solo debe usarlos como evidencia contextual.

---

## 15. Endpoints principales

### Dashboard y salud

```text
GET /
GET /dashboard
GET /health
GET /debug_hana_connection
```

### Métricas SOC

```text
GET /soc_summary
GET /anomaly_risk_summary
GET /anomaly_score_distribution
GET /top_anomalies
GET /viz_data?hours=72&limit=50000&anomaly_type=security
```

### Agente SOC

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

## 16. Estructura del proyecto

```text
.
├── main.py
├── config.py
├── requirements.txt
├── manifest.yml
├── Procfile
├── api/
│   ├── routes_assistant.py
│   ├── routes_export.py
│   ├── routes_health.py
│   ├── routes_metrics.py
│   └── routes_visualization.py
├── core/
│   ├── hana.py
│   └── hana_autostart.py
├── data_ingestion/
│   ├── data_extraction.py
│   ├── data_processing.py
│   └── db_loader.py
├── ml/
│   ├── detector.py
│   ├── features.py
│   └── model_loader.py
├── soc/
│   ├── alerting.py
│   └── risk_engine.py
├── templates/
│   └── dashboard.html
├── static/
│   ├── css/
│   │   └── soc_dashboard.css
│   └── js/
│       └── soc_dashboard.js
└── docs/
    └── reporte_tecnico.md
```

---

## 17. Variables de entorno

Las variables sensibles no deben subirse al repositorio. Deben configurarse mediante `.env` local o variables de Cloud Foundry.

Ejemplo de `.env.example`:

```env
API_URL=https://sap-api-b4.674318.xyz/logs/current?page=1
API_BASE_URL=https://sap-api-b4.674318.xyz/logs/current?page=1
API_KEY=your_api_key_here

ALERT_API_URL=https://sap-api-b4.674318.xyz/alerts
TEAM_NAME=ROCKET_POWERS

OUTPUT_FOLDER=shared_data/raw_logs.json
OUTPUT_PARQUET_FOLDER=shared_data/processed_logs.parquet

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash-lite

MAX_ALERTS_PER_CYCLE=5
```

---

## 18. Despliegue

### Validar sintaxis

```bash
python -m py_compile main.py api/routes_assistant.py api/routes_metrics.py api/routes_visualization.py soc/risk_engine.py
python -c "import main; print('main import OK')"
```

### Desplegar

```bash
cf push
```

### Revisar estado

```bash
cf apps
```

La aplicación debe aparecer como:

```text
rocket-powers-soc   started   1/1
```

### Revisar logs

```bash
cf logs rocket-powers-soc --recent
```

---

## 19. Validación del sistema

Para validar la solución:

1. Abrir el dashboard:

```text
https://rocket-powers-soc.cfapps.us10-001.hana.ondemand.com/dashboard
```

2. Revisar que el status indique que el dashboard cargó correctamente.
3. Usar el filtro `Solo seguridad`.
4. Revisar eventos HTTP 401, 403 y 429.
5. Cambiar a `Solo operativas` para revisar latencia, tokens y errores.
6. Consultar al agente SOC con IA.
7. Revisar logs de Cloud Foundry para confirmar ciclos automáticos.

---

## 20. Limitaciones

- El modelo detecta anomalías, no ataques confirmados.
- La clasificación de seguridad depende de señales interpretables posteriores al modelo.
- Los eventos HTTP 401, 403 y 429 indican señales para investigación SOC, no confirmación definitiva de ataque.
- La disponibilidad del agente generativo depende de la cuota/API key configurada.
- El sistema puede requerir calibración adicional de umbrales dependiendo del volumen real de logs.
- La confirmación de incidentes requiere análisis humano adicional.

---

## 21. Próximos pasos

- Agregar tabla dedicada de alertas enviadas para auditoría.
- Mejorar deduplicación de alertas por `EVENT_HASH`.
- Agregar reglas de correlación por IP, servicio y ventana temporal.
- Agregar detección más explícita de prompt injection usando modelos supervisados.
- Agregar integración con SAP Analytics Cloud.
- Crear playbooks automáticos para cada tipo de señal.
- Incorporar métricas de precisión mediante validación manual de incidentes.

---

## 22. Conclusión

Rocket Powers SOC Defense implementa un sistema SOC funcional para monitoreo de tráfico LLM en la nube. La solución combina SAP HANA Cloud, FastAPI, Machine Learning, reglas SOC interpretables, dashboard forense y un agente con IA generativa.

El valor principal del sistema es que no se limita a detectar anomalías. También interpreta el contexto, clasifica eventos, reduce ruido y ayuda al analista a priorizar investigación. Esta arquitectura permite una operación más cercana a un SOC real, donde la detección automática debe complementarse con reglas explicables, visualización clara y apoyo inteligente para la toma de decisiones.
