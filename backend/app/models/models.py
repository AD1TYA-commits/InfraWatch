"""
SQLAlchemy ORM models.

NOTE on geometry: the canonical schema (see app/db/schema.sql) defines
`geometry` as a real PostGIS `GEOMETRY(Point, 4326)` column with a GIST
index, for use against PostgreSQL+PostGIS in Docker/production.

The ORM layer below stores geometry as WKT text so the exact same model
code runs against SQLite (zero-dependency local dev) and Postgres alike.
Swapping DATABASE_URL to a Postgres+PostGIS DSN uses schema.sql for the
real GEOMETRY column; the ORM's `geometry_wkt` field is a portable
stand-in that works everywhere. latitude/longitude are always plain floats
per the spec, so nothing depends on PostGIS being present for the MVP to run.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, func
)
from sqlalchemy.orm import relationship

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    project_type = Column(String, nullable=False)
    description = Column(Text, default="")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    geometry_wkt = Column(Text, nullable=True)  # e.g. "POINT(lon lat)"
    start_date = Column(DateTime, nullable=True)
    expected_end_date = Column(DateTime, nullable=True)
    approved_cost = Column(Float, nullable=True)
    reported_progress = Column(Float, default=0.0)
    status = Column(String, default="normal")  # normal | watch | high | critical
    is_demo = Column(Integer, default=1)  # 1 = synthetic demo data, 0 = real

    milestones = relationship("Milestone", back_populates="project", cascade="all, delete-orphan")
    financial_records = relationship("FinancialRecord", back_populates="project", cascade="all, delete-orphan")
    progress_reports = relationship("ProgressReport", back_populates="project", cascade="all, delete-orphan")
    satellite_observations = relationship("SatelliteObservation", back_populates="project", cascade="all, delete-orphan")
    ai_results = relationship("AIResult", back_populates="project", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="project", cascade="all, delete-orphan")


class Milestone(Base):
    __tablename__ = "milestones"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    milestone_date = Column(DateTime, nullable=False)
    expected_progress = Column(Float, nullable=False)
    description = Column(Text, default="")

    project = relationship("Project", back_populates="milestones")


class FinancialRecord(Base):
    __tablename__ = "financial_records"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)

    project = relationship("Project", back_populates="financial_records")


class ProgressReport(Base):
    __tablename__ = "progress_reports"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    reported_progress = Column(Float, nullable=False)
    source = Column(String, default="")

    project = relationship("Project", back_populates="progress_reports")


class SatelliteObservation(Base):
    __tablename__ = "satellite_observations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    acquisition_date = Column(DateTime, nullable=False)
    source = Column(String, nullable=False)  # e.g. "demo", "sentinel-2-l2a"
    image_reference = Column(String, nullable=False)  # path or asset id, never raw raster in DB
    cloud_percentage = Column(Float, nullable=True)
    processing_status = Column(String, default="pending")

    project = relationship("Project", back_populates="satellite_observations")


class AIResult(Base):
    __tablename__ = "ai_results"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    observation_a = Column(Integer, ForeignKey("satellite_observations.id"), nullable=False)
    observation_b = Column(Integer, ForeignKey("satellite_observations.id"), nullable=False)
    changed_area = Column(Float, nullable=True)       # sq. meters (or px, documented per model_version)
    observed_progress = Column(Float, nullable=True)  # demo/heuristic estimate, clearly labeled in API
    confidence = Column(Float, nullable=True)
    model_version = Column(String, default="baseline-diff-v0")

    project = relationship("Project", back_populates="ai_results")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    type = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    severity = Column(String, nullable=False)  # normal | watch | high | critical
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="anomalies")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_action = Column(String, nullable=False)  # "<user>: <action>"
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    timestamp = Column(DateTime, server_default=func.now())
