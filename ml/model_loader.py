import joblib
from config import MODEL_PATH

artifact = joblib.load(MODEL_PATH)
model = artifact["iforest_model"]



def get_model():
    return model


def get_artifact():
    return artifact