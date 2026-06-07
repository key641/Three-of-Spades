import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.feedback import router as feedback_router
from app.api.pois import router as pois_router
from app.api.routes import router as routes_router
from app.config import settings
from app.llm.provider import get_llm_client


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logging.getLogger("app").setLevel(logging.INFO)

app = FastAPI(title="Local Route Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(pois_router, prefix="/api")
app.include_router(routes_router, prefix="/api")
app.include_router(feedback_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/debug/llm-check")
async def llm_check() -> dict:
    """调试接口：检查 LLM 是否正常响应，返回耗时和模型回复。"""
    client = get_llm_client()
    t0 = time.time()
    try:
        result = await client.complete(
            messages=[{"role": "user", "content": "用中文回复：大模型运行正常"}],
            json_mode=False,
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        content = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        model = result.get("model", "unknown")
        return {
            "ok": True,
            "model": model,
            "reply": content,
            "elapsed_ms": elapsed_ms,
            "provider": settings.llm_provider,
        }
    except Exception as exc:
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "ok": False,
            "error": str(exc),
            "elapsed_ms": elapsed_ms,
            "provider": settings.llm_provider,
        }
