from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from pymongo.errors import PyMongoError

from nomostc.routers import api_router
from nomostc.exceptions import EdifactParsingError
from nomostc.db import get_db, close_db
from nomostc.repository import log_request

logger = logging.getLogger("nomostc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()
    logger.info("MongoDB connection pool ready")
    yield
    close_db()
    logger.info("MongoDB connection pool closed")


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)

logging.basicConfig(level="DEBUG")


@app.exception_handler(EdifactParsingError)
async def edifact_parsing_error_handler(request: Request, exc: EdifactParsingError):
    logger.error("EDIFACT parsing error", extra={"error": str(exc)})
    return JSONResponse(
        status_code=400,
        content={"detail": f"EDIFACT parsing error: {str(exc)}"},
    )


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError):
    logger.warning("File not found", extra={"path": str(exc)})
    return JSONResponse(
        status_code=404,
        content={"detail": f"File not found: {str(exc)}"},
    )


@app.exception_handler(PyMongoError)
async def database_error_handler(request: Request, exc: PyMongoError):
    logger.exception("Database error")
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable"},
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    try:
        log_request(
            get_db(),
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
    except Exception as e:
        logger.warning("Failed to persist request: %s", e)
    return response


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")
