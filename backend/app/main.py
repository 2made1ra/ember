from __future__ import annotations

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .agent import run_argus_turn
from .auth import require_user
from .config import get_settings
from .errors import DependencyUnavailableError
from .ingest import ingest_catalog
from .lm_studio import LMStudioClient
from .search import PriceSearcher
from .semantic_agent import run_semantic_search_agent
from .state import get_brief_state, get_catalog_status, reset_brief_state, set_catalog_status


app = FastAPI(title="ARGUS Brief Agent MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DependencyUnavailableError)
async def dependency_unavailable_handler(
    request: Request,
    exc: DependencyUnavailableError,
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    mode: str = "brief"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=3, ge=1, le=10)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/catalog/status")
def catalog_status(_user: dict = Depends(require_user)) -> dict:
    return get_catalog_status().to_dict()


@app.post("/api/catalog/upload")
async def upload_catalog(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    _user: dict = Depends(require_user),
) -> dict:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty")

    settings = get_settings()
    set_catalog_status(
        ready=False,
        stage="queued",
        message=f"Файл {file.filename} принят в обработку",
        row_count=0,
        embedded_count=0,
        vector_size=None,
        error=None,
    )
    background_tasks.add_task(ingest_catalog, content, settings)
    return get_catalog_status().to_dict()


@app.post("/api/chat")
def chat(request: ChatRequest, _user: dict = Depends(require_user)) -> dict:
    if not get_catalog_status().ready:
        raise HTTPException(status_code=409, detail="Catalog is not loaded")

    settings = get_settings()
    searcher = PriceSearcher(settings)
    chat_client = LMStudioClient(settings)
    return run_argus_turn(
        state=get_brief_state(),
        message=request.message,
        searcher=searcher,
        chat_client=chat_client,
        ui_mode=request.mode,
    )


@app.post("/api/chat/reset")
def reset_chat(_user: dict = Depends(require_user)) -> dict:
    return reset_brief_state().to_dict()


@app.post("/api/search")
def semantic_search(request: SearchRequest, _user: dict = Depends(require_user)) -> dict:
    if not get_catalog_status().ready:
        raise HTTPException(status_code=409, detail="Catalog is not loaded")

    settings = get_settings()
    searcher = PriceSearcher(settings)
    result = run_semantic_search_agent(request.query, searcher=searcher, limit=request.limit)
    return {"query": request.query, **result}
