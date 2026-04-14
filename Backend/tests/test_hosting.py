"""
Tests para los endpoints de Hosting Capacity.

Grupo 4: POST/GET /{circuit_id}/hosting-capacity
"""
import pytest


@pytest.mark.integration
def test_get_hosting_capacity_without_calculation(client):
    """GET hosting-capacity sin calculo previo debe retornar 404."""
    # Primero verificamos que el circuit_id no existe
    response = client.get("/api/v1/circuit/ckt_nocalc/hosting-capacity")
    # 404 porque el circuito no existe (se valida primero)
    assert response.status_code == 404


@pytest.mark.integration
def test_post_hosting_capacity_nonexistent_circuit(client):
    """POST hosting-capacity en circuito inexistente debe retornar 404."""
    payload = {
        "max_power_kw": 1500000,
        "check_voltage": True,
        "check_current": True,
        "check_power": True,
    }
    response = client.post(
        "/api/v1/circuit/ckt_nonexistent/hosting-capacity", json=payload
    )
    assert response.status_code == 404


@pytest.mark.unit
def test_hosting_capacity_request_defaults():
    """Los valores default del request de hosting capacity son correctos."""
    from app.models.schemas import HostingCapacityRequest

    req = HostingCapacityRequest()
    assert req.max_power_kw == 1_500_000
    assert req.check_voltage is True
    assert req.check_current is True
    assert req.check_power is True
    assert req.buses is None


@pytest.mark.unit
def test_hosting_capacity_request_invalid_max_power():
    """max_power_kw <= 0 debe ser rechazado."""
    from pydantic import ValidationError

    from app.models.schemas import HostingCapacityRequest

    with pytest.raises(ValidationError):
        HostingCapacityRequest(max_power_kw=0)

    with pytest.raises(ValidationError):
        HostingCapacityRequest(max_power_kw=-100)
