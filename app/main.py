import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.database import init_db
from app.api.router import api_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("codemind.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing CodeMind database...")
    init_db()
    logger.info("CodeMind Backend startup complete.")
    yield
    logger.info("CodeMind Backend shutting down.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS configuration
raw_origins = [o.strip() for o in settings.FRONTEND_URL.split(",") if o.strip()]
origins = list(dict.fromkeys(raw_origins + [settings.frontend_url_clean, "https://codemind-1218.vercel.app", "http://localhost:3000", "http://127.0.0.1:3000"]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/health")
@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "config": {
            "github_configured": bool(settings.github_client_id_clean and settings.github_client_secret_clean),
            "google_configured": bool(settings.google_client_id_clean and settings.google_client_secret_clean),
            "hindsight_configured": bool(settings.HINDSIGHT_API_KEY.strip()),
            "groq_configured": bool(settings.GROQ_API_KEY.strip())
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
