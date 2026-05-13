let latencyChart = null;
let tokensChart = null;
let typeChart = null;
let scoreChart = null;
let securityTimelineChart = null;
let securityHttpChart = null;

function fmt(n) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return "-";
    return Number(n).toLocaleString();
}

function destroyChart(chart) {
    if (chart) {
        chart.destroy();
    }
}

function setStatus(text, type = "ok") {
    const el = document.getElementById("loadStatus");
    el.innerText = text;
    el.className = type === "ok" ? "status-pill" : "warning-pill";
}

function toggleAgentSidebar() {
    const appShell = document.querySelector(".app-shell");
    const sidebar = document.getElementById("agentSidebar");
    const btn = document.getElementById("sidebarToggleBtn");

    if (!appShell || !sidebar || !btn) return;

    appShell.classList.toggle("agent-collapsed");
    sidebar.classList.toggle("collapsed");

    if (appShell.classList.contains("agent-collapsed")) {
        btn.innerText = "⮜"; // abrir hacia la izquierda
    } else {
        btn.innerText = "⮞"; // cerrar hacia la derecha
    }

    setTimeout(() => {
        resizeCharts();
    }, 300);
}



function scrollToSection(sectionId) {
    const container = document.getElementById("dashboardScroll");
    const section = document.getElementById(sectionId);

    if (!container || !section) {
        console.warn("No se encontró el contenedor o la sección:", {
            container: !!container,
            sectionId,
            section: !!section
        });
        return;
    }

    const targetPosition = section.offsetTop - 16;

    container.scrollTo({
        top: targetPosition,
        behavior: "smooth"
    });
}



function resizeCharts() {
    [
        latencyChart,
        tokensChart,
        typeChart,
        scoreChart,
        securityTimelineChart,
        securityHttpChart
    ].forEach(chart => {
        if (chart) {
            try {
                chart.resize();
            } catch (e) {}
        }
    });
}

function translateType(type) {
    if (type === "Prompt Security") return "Seguridad: Prompt";
    if (type === "Access Security") return "Seguridad: Acceso";
    if (type === "Rate Limit / Abuse") return "Seguridad: Rate Limit";
    if (type === "Security") return "Seguridad";
    if (type === "Operational") return "Operativa";
    return type || "-";
}

function getTypeClass(type) {
    if (type === "Prompt Security") return "tag-prompt";
    if (type === "Access Security") return "tag-access";
    if (type === "Rate Limit / Abuse") return "tag-ratelimit";
    if (type === "Security") return "tag-security";
    if (type === "Operational") return "tag-operational";
    return "tag-operational";
}

function translateFilter(type) {
    if (type === "security") return "Solo seguridad";
    if (type === "operational") return "Solo operativas";
    if (type === "all") return "Todas";
    return type;
}

function translateReason(reason) {
    const map = {
        "suspicious_prompt": "prompt sospechoso",
        "auth_or_access_risk": "riesgo de acceso no autorizado",
        "rate_limit_or_abuse": "abuso de rate limit o tráfico",
        "high_latency": "latencia alta",
        "high_token_usage": "uso alto de tokens",
        "llm_status_timeout": "timeout del LLM",
        "llm_status_error": "error del LLM",
        "llm_status_failed": "fallo del LLM",
        "llm_status_failure": "fallo del LLM",
        "http_400": "HTTP 400",
        "http_408": "HTTP 408",
        "http_500": "HTTP 500",
        "http_502": "HTTP 502",
        "http_503": "HTTP 503"
    };

    return map[reason] || reason;
}

function translateReasons(reasonsText) {
    if (!reasonsText) return "-";
    return reasonsText
        .split(",")
        .map(r => translateReason(r.trim()))
        .join(", ");
}

