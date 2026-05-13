# Reporte Técnico de Arquitectura — Rocket Powers SOC Defense

## 1. Resumen Ejecutivo

Rocket Powers SOC Defense es un sistema de monitoreo y defensa en tiempo real para identificar anomalías y amenazas probables en logs relacionados con servicios LLM. La solución fue diseñada para operar como un SOC automatizado: extrae logs desde la API del reto, los procesa, los almacena en SAP HANA Cloud, ejecuta un modelo de detección de anomalías y envía alertas a la API del concurso únicamente cuando el evento cumple criterios de riesgo.

La principal diferencia del sistema es su arquitectura de dos capas. Primero, un modelo no supervisado detecta desviaciones estadísticas en el comportamiento de los logs. Después, un motor SOC evalúa señales adicionales como errores, timeouts, alto consumo de tokens, alta latencia o patrones sospechosos en prompts para decidir si el evento debe escalarse como alerta. Esto permite reducir falsos positivos y evitar alert fatigue.

## 2. Objetivo del Sistema

El objetivo del proyecto es construir un sistema que identifique amenazas o anomalías en prompts y eventos LLM, y que pueda enviar reportes automáticos a la API proporcionada por el hackathon.

El sistema debe cumplir con dos funciones principales:

1. Extraer logs de la API del reto de forma periódica.
2. Analizar los eventos y enviar alertas mediante POST cuando se detecten amenazas probables.

## 3. Arquitectura General

```text
SAP Hackathon Logs API
        ↓
FastAPI Backend
        ↓
Scheduler cada 30 minutos
        ↓
Data Extraction
        ↓
Processor / Cleaning
        ↓
SAP HANA Cloud
        ↓
Feature Engineering
        ↓
ML Anomaly Detection
        ↓
Risk Context Engine
        ↓
Severity Engine
        ↓
Alert Decision Engine
        ↓
SAP Alert API
        ↓
Forensic Reporting / Dashboard
```

## 4. Componentes Principales

### 4.1 FastAPI Backend

El backend se implementó con FastAPI y se desplegó en SAP BTP Cloud Foundry. Este servicio ejecuta el ciclo principal del SOC y expone endpoints de salud, diagnóstico y análisis.

### 4.2 Scheduler

Se utiliza APScheduler para ejecutar el ciclo SOC cada 30 minutos. Además, al iniciar la aplicación se ejecuta una ingesta inicial en segundo plano para validar operación inmediata.

### 4.3 Data Extraction

El módulo de extracción consume la API del reto y descarga los logs paginados. Los registros se almacenan temporalmente como JSON antes de ser procesados.

### 4.4 Processor

El módulo de procesamiento normaliza campos clave: IP origen, timestamp, localización, proveedor LLM, modelo LLM, prompt, tokens, costo, latencia, estatus HTTP y estatus LLM.

### 4.5 SAP HANA Cloud

SAP HANA Cloud se utiliza como base central para persistir los eventos. La tabla principal es `SOC_ANOMALY_LOGS`, donde se almacenan los logs, los scores de anomalía y las etiquetas asignadas por el modelo.

### 4.6 Modelo de Anomalías

Se usa un modelo no supervisado basado en Isolation Forest. El modelo recibe features numéricas y categóricas codificadas, y produce:

- `ANOMALY_SCORE`
- `LABEL`: Normal o Anomalia

El modelo permite reducir millones de registros a un subconjunto investigable por el SOC.

## 5. Feature Engineering

El sistema genera features en producción para mantener consistencia con el entrenamiento.

| Feature | Descripción |
|---|---|
| `prompt_length` | Longitud del prompt |
| `token_density` | Tokens por longitud de prompt |
| `latency_per_token` | Latencia por token |
| `cost_intensity` | Costo por token |
| `hour` | Hora del evento |
| `day_of_week` | Día de la semana |
| `is_night` | Indicador de horario nocturno |
| `is_weekend` | Indicador de fin de semana |
| `requests_per_minute` | Volumen de eventos por minuto |
| `errors_per_minute` | Errores por minuto |
| `avg_latency_per_minute` | Latencia promedio por minuto |
| `tokens_per_minute` | Tokens acumulados por minuto |

También se codifican variables categóricas como localización, proveedor, categoría de prompt, estatus LLM y tipo de tarea.

## 6. Motor de Riesgo SOC

Después de la predicción del modelo, el sistema ejecuta un motor de riesgo que extrae señales operativas:

- HTTP 400, 401, 403, 408, 429, 500, 502, 503.
- Estatus LLM: error, timeout, blocked, failed o failure.
- Alto consumo de tokens.
- Alta latencia.
- Palabras sospechosas en el prompt.
- Eventos incompletos o genéricos que deben ignorarse.

Esta capa permite distinguir entre anomalías informativas y amenazas probables.

## 7. Clasificación de Severidad

