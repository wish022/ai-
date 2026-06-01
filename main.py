import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 支持 IDE 直接运行 app/main.py（需在 import app 之前）
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.router import api_router
from app.config import settings
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.DEBUG:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")
        except Exception as e:
            logger.warning(f"Database init skipped: {e}")
    yield
    await engine.dispose()


app = FastAPI(
    title="小众旅游助手 API",
    description="对话式小众景点推荐后端",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

static_dir = Path(__file__).resolve().parent / "static"
NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate"}


def _html_page(name: str) -> FileResponse:
    return FileResponse(static_dir / name, media_type="text/html", headers=NO_CACHE)


if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/chat.html")


@app.get("/chat.html")
async def chat_page():
    return _html_page("chat.html")


@app.get("/spot.html")
async def spot_page():
    return _html_page("spot.html")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# 可选：本地 Ollama 测试接口（需安装 ollama 包且 Ollama 服务在运行）
if settings.LLM_PROVIDER == "ollama":
    try:
        import ollama

        @app.post("/api/ollama/chat")
        async def ollama_chat(prompt: str):
            try:
                response = ollama.chat(
                    model=settings.OLLAMA_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                )
                return {"reply": response["message"]["content"]}
            except Exception as e:
                return {"reply": f"Ollama 调用失败: {e}"}
    except ImportError:
        logger.warning("LLM_PROVIDER=ollama 但未安装 ollama 包，跳过 /api/ollama/chat")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(_backend_dir / "app")],
    )
