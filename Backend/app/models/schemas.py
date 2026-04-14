"""
Modelos Pydantic para validacion de requests y serializacion de responses.
Representan el contrato publico de la API REST.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumeraciones
# ---------------------------------------------------------------------------


class ConnectionType(str, Enum):
    single_phase = "single_phase"
    two_phase = "two_phase"
    three_phase = "three_phase"


class TaskStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


# ---------------------------------------------------------------------------
# Circuito
# ---------------------------------------------------------------------------


class CircuitInfo(BaseModel):
    name: str
    num_buses: int
    num_elements: int
    converged: bool
    total_power_kw: float
    total_power_kvar: float


class UploadCircuitResponse(BaseModel):
    circuit_id: str
    circuit_info: CircuitInfo
    buses: List[str]
    buses_phases: Dict[str, List[int]]
    expires_at: str
    preprocessing_warnings: List[str] = []


class CircuitDetailResponse(BaseModel):
    circuit_id: str
    name: str
    num_buses: int
    num_elements: int
    converged: bool
    total_power_kw: float
    total_power_kvar: float
    buses_phases: Dict[str, List[int]]
    lines: List[Dict]
    expires_at: str


# ---------------------------------------------------------------------------
# Analisis de voltaje
# ---------------------------------------------------------------------------


class VoltagePoint(BaseModel):
    bus_phase: str
    voltage_pu: float
    in_range: bool


class VoltageProfileResponse(BaseModel):
    circuit_id: str
    state: str = "base"
    voltage_profile: List[VoltagePoint]
    limits: Dict[str, float] = {"lower": 0.95, "upper": 1.05}
    violations_count: int
    summary: Dict[str, float]


# ---------------------------------------------------------------------------
# Perdidas
# ---------------------------------------------------------------------------


class LossElement(BaseModel):
    type: str
    element: str
    losses_kw: float
    losses_kvar: float
    losses_pct: float


class LossesResponse(BaseModel):
    circuit_id: str
    state: str = "base"
    summary: Dict[str, float]
    elements: List[LossElement]


# ---------------------------------------------------------------------------
# Lineas
# ---------------------------------------------------------------------------


class LineInfo(BaseModel):
    name: str
    phases: int
    bus1: str
    bus2: str
    norm_amps: float
    emerg_amps: float
    kv_base: float
    s_nominal_kva: float
    current_base_amps: List[float]
    loading_pct_base: float


class LinesResponse(BaseModel):
    circuit_id: str
    lines: List[LineInfo]


# ---------------------------------------------------------------------------
# Simulacion con GD
# ---------------------------------------------------------------------------


class SimulateGDRequest(BaseModel):
    bus: str = Field(..., description="Nombre de la barra de conexion")
    phases: List[int] = Field(
        ..., min_length=1, max_length=3, description="Fases a utilizar (1, 2 o 3)"
    )
    connection_type: ConnectionType
    power_kw: float = Field(..., ge=0, le=150_000, description="Potencia activa en kW")
    power_kvar: float = Field(default=0.0, description="Potencia reactiva en kvar")

    @field_validator("phases")
    @classmethod
    def validate_phases(cls, v: List[int]) -> List[int]:
        if not all(p in [1, 2, 3] for p in v):
            raise ValueError("Las fases deben ser 1, 2 o 3")
        if len(v) != len(set(v)):
            raise ValueError("No se pueden repetir fases")
        return sorted(v)

    @model_validator(mode="after")
    def validate_connection_consistency(self) -> "SimulateGDRequest":
        expected = {
            ConnectionType.single_phase: 1,
            ConnectionType.two_phase: 2,
            ConnectionType.three_phase: 3,
        }
        n = len(self.phases)
        if n != expected[self.connection_type]:
            raise ValueError(
                f"connection_type '{self.connection_type}' requiere "
                f"{expected[self.connection_type]} fase(s) pero se "
                f"especificaron {n}"
            )
        return self


class VoltageComparison(BaseModel):
    bus_phase: str
    voltage_base_pu: float
    voltage_with_gd_pu: float
    delta_pu: float
    in_range_base: bool
    in_range_with_gd: bool


class SimulationViolations(BaseModel):
    voltage: List[Dict] = []
    current: List[Dict] = []
    power: List[Dict] = []


class SimulationSummary(BaseModel):
    has_violations: bool
    voltage_violations_count: int
    current_violations_count: int
    power_violations_count: int
    losses_change_pct: Optional[float] = None


class SimulateGDResponse(BaseModel):
    circuit_id: str
    simulation_id: str
    input: SimulateGDRequest
    converged: bool
    voltage_comparison: List[VoltageComparison]
    losses: Dict[str, float]
    violations: SimulationViolations
    summary: SimulationSummary


# ---------------------------------------------------------------------------
# Hosting Capacity
# ---------------------------------------------------------------------------


class HostingCapacityRequest(BaseModel):
    max_power_kw: float = Field(default=1_500_000, gt=0)
    check_voltage: bool = True
    check_current: bool = True
    check_power: bool = True
    buses: Optional[List[str]] = None


class HostingCapacityQueued(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.queued
    circuit_id: str
    total_combinations: int
    estimated_duration_seconds: int
    poll_url: str
    created_at: str


class HostingCapacityResult(BaseModel):
    bus: str
    phase: int
    max_gd_kw: Optional[float]
    limiting_constraint: Optional[str]


class HostingCapacityResponse(BaseModel):
    circuit_id: str
    calculated_at: str
    results: List[HostingCapacityResult]
    pivot: Dict[str, Dict[str, float]]
    summary: Dict[str, object]


class HostingCapacityBusResponse(BaseModel):
    circuit_id: str
    bus: str
    phases: List[Dict]


# ---------------------------------------------------------------------------
# Tareas asincronas
# ---------------------------------------------------------------------------


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress_pct: Optional[int] = None
    current_step: Optional[str] = None
    buses_completed: Optional[int] = None
    buses_total: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_seconds: Optional[int] = None
    estimated_remaining_seconds: Optional[int] = None
    result_url: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    partial_results_available: bool = False
    partial_results_url: Optional[str] = None
    position_in_queue: Optional[int] = None
    created_at: Optional[str] = None


class TaskCancelResponse(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.cancelled
    cancelled_at: str


# ---------------------------------------------------------------------------
# Error responses estandar
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: Optional[str] = None
    suggestion: Optional[str] = None