function escapeHtml(value) {
    if (value === null || value === undefined) return "-";

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

async function loadDashboard() {
    try {
        setStatus("Cargando datos del SOC...", "ok");

        const anomalyType = document.getElementById("anomalyTypeFilter").value;
        const hours = document.getElementById("hoursFilter").value;

        const [viz, summary, risk, scoreDistribution] = await Promise.all([
            fetch(`/viz_data?hours=${hours}&limit=50000&anomaly_type=${anomalyType}`).then(r => r.json()),
            fetch("/soc_summary").then(r => r.json()),
            fetch("/anomaly_risk_summary").then(r => r.json()),
            fetch("/anomaly_score_distribution").then(r => r.json())
        ]);

        const s = viz.summary || {};

        document.getElementById("eventsWindow").innerText = fmt(s.total_events);
        document.getElementById("anomaliesWindow").innerText = fmt(s.total_anomalies);
        document.getElementById("visibleWindow").innerText = fmt(s.visible_anomalies);
        document.getElementById("securityWindow").innerText = fmt(s.security_anomalies);

        document.getElementById("funnelEvents").innerText = fmt(s.total_events);
        document.getElementById("funnelAnomalies").innerText = fmt(s.total_anomalies);
        document.getElementById("funnelOperational").innerText = fmt(s.operational_anomalies);
        document.getElementById("funnelSecurity").innerText = fmt(s.security_anomalies);

        const securityLabels = (viz.security_series || []).map(x => x.time);
        const securityEvents = (viz.security_series || []).map(x => x.security_events);

        const total401 = (viz.security_series || []).reduce((acc, x) => acc + (x.http_401 || 0), 0);
        const total403 = (viz.security_series || []).reduce((acc, x) => acc + (x.http_403 || 0), 0);
        const total429 = (viz.security_series || []).reduce((acc, x) => acc + (x.http_429 || 0), 0);

        destroyChart(securityTimelineChart);
        securityTimelineChart = new Chart(document.getElementById("securityTimelineChart"), {
            type: "bar",
            data: {
                labels: securityLabels,
                datasets: [{
                    label: "Eventos de seguridad",
                    data: securityEvents
                }]
            },
            options: chartOptions("Eventos")
        });

        destroyChart(securityHttpChart);
        securityHttpChart = new Chart(document.getElementById("securityHttpChart"), {
            type: "bar",
            data: {
                labels: ["HTTP 401", "HTTP 403", "HTTP 429"],
                datasets: [{
                    label: "Eventos",
                    data: [total401, total403, total429]
                }]
            },
            options: chartOptions("Eventos")
        });

        const labels = viz.series.map(x => x.time);
        const avgLatency = viz.series.map(x => x.avg_latency);
        const anomalyLatency = viz.series.map(x => x.anomaly_latency);

        const avgTokens = viz.series.map(x => x.avg_tokens);
        const anomalyTokens = viz.series.map(x => x.anomaly_tokens);

        destroyChart(latencyChart);
        latencyChart = new Chart(document.getElementById("latencyChart"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Latencia promedio real",
                        data: avgLatency,
                        borderWidth: 2,
                        tension: 0.25,
                        pointRadius: 1
                    },
                    {
                        label: "Punto anómalo filtrado",
                        data: anomalyLatency,
                        showLine: false,
                        pointRadius: 6,
                        pointHoverRadius: 8
                    }
                ]
            },
            options: chartOptions("Latencia (ms)")
        });

        destroyChart(tokensChart);
        tokensChart = new Chart(document.getElementById("tokensChart"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Tokens promedio reales",
                        data: avgTokens,
                        borderWidth: 2,
                        tension: 0.25,
                        pointRadius: 1
                    },
                    {
                        label: "Punto anómalo filtrado",
                        data: anomalyTokens,
                        showLine: false,
                        pointRadius: 6,
                        pointHoverRadius: 8
                    }
                ]
            },
            options: chartOptions("Tokens")
        });

        destroyChart(typeChart);
        typeChart = new Chart(document.getElementById("typeChart"), {
            type: "bar",
            data: {
                labels: ["Operativas", "Seguridad"],
                datasets: [{
                    label: "Cantidad de anomalías",
                    data: [s.operational_anomalies || 0, s.security_anomalies || 0]
                }]
            },
            options: chartOptions("Eventos")
        });

        destroyChart(scoreChart);
        scoreChart = new Chart(document.getElementById("scoreChart"), {
            type: "bar",
            data: {
                labels: scoreDistribution.map(x => x.SCORE_BUCKET),
                datasets: [{
                    label: "Anomalías por bucket de score",
                    data: scoreDistribution.map(x => x.TOTAL)
                }]
            },
            options: chartOptions("Anomalías")
        });

        const tbody = document.getElementById("anomalyTable");
        tbody.innerHTML = "";

        if (!viz.top_anomalies || viz.top_anomalies.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="15">
                        No se encontraron anomalías para el filtro seleccionado.
                        Cambia la ventana de tiempo o selecciona "Todas" para revisar contexto forense.
                    </td>
                </tr>`;
        } else {
            viz.top_anomalies.forEach(row => {
                const tr = document.createElement("tr");
                const typeClass = getTypeClass(row.alert_type);

                tr.innerHTML = `
                    <td>${row.timestamp || "-"}</td>
                    <td><span class="tag ${typeClass}">${translateType(row.alert_type)}</span></td>
                    <td>${row.provider || "-"}</td>
                    <td>${row.service || "-"}</td>
                    <td>${row.source_ip || "-"}</td>
                    <td>${row.location || "-"}</td>
                    <td>${row.model || "-"}</td>
                    <td>${row.status || "-"}</td>
                    <td>${row.http ?? "-"}</td>
                    <td>${fmt(row.tokens)}</td>
                    <td>${fmt(row.latency)} ms</td>
                    <td>${row.score ?? "-"}</td>
                    <td class="security-evidence">${translateReasons(row.security_reasons) || "-"}</td>
                    <td class="operational-context">${translateReasons(row.operational_reasons) || "-"}</td>
                    <td class="prompt-cell">${escapeHtml(row.prompt_preview || "-")}</td>
                `;

                tbody.appendChild(tr);
            });
        }

        setStatus(
            `Dashboard actualizado. Filtro: ${translateFilter(s.active_filter)} | Ventana: ${s.hours} horas | ` +
            `Logs totales en tabla: ${fmt(summary.TOTAL_LOGS)} | Anomalías totales: ${fmt(summary.TOTAL_ANOMALIAS)}.`,
            "ok"
        );

        resizeCharts();

    } catch (err) {
        console.error(err);
        setStatus("No se pudo cargar el dashboard. Revisa los endpoints de la API.", "warn");
    }
}

function chartOptions(yTitle) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: "#e5e7eb"
                }
            },
            tooltip: {
                mode: "index",
                intersect: false
            }
        },
        scales: {
            x: {
                ticks: {
                    color: "#e5e7eb",
                    maxRotation: 45,
                    minRotation: 45
                },
                grid: {
                    color: "#1f2937"
                }
            },
            y: {
                title: {
                    display: true,
                    text: yTitle,
                    color: "#e5e7eb"
                },
                ticks: {
                    color: "#e5e7eb"
                },
                grid: {
                    color: "#1f2937"
                }
            }
        }
    };
}

/* =========================
   AGENTE SOC
========================== */

function quickAsk(question) {
    document.getElementById("assistantQuestion").value = question;
    askAssistant();
}

async function askAssistant() {
    const question = document.getElementById("assistantQuestion").value || "";
    const hours = Number(document.getElementById("hoursFilter").value || 72);
    const answerBox = document.getElementById("assistantAnswer");

    if (!question.trim()) {
        answerBox.innerText = "Escribe una pregunta para el agente SOC.";
        return;
    }

    answerBox.innerText = "El agente está consultando SAP HANA y analizando el contexto con IA...";

    try {
        const response = await fetch("/soc_assistant", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                question: question,
                hours: hours
            })
        });

        if (!response.ok) {
            throw new Error("Error HTTP " + response.status);
        }

        const data = await response.json();

        const modeLabel =
            data.mode === "ai_agent"
                ? "Modo: IA generativa con contexto SOC"
                : "Modo: fallback contextual";

        answerBox.innerText =
            modeLabel +
            "\n\n" +
            data.answer +
            "\n\nMétricas consultadas:" +
            `\n- Eventos totales: ${fmt(data.metrics.total_events)}` +
            `\n- Anomalías ML: ${fmt(data.metrics.total_anomalies)}` +
            `\n- Eventos de seguridad: ${fmt(data.metrics.security_events)}` +
            `\n- Anomalías operativas: ${fmt(data.metrics.operational_events)}` +
            `\n- HTTP 401: ${fmt(data.metrics.http_401)}` +
            `\n- HTTP 403: ${fmt(data.metrics.http_403)}` +
            `\n- HTTP 429: ${fmt(data.metrics.http_429)}`;

    } catch (error) {
        console.error(error);
        answerBox.innerText = "No se pudo consultar el agente SOC. Revisa el endpoint /soc_assistant.";
    }
}

window.loadDashboard = loadDashboard;
window.quickAsk = quickAsk;
window.askAssistant = askAssistant;
window.toggleAgentSidebar = toggleAgentSidebar;
window.scrollToSection = scrollToSection;

// Permite enviar con Enter en el input del agente
document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("assistantQuestion");

    if (input) {
        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                askAssistant();
            }
        });
    }
});



loadDashboard();