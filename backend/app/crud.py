from datetime import date
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models import Project, Place
from app.schemas import ProjectCreate, ProjectUpdate, PlaceUpdate

async def recalculate_project_completeness(db: AsyncSession, project_id: int) -> bool:
    """
    Recalculates the completeness of a project.
    A project is marked completed if it has at least 1 place and all places are visited.
    """
    # Fetch all places for this project
    result = await db.execute(select(Place).filter(Place.project_id == project_id))
    places = result.scalars().all()

    is_completed = len(places) > 0 and all(p.is_visited for p in places)

    # Update project directly without fetching it to avoid relationship cascading issues
    await db.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(is_completed=is_completed)
    )
    await db.commit()
    
    return is_completed

# --- PROJECT CRUD ---

async def create_project(db: AsyncSession, project: ProjectCreate) -> Project:
    db_project = Project(
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        is_completed=False
    )
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    return db_project

async def create_project_with_places(
    db: AsyncSession, project: ProjectCreate, places_data: list[dict]
) -> Project:
    """
    Creates a project and associates imported places in a single transaction.
    """
    db_project = Project(
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        is_completed=False  # starts as false because newly imported places are unvisited
    )
    db.add(db_project)
    await db.flush()  # get db_project.id

    for place_info in places_data:
        db_place = Place(
            project_id=db_project.id,
            external_id=place_info["external_id"],
            title=place_info["title"],
            image_id=place_info.get("image_id"),
            notes=None,
            is_visited=False
        )
        db.add(db_place)

    await db.commit()
    await db.refresh(db_project)
    return db_project

async def get_projects(
    db: AsyncSession, skip: int = 0, limit: int = 100, is_completed: Optional[bool] = None
) -> list[Project]:
    query = select(Project)
    if is_completed is not None:
        query = query.filter(Project.is_completed == is_completed)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())

async def get_project(db: AsyncSession, project_id: int) -> Project | None:
    result = await db.execute(select(Project).filter(Project.id == project_id))
    return result.scalar_one_or_none()

async def update_project(db: AsyncSession, db_project: Project, project_update: ProjectUpdate) -> Project:
    update_data = project_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    return db_project

async def delete_project(db: AsyncSession, db_project: Project) -> None:
    """
    Deletes a project. Fails if any associated places are already visited.
    """
    # Check if any places are visited
    # db_project.places is loaded because of selectin loading
    has_visited = any(place.is_visited for place in db_project.places)
    if has_visited:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete project: one or more places in this project have already been marked as visited."
        )
    
    await db.delete(db_project)
    await db.commit()


# --- PLACE CRUD ---

async def add_place_to_project(
    db: AsyncSession, db_project: Project, external_id: str, title: str, image_id: str | None
) -> Place:
    """
    Adds a validated place to a project.
    Validates limits (max 10) and prevents duplicate external places in the same project.
    """
    # Enforce limit of maximum 10 places
    if len(db_project.places) >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add place: This project already contains the maximum limit of 10 places."
        )

    # Check for duplicates
    if any(place.external_id == external_id for place in db_project.places):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Place with external ID '{external_id}' is already added to this project."
        )

    db_place = Place(
        project_id=db_project.id,
        external_id=external_id,
        title=title,
        image_id=image_id,
        notes=None,
        is_visited=False
    )
    db.add(db_place)
    await db.commit()
    await db.refresh(db_place)

    # Recalculate completeness (will set is_completed=False because of the new unvisited place)
    await recalculate_project_completeness(db, db_project.id)
    return db_place

async def get_places_for_project(db: AsyncSession, project_id: int) -> list[Place]:
    result = await db.execute(select(Place).filter(Place.project_id == project_id))
    return list(result.scalars().all())

async def get_place_by_id(db: AsyncSession, project_id: int, place_id: int) -> Place | None:
    result = await db.execute(
        select(Place).filter(Place.project_id == project_id, Place.id == place_id)
    )
    return result.scalar_one_or_none()

async def update_place_in_project(
    db: AsyncSession, db_place: Place, place_update: PlaceUpdate
) -> Place:
    update_data = place_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_place, key, value)
    
    db.add(db_place)
    await db.commit()
    await db.refresh(db_place)

    # Recalculate completeness
    await recalculate_project_completeness(db, db_place.project_id)
    return db_place

async def delete_place_from_project(db: AsyncSession, db_place: Place) -> None:
    project_id = db_place.project_id
    
    # Load all places for this project to check count
    result = await db.execute(select(Place).filter(Place.project_id == project_id))
    places = list(result.scalars().all())

    if len(places) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last place from a project. A project must contain at least 1 place."
        )

    await db.delete(db_place)
    await db.commit()

    # Fetch project and refresh relationship to prevent stale cache in same session
    proj_result = await db.execute(select(Project).filter(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if project:
        await db.refresh(project, ["places"])

    # Recalculate completeness after deletion
    await recalculate_project_completeness(db, project_id)
