from datetime import date
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional

# --- PLACE SCHEMAS ---

class PlaceBase(BaseModel):
    notes: Optional[str] = Field(None, max_length=1000, description="Notes about the place")
    is_visited: bool = Field(False, description="Whether the traveller has visited the place")

class PlaceCreate(BaseModel):
    external_id: str = Field(..., min_length=1, description="External artwork ID from the Art Institute of Chicago")

class PlaceUpdate(BaseModel):
    notes: Optional[str] = Field(None, max_length=1000, description="Updated notes")
    is_visited: Optional[bool] = Field(None, description="Updated visited status")

class PlaceOut(PlaceBase):
    id: int
    project_id: int
    external_id: str
    title: str
    image_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- PROJECT SCHEMAS ---

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the travel project")
    description: Optional[str] = Field(None, max_length=2000, description="Optional description of the project")
    start_date: Optional[date] = Field(None, description="Optional start date of the project")

class ProjectCreate(ProjectBase):
    pass

class ProjectCreateWithPlaces(ProjectBase):
    places: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,  # Max 10 items will be enforced via validator/business logic.
        description="List of external place IDs to import. Must contain 1 to 10 unique items."
    )

    @field_validator("places")
    @classmethod
    def validate_places_limit_and_uniqueness(cls, v: List[str]) -> List[str]:
        if not (1 <= len(v) <= 10):
            raise ValueError("A project must contain between 1 and 10 places.")
        
        # Check for duplicates in the list
        if len(v) != len(set(v)):
            raise ValueError("Duplicate external place IDs in request are not allowed.")
        return v

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    start_date: Optional[date] = Field(None)

class ProjectOut(ProjectBase):
    id: int
    is_completed: bool
    places: List[PlaceOut] = []

    model_config = ConfigDict(from_attributes=True)
