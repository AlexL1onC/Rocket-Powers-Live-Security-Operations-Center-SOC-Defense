from config import ALERT_SCORE_THRESHOLD


def get_risk_context(row):
    score = float(row.get("ANOMALY_SCORE", 0) or 0)
    http = int(row.get("HTTP_STATUS_CODE", 0) or 0)
    status = str(row.get("LLM_STATUS", "") or "").lower()
    tokens = float(row.get("LLM_TOTAL_TOKENS", 0) or 0)
    latency = float(row.get("LLM_RESPONSE_TIME_MS", 0) or 0)
    provider = str(row.get("LLM_PROVIDER", "") or "").strip()
    model_id = str(row.get("LLM_MODEL_ID", "") or "").strip()
    prompt = str(row.get("LLM_PROMPT", "") or "").lower()

    requests_per_minute = float(row.get("requests_per_minute", 0) or 0)
    errors_per_minute = float(row.get("errors_per_minute", 0) or 0)

    # Prompts administrativos/operativos que NO deben tratarse como security.
    benign_admin_patterns = [
        "summarise llm api token consumption",
        "summarize llm api token consumption",
        "highlight cost drivers",
        "exceeded 80% of its monthly llm token budget",
        "suggest prompt optimisations to reduce token usage",
        "suggest prompt optimizations to reduce token usage",
        "review the system prompt used by",
        "recommend immediate actions",
        "reduce ambiguous or off-topic responses",
    ]

    is_benign_admin_prompt = any(pattern in prompt for pattern in benign_admin_patterns)

    # Señales explícitas de ataque o abuso.
    # Nota: NO usamos "system prompt" solo, porque puede ser una tarea legítima.
    security_keywords = [
        "ignore previous instructions",
        "ignore all previous instructions",
        "disregard previous instructions",
        "forget previous instructions",
        "override previous instructions",
        "jailbreak",
        "developer mode",
        "dan mode",
        "do anything now",
        "reveal your system prompt",
        "show me your system prompt",
        "print your system prompt",
        "leak your system prompt",
        "exfiltrate",
        "steal credentials",
        "credentials",
        "api key",
        "access token",
        "bearer token",
        "password",
        "secret key",
        "private key",
        "sql injection",
        "union select",
        "drop table",
        "delete from",
        "rm -rf",
        "reverse shell",
        "/etc/passwd",
        "admin access",
        "bypass authentication",
        "privilege escalation",
    ]

    has_suspicious_prompt = (
        not is_benign_admin_prompt
        and any(keyword in prompt for keyword in security_keywords)
    )

    is_incomplete_generic_event = (
        http in [200, 201, 204, 301, 302]
        and tokens == 0
        and latency == 0
        and provider == ""
        and model_id == ""
    )

    # Operacional: útil para monitoreo, pero NO security por sí solo.
    operational_signal = (
        status in ["error", "timeout", "failed", "failure"]
        or http in [400, 408, 500, 502, 503]
        or tokens >= 2500
        or latency >= 10000
    )

    # Seguridad real.
    auth_or_access_risk = http in [401, 403]

    # Abuso volumétrico/rate limit.
    # Solo es seguridad si hay 429 o volumen real; no por timeout/error aislado.
    rate_limit_or_abuse = (
        http == 429
        or requests_per_minute >= 300
        or errors_per_minute >= 50
    )

    security_signal = (
        has_suspicious_prompt
        or auth_or_access_risk
        or rate_limit_or_abuse
    )

    security_reasons = []
    operational_reasons = []

    if has_suspicious_prompt:
        security_reasons.append("suspicious_prompt")
    if auth_or_access_risk:
        security_reasons.append("auth_or_access_risk")
    if rate_limit_or_abuse:
        security_reasons.append("rate_limit_or_abuse")

    if status in ["error", "timeout", "failed", "failure"]:
        operational_reasons.append(f"llm_status_{status}")
    if latency >= 10000:
        operational_reasons.append("high_latency")
    if tokens >= 2500:
        operational_reasons.append("high_token_usage")
    if http in [400, 408, 500, 502, 503]:
        operational_reasons.append(f"http_{http}")

    reasons = security_reasons + operational_reasons

    return {
        "score": score,
        "http": http,
        "status": status,
        "tokens": tokens,
        "latency": latency,
        "requests_per_minute": requests_per_minute,
        "errors_per_minute": errors_per_minute,
        "is_benign_admin_prompt": is_benign_admin_prompt,
        "has_suspicious_prompt": has_suspicious_prompt,
        "is_incomplete_generic_event": is_incomplete_generic_event,
        "operational_signal": operational_signal,
        "security_signal": security_signal,
        "auth_or_access_risk": auth_or_access_risk,
        "rate_limit_or_abuse": rate_limit_or_abuse,
        "security_reasons": security_reasons,
        "operational_reasons": operational_reasons,
        "reasons": reasons,
    }



def assign_severity(row):
    if row["LABEL"] != "Anomalia":
        return "Normal"

    ctx = get_risk_context(row)
    score = ctx["score"]

    # High: seguridad explícita + score fuerte.
    if ctx["security_signal"] and score <= -0.05:
        return "High"

    # Medium: seguridad explícita + anomalía razonable.
    if ctx["security_signal"] and score <= -0.03:
        return "Medium"

    # Operational: anomalía útil, pero no seguridad.
    if ctx["operational_signal"]:
        return "Operational"

    return "Low"








def is_alert_worthy(row):
    ctx = get_risk_context(row)

    if ctx["is_incomplete_generic_event"]:
        return False

    # Si no hay evidencia security, no se escala a la API del concurso.
    if not ctx["security_signal"]:
        return False

    # Prompt malicioso explícito: security.
    if ctx["has_suspicious_prompt"]:
        return True

    # 401/403: posible acceso no autorizado.
    if ctx["auth_or_access_risk"]:
        return True

    # 429 o abuso volumétrico.
    if ctx["rate_limit_or_abuse"]:
        return True

    return False

