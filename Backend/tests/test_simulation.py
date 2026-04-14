"""
Tests para los endpoints de simulacion con GD.

Grupo 3: POST /{circuit_id}/simulate
"""
import pytest


@pytest.mark.integration
def test_simulate_nonexistent_circuit(client):
    """Simular en un circuito que no existe debe retornar 404."""
    payload = {
        "bus": "634",
        "phases": [1, 2, 3],
        "connection_type": "three_phase",
        "power_kw": 500.0,
        "power_kvar": 0.0,
    }
    response = client.post(
        "/api/v1/circuit/ckt_nonexistent/simulate", json=payload
    )
    assert response.status_code == 404


@pytest.mark.unit
def test_simulate_request_validation_phase_mismatch():
    """connection_type inconsistente con el numero de fases debe ser rechazado."""
    from pydantic import ValidationError

    from app.models.schemas import SimulateGDRequest

    with pytest.raises(ValidationError) as exc_info:
        SimulateGDRequest(
            bus="634",
            phases=[1, 2],          # 2 fases
            connection_type="three_phase",  # pero pide 3
            power_kw=500.0,
        )
    assert "connection_type" in str(exc_info.value).lower() or "fase" in str(
        exc_info.value
    ).lower()


@pytest.mark.unit
def test_simulate_request_validation_invalid_phases():
    """Fases fuera del rango [1,2,3] deben ser rechazadas."""
    from pydantic import ValidationError

    from app.models.schemas import SimulateGDRequest

    with pytest.raises(ValidationError):
        SimulateGDRequest(
            bus="634",
            phases=[0, 4],  # invalidas
            connection_type="two_phase",
            power_kw=100.0,
        )


@pytest.mark.unit
def test_simulate_request_validation_duplicate_phases():
    """Fases duplicadas deben ser rechazadas."""
    from pydantic import ValidationError

    from app.models.schemas import SimulateGDRequest

    with pytest.raises(ValidationError):
        SimulateGDRequest(
            bus="634",
            phases=[1, 1, 2],
            connection_type="three_phase",
            power_kw=100.0,
        )
