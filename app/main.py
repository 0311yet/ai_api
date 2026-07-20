"""FastAPI 主程序"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import init_db
from app.config import HOST, PORT, ALLOWED_ORIGINS
from app.router import proxy, admin, stats, web


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init database
    await init_db()
    print("[OK] Database initialized")
    yield
    # Shutdown


app = FastAPI(title="AI API Gateway", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(proxy.router)        # 转发
app.include_router(admin.router)        # 管理
app.include_router(stats.router)        # 统计
app.include_router(web.router)          # Web面板


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
