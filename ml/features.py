import pandas as pd
import numpy as np
from ml.model_loader import model, artifact

def classify_prompt(prompt):
    if pd.isna(prompt):
        return "other"

    text = str(prompt).lower()

    if any(x in text for x in ["summarize", "summarise", "resumen", "resume"]):
        return "summarization"
    if any(x in text for x in ["generate", "draft", "write", "crear", "genera", "redacta"]):
        return "generation"
    if any(x in text for x in ["error", "failure", "exception", "fallo", "timeout"]):
        return "system_task"

    return "other"



def get_expected_feature_columns():
    if hasattr(model, "feature_names_in_"):
        return list(model.feature_names_in_)

    return artifact["feature_columns"]



def build_features(df_raw):
    df = df_raw.copy()

    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
    df = df[df["TIMESTAMP"].notna()].copy()

    numeric_base = [
        "LLM_TOTAL_TOKENS",
        "LLM_COST_USD",
        "LLM_RESPONSE_TIME_MS",
        "HTTP_STATUS_CODE",
    ]

    for col in numeric_base:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in ["LOCATION", "LLM_PROVIDER", "LLM_PROMPT_CATEGORY", "LLM_STATUS", "LLM_PROMPT"]:
        if col not in df.columns:
            df[col] = "Unknown"
        df[col] = df[col].fillna("Unknown").astype(str)

    df["hour"] = df["TIMESTAMP"].dt.hour
    df["day_of_week"] = df["TIMESTAMP"].dt.dayofweek
    df["day_of_month"] = df["TIMESTAMP"].dt.day
    df["month"] = df["TIMESTAMP"].dt.month
    df["is_night"] = df["hour"].between(0, 5).astype(int)
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["minute_window"] = df["TIMESTAMP"].dt.floor("min")

    df["requests_per_minute"] = df.groupby("minute_window")["EVENT_HASH"].transform("count")

    error_status = df["LLM_STATUS"].str.lower().isin(["error", "timeout", "failed", "failure"])
    http_error = df["HTTP_STATUS_CODE"] >= 400
    df["_is_error"] = (error_status | http_error).astype(int)

    df["errors_per_minute"] = df.groupby("minute_window")["_is_error"].transform("sum")
    df["avg_latency_per_minute"] = df.groupby("minute_window")["LLM_RESPONSE_TIME_MS"].transform("mean")
    df["tokens_per_minute"] = df.groupby("minute_window")["LLM_TOTAL_TOKENS"].transform("sum")

    df["prompt_length"] = df["LLM_PROMPT"].astype(str).str.len().replace(0, 1)
    df["latency_per_token"] = df["LLM_RESPONSE_TIME_MS"] / df["LLM_TOTAL_TOKENS"].replace(0, 1)
    df["cost_intensity"] = df["LLM_COST_USD"] / df["LLM_TOTAL_TOKENS"].replace(0, 1)
    df["token_density"] = df["LLM_TOTAL_TOKENS"] / df["prompt_length"].replace(0, 1)
    df["task_type"] = df["LLM_PROMPT"].apply(classify_prompt)

    num_features = artifact["num_features"]
    cat_features = artifact["cat_features"]

    X_num = df[num_features].copy()
    X_cat = pd.get_dummies(df[cat_features], drop_first=True)

    X = pd.concat([X_num, X_cat], axis=1)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

    expected_columns = get_expected_feature_columns()

    # Importante: aquí se rellenan también las columnas TDA h0/h1 que tu modelo espera.
    X = X.reindex(columns=expected_columns, fill_value=0)

    return df, X