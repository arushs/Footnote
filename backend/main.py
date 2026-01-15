from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routes import auth, folders, chat
from app.services import embedding
from app.services import anthropic as anthropic_service
from app.services import mistral as mistral_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown - close SDK clients
    await embedding.close_client()
    await anthropic_service.close_client()
    await mistral_service.close_client()


app = FastAPI(
    title="Footnote API",
    description="RAG API for chatting with Google Drive folders",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(folders.router, prefix="/api/folders", tags=["folders"])
app.include_router(chat.router, prefix="/api", tags=["chat"])


@app.get("/api/health")
async def health():
    return {"status": "healthy"}
