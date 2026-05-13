from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")