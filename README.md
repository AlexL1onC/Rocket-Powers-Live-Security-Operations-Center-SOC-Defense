# Rocket Powers SOC Defense

Sistema SOC en tiempo real para detectar anomalías en logs de uso de LLMs y escalar amenazas probables mediante la API del hackathon SAP.

## Resumen

Rocket Powers SOC Defense implementa un pipeline de defensa operacional para monitorear eventos relacionados con servicios LLM. La solución consume logs desde la API del reto, normaliza los datos, los almacena en SAP HANA Cloud, ejecuta un modelo de detección de anomalías y escala únicamente eventos con señales adicionales de riesgo.

El sistema no envía una alerta por cada anomalía. Primero detecta desviaciones estadísticas y después aplica un motor SOC de severidad para reducir falsos positivos y evitar alert fatigue.

## Diferenciador

La solución no es solo un notebook de machine learning. Es un sistema desplegado de extremo a extremo:

- Extracción automática cada 30 minutos desde la API del reto.
- Backend FastAPI desplegado en SAP BTP Cloud Foundry.
- Persistencia de logs en SAP HANA Cloud.
- Feature engineering en producción.
- Modelo no supervisado de detección de anomalías.
- Motor de severidad basado en score y señales de riesgo.
- Envío automático de alertas mediante POST a la API del concurso.
- Endpoints de diagnóstico para monitoreo, calibración y análisis forense.

## Arquitectura

```text
SAP Hackathon Logs API
        ↓
FastAPI Scheduler
        ↓
Data Extraction
        ↓
Processor / Feature Engineering
        ↓
SAP HANA Cloud
        ↓
Isolation Forest Anomaly Detection
        ↓
Risk Context + Severity Engine
        ↓
Alert Decision Engine
        ↓
SAP Alert API
        ↓
Forensic Reporting / Dashboard
```

## Tech Stack

- Python
- FastAPI
- SAP BTP Cloud Foundry
- SAP HANA Cloud
- hdbcli
- pandas / NumPy
- scikit-learn
- APScheduler
- REST APIs

## Pipeline

1. El scheduler ejecuta el ciclo SOC cada 30 minutos.
2. Se extraen logs desde la API del hackathon.
3. Los datos se limpian, normalizan y convierten a estructura tabular.
4. Los registros se cargan en SAP HANA Cloud mediante UPSERT.
5. Se generan features temporales, operativas y de comportamiento LLM.
6. El modelo detecta anomalías.
7. El motor SOC asigna severidad: Low, Medium o High.
8. Solo eventos con señales suficientes se escalan como alertas.
9. Las alertas se envían mediante POST a la API del concurso.

## Feature Engineering

El sistema construye variables como:

- `prompt_length`
- `token_density`
- `latency_per_token`
- `cost_intensity`
- `hour`
- `day_of_week`
- `is_night`
- `is_weekend`
- `requests_per_minute`
- `errors_per_minute`
- `avg_latency_per_minute`
- `tokens_per_minute`
- variables categóricas codificadas para proveedor, modelo, estatus y categoría del prompt

## Modelo

Se usa un modelo no supervisado basado en Isolation Forest para identificar eventos que se desvían del comportamiento normal.

El modelo no se presenta como un clasificador absoluto de ataques. Su objetivo es reducir el volumen de revisión y detectar patrones anómalos. Después, un motor SOC correlaciona esas anomalías con señales adicionales de riesgo.

## Motor de Severidad

La severidad se calcula usando:

- Score de anomalía.
- Errores HTTP.
- Estatus LLM como error, timeout o failure.
- Alto volumen de tokens.
- Alta latencia.
- Palabras sospechosas en prompts.

Reglas generales:

```text
Low:
  anomalía débil o sin señales suficientes de riesgo.

Medium:
  score anómalo + señal operativa de riesgo.

High:
  score crítico + señal operativa de riesgo.
```

## Estrategia Anti Alert Fatigue

No todas las anomalías se envían por API. Todas quedan disponibles para análisis forense, pero solo se escalan amenazas probables.

Criterios de escalamiento:

- Eventos High siempre se escalan.
- Eventos Medium se escalan cuando tienen señal de riesgo.
- Eventos Low solo se escalan si tienen evidencia explícita de prompt sospechoso.
- Se limita el envío a un máximo configurable de alertas por ciclo.

Variables relevantes:

```env
MAX_ALERTS_PER_CYCLE=5
ALERT_SCORE_THRESHOLD=-0.05
```

## Resultados Observados

```text
Total logs procesados:        2,810,476
Eventos normales:             26,617
Anomalías detectadas:         546,828
Eventos pendientes:           2,237,031
Score mínimo observado:       -0.0588499
Score promedio observado:     -0.0096964
Anomalías con score <= -0.05: 35
```

Resumen de señales de riesgo:

```text
HTTP risk:       79,509
Status risk:     54,535
High tokens:     31,943
High latency:    60,753
```

Estos números muestran que el modelo identifica anomalías a gran escala, pero que el motor SOC reduce el ruido y escala solo eventos priorizados.

## Endpoints Principales

```text
GET  /
GET  /debug_hana_connection
GET  /soc_summary
GET  /anomaly_risk_summary
GET  /anomaly_score_distribution
GET  /top_anomalies
GET  /export_datos_urgente
```

## Variables de Entorno

Crear un archivo `.env` local o configurar variables en Cloud Foundry


## Despliegue

La aplicación se despliega en SAP BTP Cloud Foundry:

```bash
cf push
```

Para revisar logs:

```bash
cf logs rocket-powers-soc
```

Para revisar variables:

```bash
cf env rocket-powers-soc
```

## Estado Actual

La solución se encuentra desplegada y operando en SAP BTP Cloud Foundry. El sistema ejecuta ciclos automáticos de ingesta, procesamiento, almacenamiento, detección y alertamiento.

## Equipo

Rocket Powers
