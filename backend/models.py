"""
AEGIS ORM Models — All database entities.
"""
from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime, Text, JSON, ForeignKey
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


class Zone(Base):
    """Spatial zone for localized environmental monitoring."""
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    geojson_boundary = Column(JSON, nullable=True)
    population = Column(Integer, nullable=True)
    area_km2 = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    observations = relationship("ZoneObservation", back_populates="zone", cascade="all, delete-orphan")
    assessments = relationship("RiskAssessment", back_populates="zone", cascade="all, delete-orphan")


class ZoneObservation(Base):
    """Time-series environmental observation data mapped to a specific zone."""
    __tablename__ = "zone_observations"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False, index=True)
    pm25 = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    rainfall = Column(Float, nullable=True)
    heat_index = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    zone = relationship("Zone", back_populates="observations")


class EnvironmentalReading(Base):
    """Time-series environmental observation data."""
    __tablename__ = "environmental_readings"

    id = Column(Integer, primary_key=True, index=True)
    pm25 = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    heat_index = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class BaselineRecord(Base):
    """Rolling historical baselines per hour-of-day."""
    __tablename__ = "baseline_records"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True, index=True)
    hour_of_day = Column(Integer, nullable=False, index=True)
    metric = Column(String(50), nullable=False)  # 'pm25' or 'heat_index'
    mean = Column(Float, nullable=False)
    std_dev = Column(Float, nullable=False)
    percentile_bands = Column(JSON, nullable=True)  # {25: val, 50: val, ...}
    sample_count = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RiskAssessment(Base):
    """Computed risk scores per assessment cycle."""
    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True, index=True)
    air_score = Column(Float, nullable=False)
    air_confidence = Column(Float, nullable=False)
    heat_score = Column(Float, nullable=False)
    heat_confidence = Column(Float, nullable=False)
    composite_score = Column(Float, nullable=False)
    composite_confidence = Column(Float, nullable=False)
    air_trend = Column(String(10), default="stable")  # up, down, stable
    heat_trend = Column(String(10), default="stable")
    composite_trend = Column(String(10), default="stable")
    anomaly_flags = Column(JSON, nullable=True)
    anomaly_description = Column(Text, nullable=True)
    pm25_value = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    heat_index = Column(Float, nullable=True)
    pm25_zscore = Column(Float, nullable=True)
    heat_zscore = Column(Float, nullable=True)
    smoke_score = Column(Float, nullable=True)
    smoke_confidence = Column(Float, nullable=True)
    hotspot_count = Column(Integer, nullable=True)
    flood_score = Column(Float, nullable=True)
    flood_alert_level = Column(String(50), nullable=True)
    vector_risk = Column(Float, nullable=True)
    vector_risk_level = Column(String(50), nullable=True)
    water_contamination_risk = Column(Float, nullable=True)
    water_contamination_risk_level = Column(String(50), nullable=True)
    pm25_baseline_mean = Column(Float, nullable=True)
    heat_baseline_mean = Column(Float, nullable=True)
    pm25_percentile = Column(Float, nullable=True)
    heat_percentile = Column(Float, nullable=True)
    amplification_factor = Column(Float, nullable=True)
    intelligence_summary = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    zone = relationship("Zone", back_populates="assessments")


class Alert(Base):
    """Environmental alerts with severity classification."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    severity = Column(String(20), nullable=False)  # Normal, Moderate, High
    alert_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    risk_score = Column(Float, nullable=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class Advisory(Base):
    """Public advisories requiring government approval."""
    __tablename__ = "advisories"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)
    approved = Column(Boolean, default=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    published = Column(Boolean, default=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GovernmentUser(Base):
    """Authenticated government operators."""
    __tablename__ = "government_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IntelligenceFeedEntry(Base):
    """Chronological autonomous intelligence reports."""
    __tablename__ = "intelligence_feed"

    id = Column(Integer, primary_key=True, index=True)
    entry_type = Column(String(50), nullable=False)  # observation, risk_update, alert, anomaly
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    severity = Column(String(20), default="info")
    metadata_json = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
