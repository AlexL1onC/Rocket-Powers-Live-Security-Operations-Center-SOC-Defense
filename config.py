import os
from dotenv import load_dotenv

load_dotenv()

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'soc_anomaly_ensemble.joblib')
MAX_ALERTS_PER_CYCLE = int(os.getenv("MAX_ALERTS_PER_CYCLE", "5"))
ALERT_SCORE_THRESHOLD = float(os.getenv("ALERT_SCORE_THRESHOLD", "-0.05"))

ALERT_API_URL = os.getenv("ALERT_API_URL")
API_TOKEN = os.getenv("ALERT_API_TOKEN")
TEAM_NAME = os.getenv("TEAM_NAME", "team_alpha")