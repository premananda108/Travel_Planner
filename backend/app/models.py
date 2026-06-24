from datetime import date
from sqlalchemy import String, Boolean, Date, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship to places, with cascade delete on orphan records
    places: Mapped[list["Place"]] = relationship(
        "Place",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    image_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    is_visited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Back relationship to project
    project: Mapped["Project"] = relationship("Project", back_populates="places")

    # Enforce that the same external place cannot be added to the same project more than once
    __table_args__ = (
        UniqueConstraint("project_id", "external_id", name="uq_project_external_place"),
    )
