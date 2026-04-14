"""
Modelos SQLAlchemy para persistencia en PostgreSQL.

Los resultados del calculo de Hosting Capacity se guardan aqui para no
recalcular en cada request. Las simulaciones puntuales tambien se registran
para poder exportarlas despues.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class CircuitRecord(Base):
    """Metadatos de un circuito que fue subido y compilado."""

    __tablename__ = "circuits"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    num_buses = Column(Integer)
    num_elements = Column(Integer)
    total_power_kw = Column(Float)
    total_power_kvar = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    hosting_results = relationship(
        "HostingCapacityResult", back_populates="circuit", cascade="all, delete"
    )
    simulations = relationship(
        "SimulationRecord", back_populates="circuit", cascade="all, delete"
    )


class HostingCapacityResult(Base):
    """
    Un resultado de hosting capacity por (circuito, barra, fase).
    Asociado a la tarea Celery que lo genero.
    """

    __tablename__ = "hosting_capacity_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    circuit_id = Column(String, ForeignKey("circuits.id"), nullable=False)
    task_id = Column(String, nullable=False)
    bus = Column(String, nullable=False)
    phase = Column(Integer, nullable=False)
    max_gd_kw = Column(Float)
    limiting_constraint = Column(String)
    calculated_at = Column(DateTime, default=datetime.utcnow)

    circuit = relationship("CircuitRecord", back_populates="hosting_results")


class SimulationRecord(Base):
    """
    Registro de una simulacion puntual (POST /simulate).
    Permite exportar resultados despues sin recalcular.
    """

    __tablename__ = "simulations"

    id = Column(String, primary_key=True)
    circuit_id = Column(String, ForeignKey("circuits.id"), nullable=False)
    bus = Column(String, nullable=False)
    phases = Column(JSON, nullable=False)
    connection_type = Column(String, nullable=False)
    power_kw = Column(Float, nullable=False)
    power_kvar = Column(Float, default=0.0)
    converged = Column(Boolean, default=True)
    losses_base_kw = Column(Float)
    losses_with_gd_kw = Column(Float)
    has_violations = Column(Boolean, default=False)
    violations = Column(JSON)
    voltage_comparison = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    circuit = relationship("CircuitRecord", back_populates="simulations")
