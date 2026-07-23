"""应用入口"""
from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.routers import auth, providers, pools, keys, logs, stats, proxy, health, rates


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库 + 启动后台任务"""
    await init_db()
    # 启动 Provider Health 后台任务
    from app.services.provider_health import start_health_tasks
    await start_health_tasks()
    yield
    # shutdown
    from app.services.provider_health import stop_health_tasks
    await stop_health_tasks()


app = FastAPI(
    title="AI API Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS（开发阶段允许前端 Vite dev server 跨域；生产由同源挂载静态文件，不依赖 CORS）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(providers.router)
app.include_router(pools.router)
app.include_router(keys.router)
app.include_router(logs.router)
app.include_router(stats.router)
app.include_router(health.router)
app.include_router(rates.router)

app.include_router(proxy.router)


@app.get("/healthz")
async def health():
    return {"status": "ok", "service": "ai-api-gateway"}


# 生产环境：挂载前端静态文件（Vite 构建产物）
# 静态目录由环境变量 STATIC_DIR 指定，默认 /app/static
_static_dir = os.environ.get("STATIC_DIR", "/app/static")
if Path(_static_dir).is_dir():
    app.mount("/assets", StaticFiles(directory=Path(_static_dir) / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA 回退：非 API 路由统一返回 index.html"""
        # 排除 API 路由（它们优先匹配上面注册的 router）
        if full_path.startswith(("admin/", "v1/")):
            return {"detail": "Not Found"}
        index_file = Path(_static_dir) / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return {"detail": "Not Found"}
