from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import date

from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import Base, engine, get_db
from app.auth import get_current_user
import app.schemas as schemas
import app.crud as crud
import app.services as services

# Database tables lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup: Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Teardown: (Optional cleanups here)

from fastapi.responses import RedirectResponse

app = FastAPI(
    title="Travel Planner API",
    description="A CRUD API to help travellers plan trips, manage projects, import places from the Art Institute of Chicago, and attach notes.",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")

# Protect all routes under this router with Basic Authentication
api_router = APIRouter(
    prefix="/api",
    dependencies=[Depends(get_current_user)]
)

# --- PROJECTS ENDPOINTS ---

@api_router.post("/projects", response_model=schemas.ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: schemas.ProjectCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a travel project.
    Optionally imports an array of places from the Art Institute of Chicago API in the same request.
    """
    if project_data.places:
        places_to_import = []
        for ext_id in project_data.places:
            # Validate place exists in external API (utilizes caching internally)
            artwork_details = await services.fetch_artwork_from_api(ext_id)
            places_to_import.append(artwork_details)

        # Delegate to CRUD to create project and bulk-insert places
        return await crud.create_project_with_places(
            db=db,
            project=project_data,
            places_data=places_to_import
        )
    
    # Create empty project
    return await crud.create_project(db, project_data)


@api_router.get("/projects", response_model=List[schemas.ProjectOut])
async def list_projects(
    skip: int = Query(0, ge=0, description="Number of projects to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max number of projects to return"),
    is_completed: Optional[bool] = Query(None, description="Filter projects by completed status"),
    db: AsyncSession = Depends(get_db)
):
    """List travel projects with optional filtering (is_completed) and pagination."""
    return await crud.get_projects(db, skip=skip, limit=limit, is_completed=is_completed)


@api_router.get("/projects/{project_id}", response_model=schemas.ProjectOut)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a single travel project by its ID."""
    db_project = await crud.get_project(db, project_id)
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found."
        )
    return db_project


@api_router.put("/projects/{project_id}", response_model=schemas.ProjectOut)
async def update_project(
    project_id: int,
    project_update: schemas.ProjectUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update general travel project information (Name, Description, Start Date)."""
    db_project = await crud.get_project(db, project_id)
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found."
        )
    return await crud.update_project(db, db_project, project_update)


@api_router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a travel project from the system.
    A project cannot be deleted if any of its places are already marked as visited.
    """
    db_project = await crud.get_project(db, project_id)
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found."
        )
    await crud.delete_project(db, db_project)
    return None


# --- PLACES ENDPOINTS ---

@api_router.post("/projects/{project_id}/places", response_model=schemas.PlaceOut, status_code=status.HTTP_201_CREATED)
async def add_place_to_project(
    project_id: int,
    place_in: schemas.PlaceCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Add a place to an existing project.
    Validates that the place exists in the Art Institute API.
    Enforces maximum limit of 10 places per project and unique external places.
    """
    # 1. Verify project exists
    db_project = await crud.get_project(db, project_id)
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found."
        )

    # 2. Enforce pre-validation to avoid API check if database limits are already breached
    if len(db_project.places) >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add place: This project already contains the maximum limit of 10 places."
        )
    if any(p.external_id == place_in.external_id for p in db_project.places):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Place with external ID '{place_in.external_id}' is already added to this project."
        )

    # 3. Call services to validate place in Art Institute API
    artwork_details = await services.fetch_artwork_from_api(place_in.external_id)

    # 4. Insert into database
    return await crud.add_place_to_project(
        db=db,
        db_project=db_project,
        external_id=artwork_details["external_id"],
        title=artwork_details["title"],
        image_id=artwork_details["image_id"]
    )


@api_router.get("/projects/{project_id}/places", response_model=List[schemas.PlaceOut])
async def list_places_for_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    """List all places associated with a project."""
    # Verify project exists first
    db_project = await crud.get_project(db, project_id)
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found."
        )
    return await crud.get_places_for_project(db, project_id)


@api_router.get("/projects/{project_id}/places/{place_id}", response_model=schemas.PlaceOut)
async def get_place_within_project(
    project_id: int,
    place_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get details of a single place within a project."""
    db_place = await crud.get_place_by_id(db, project_id, place_id)
    if not db_place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Place with ID {place_id} does not exist in Project {project_id}."
        )
    return db_place


@api_router.patch("/projects/{project_id}/places/{place_id}", response_model=schemas.PlaceOut)
async def update_place_within_project(
    project_id: int,
    place_id: int,
    place_update: schemas.PlaceUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update notes or visited status of a place within a project.
    If all places are marked as visited, the project will automatically mark as completed.
    """
    db_place = await crud.get_place_by_id(db, project_id, place_id)
    if not db_place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Place with ID {place_id} does not exist in Project {project_id}."
        )
    return await crud.update_place_in_project(db, db_place, place_update)


@api_router.delete("/projects/{project_id}/places/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_place_from_project(
    project_id: int,
    place_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Remove a place from a project. Completeness state will be automatically re-evaluated."""
    db_project = await crud.get_project(db, project_id)
    if not db_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found."
        )
    
    # Refresh relationship to sync with the database and avoid cached session states
    await db.refresh(db_project, ["places"])
        
    db_place = next((p for p in db_project.places if p.id == place_id), None)
    if not db_place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Place with ID {place_id} does not exist in Project {project_id}."
        )

    await crud.delete_place_from_project(db, db_place)
    return None


# Include all protected endpoints under `/api`
app.include_router(api_router)

# Public health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy", "service": "Travel Planner API"}
