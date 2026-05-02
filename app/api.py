from fastapi import APIRouter, HTTPException

from app.demo_cases import DEMO_CASES
from app.schemas import (
    HealthResponse,
    SourceImportRequest,
    SourceImportResponse,
    TravelPlanGenerateRequest,
    TravelPlanGenerateResponse,
)
from app.services.planner import TravelPlannerService
from app.services.source_importer import SourceImportError, SourceImporterService


router = APIRouter()
planner_service = TravelPlannerService()
source_importer_service = SourceImporterService()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version="0.1.0",
        mode="v0-prototype",
        message="高可靠旅行决策助手运行正常",
    )


@router.get("/demo-cases")
async def demo_cases():
    return {"cases": DEMO_CASES}


@router.post("/sources/import", response_model=SourceImportResponse)
async def import_source(
    request: SourceImportRequest,
) -> SourceImportResponse:
    try:
        return source_importer_service.import_manual_note(request)
    except SourceImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/plans/generate", response_model=TravelPlanGenerateResponse)
async def generate_plan(
    request: TravelPlanGenerateRequest,
) -> TravelPlanGenerateResponse:
    return planner_service.generate(request)