La severidad se asigna con base en el score del modelo y las señales de riesgo.

```text
Low:
  Evento anómalo, pero sin evidencia suficiente para escalar.

Medium:
  Score anómalo + señal operativa de riesgo.

High:
  Score crítico + señal operativa de riesgo.
```

La lógica implementada usa umbrales calibrados con datos reales:

```text
High:   score <= -0.05 y señal de riesgo.
Medium: score <= -0.03 y señal de riesgo.
Low:    resto de anomalías.
```

## 8. Estrategia de Alertamiento

El sistema no envía una alerta por cada anomalía. La política de alertamiento es:

- High: se escala por API.
- Medium: se escala si mantiene señal real de riesgo.
- Low: solo se escala si contiene evidencia explícita de prompt sospechoso.
- Se limita el número de alertas por ciclo usando `MAX_ALERTS_PER_CYCLE`.

Esta estrategia reduce ruido operativo y evita alert fatigue.

## 9. Resultados Operativos

```text
Total logs:                  2,810,476
Eventos normales:             26,617
Anomalías detectadas:         546,828
Eventos pendientes:         2,237,031
Score mínimo:                -0.0588499
Score máximo:                 0.0219018
Score promedio:              -0.0096964
```

Resumen de riesgo:

```text
HTTP risk:       79,509
Status risk:     54,535
High tokens:     31,943
High latency:    60,753
Score <= -0.05:  35
Score <= -0.10:  0
Score <= -0.15:  0
```

Estos resultados muestran que el modelo identifica una cantidad considerable de anomalías, pero que solo una fracción reducida alcanza niveles críticos de score. Por ello, el motor SOC es esencial para priorizar.

## 10. Interpretación de los Resultados

El modelo no debe interpretarse como un clasificador absoluto de ataques confirmados. Su rol es actuar como primera capa de reducción de ruido, detectando eventos que se salen del patrón normal.

La utilidad del sistema está en la combinación de:

1. Detección estadística de anomalías.
2. Correlación con señales operativas.
3. Escalamiento selectivo por severidad.

Ejemplos de eventos útiles para investigación incluyen:

- Timeouts con latencias superiores a 30 segundos.
- Eventos con alto consumo de tokens.
- Errores LLM recurrentes.
- Combinaciones de modelo, ubicación y comportamiento inusual.
- Prompts con palabras asociadas a inyección o exfiltración.

## 11. Endpoints de Diagnóstico

| Endpoint | Descripción |
|---|---|
| `/` | Health check |
| `/debug_hana_connection` | Verifica usuario/schema de HANA |
| `/soc_summary` | Resumen general del SOC |
| `/anomaly_risk_summary` | Resumen de señales de riesgo |
| `/anomaly_score_distribution` | Distribución de scores |
| `/top_anomalies` | Top anomalías por score |
| `/export_datos_urgente` | Exportación CSV |

## 12. Despliegue

La aplicación está desplegada en SAP BTP Cloud Foundry mediante:

```bash
cf push
```

El servicio usa el binding de SAP HANA Cloud mediante `VCAP_SERVICES`. Para evitar confusiones con credenciales locales, se configuró `HANA_SERVICE_NAME`.

## 13. Consideraciones de Seguridad

- No se suben tokens ni credenciales al repositorio.
- Se usa `.env.example` para documentar variables requeridas.
- Las credenciales reales viven en variables de entorno de Cloud Foundry.
- La API de alertas usa token mediante encabezado Authorization Bearer.

## 14. Limitaciones

- El modelo es no supervisado, por lo que identifica desviaciones estadísticas y no ataques confirmados.
- La clasificación final de amenaza depende de la correlación con señales de riesgo.
- Algunas anomalías pueden ser falsos positivos o eventos incompletos.
- Existe backlog de registros pendientes de análisis debido al volumen de datos y a los límites de memoria del entorno.
- La visualización completa depende del acceso a los datos correctos en HANA o de endpoints intermedios expuestos por la API.

## 15. Próximos Pasos

- Crear dashboard ejecutivo con KPIs principales.
- Agregar tabla dedicada de alertas enviadas si se requiere monitoreo interno.
- Calibrar umbrales con más datos y validación manual.
- Agregar explicación del evento en el mensaje de alerta.
- Implementar auto-start de HANA Cloud mediante SAP Service Manager.
- Mejorar MLOps con versionado formal del modelo y métricas por ciclo.

## 16. Conclusión

Rocket Powers SOC Defense demuestra una arquitectura SOC funcional de extremo a extremo: ingesta en tiempo real, almacenamiento en SAP HANA Cloud, detección de anomalías, priorización operativa y alertamiento automático.

El valor principal del sistema está en convertir grandes volúmenes de logs LLM en eventos priorizados y accionables, reduciendo ruido operativo y evitando alert fatigue.
