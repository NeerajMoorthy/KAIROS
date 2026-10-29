"""Pydantic request/response models for the KAIROS REST API."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# --------------------------------------------------------------------- #
# tasks
# --------------------------------------------------------------------- #
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    # `topic` and `notes` remain accepted for older clients. New clients can
    # use the more general category and description fields.
    topic: str = Field("", max_length=120)
    category: Optional[str] = Field(None, max_length=120)
    project: Optional[str] = Field(None, max_length=160)
    description: str = Field("", max_length=4000)
    deadline: date
    priority: Priority = Priority.MEDIUM
    estimated_hours: float = Field(2.0, gt=0, le=1000)
    notes: Optional[str] = Field(None, max_length=4000)

    @field_validator("title")
    @classmethod
    def title_must_contain_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title cannot be blank.")
        return value.strip()


class TaskUpdate(BaseModel):
    completed: Optional[bool] = None
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    topic: Optional[str] = Field(None, max_length=120)
    category: Optional[str] = Field(None, max_length=120)
    project: Optional[str] = Field(None, max_length=160)
    description: Optional[str] = Field(None, max_length=4000)
    notes: Optional[str] = Field(None, max_length=4000)
    deadline: Optional[date] = None
    priority: Optional[Priority] = None
    estimated_hours: Optional[float] = Field(None, gt=0, le=1000)
    progress: Optional[float] = Field(None, ge=0, le=100)
    status: Optional[TaskStatus] = None
    actual_hours: Optional[float] = Field(None, ge=0, le=100000)

    @field_validator("title")
    @classmethod
    def updated_title_must_contain_text(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("Title cannot be blank.")
        return value.strip() if value is not None else None


class ScoreBreakdown(BaseModel):
    priority_component: float
    deadline_component: float
    workload_component: float
    overdue_penalty: float
    days_to_deadline: int
    formula: str


class Task(BaseModel):
    id: str
    title: str
    topic: str
    category: Optional[str] = None
    project: Optional[str] = None
    description: str = ""
    deadline: date
    priority: Priority
    estimated_hours: float
    notes: str = ""
    urgency_score: float
    score_breakdown: ScoreBreakdown
    created_at: str
    updated_at: str
    progress: float = 0
    status: TaskStatus = TaskStatus.TODO
    actual_hours: float = 0
    remaining_hours: float = 0
    completed: bool = False


# --------------------------------------------------------------------- #
# resources
# --------------------------------------------------------------------- #
class Resource(BaseModel):
    id: str
    title: str
    source: str
    kind: str
    location: str
    tags: List[str] = []
    keywords: List[str] = []
    content_keywords: List[str] = []
    size_bytes: Optional[int] = None
    modified: Optional[str] = None
    snippet: str = ""


class RankedResource(BaseModel):
    resource: Resource
    score: float
    reasons: List[str] = []


class IndexFolderRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=1024)
    tags: List[str] = Field(default_factory=list, max_length=20)
    recursive: bool = True
    read_contents: bool = True


class FolderRescanRequest(BaseModel):
    """Rescan one registered folder, or every folder when path is omitted."""
    path: Optional[str] = Field(None, min_length=1, max_length=1024)


# --------------------------------------------------------------------- #
# scheduling
# --------------------------------------------------------------------- #
class ScheduleRequest(BaseModel):
    capacity_hours: float = Field(20.0, ge=0, le=500)
    algorithm: str = Field("branch_and_bound")
    daily_hours: float = Field(3.0, ge=0, le=16)
    include_revision: bool = True


class AdaptivePlanRequest(BaseModel):
    capacity_hours: float = Field(21.0, ge=0, le=500)
    daily_hours: float = Field(3.0, ge=0, le=16)
    horizon_days: int = Field(7, ge=1, le=14)


class FocusSessionStart(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=32)
    objective: str = Field("", max_length=500)


class FocusSessionUpdate(BaseModel):
    action: Literal["pause", "resume", "complete"]
    progress: Optional[float] = Field(None, ge=0, le=100)


class SettingsUpdate(BaseModel):
    available_hours_per_day: Optional[float] = Field(None, ge=0, le=16)

    @field_validator("available_hours_per_day")
    @classmethod
    def availability_must_be_numeric(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            raise ValueError("Daily availability must be a number between 0 and 16.")
        return value


# --------------------------------------------------------------------- #
# self-rated concept confidence (compatibility endpoints)
# --------------------------------------------------------------------- #
class MasteryUpdate(BaseModel):
    concept: str = Field(..., min_length=1)
    mastery: int = Field(..., ge=0, le=100)


class Credentials(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)
