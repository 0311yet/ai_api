"""Web面板路由"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
# templates dir is at app/web/templates (one level up from this file's dir = app/router)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "web" / "templates"))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/channels", response_class=HTMLResponse)
async def channels_page(request: Request):
    return templates.TemplateResponse("channels.html", {"request": request})


@router.get("/keys", response_class=HTMLResponse)
async def keys_page(request: Request):
    return templates.TemplateResponse("keys.html", {"request": request})


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})


@router.get("/model-stats", response_class=HTMLResponse)
async def model_stats_page(request: Request):
    return templates.TemplateResponse("model_stats.html", {"request": request})