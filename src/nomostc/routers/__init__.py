from fastapi import APIRouter

from .ingest import router as ingest_router

api_router = APIRouter(prefix="/api")
api_router.include_router(ingest_router)
