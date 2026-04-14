"""
Tests para los endpoints de gestion de circuito.

Grupo 1: POST /upload, GET /{circuit_id}, DELETE /{circuit_id}
"""
import io

import pytest


@pytest.mark.integration
def test_health_endpoint(client):
    """El endpoint /health debe retornar 200 con el campo status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "uptime_seconds" in data
    assert "components" in data


@pytest.mark.integration
def test_health_components_present(client):
    """El health check debe reportar el estado de redis, postgres y celery."""
    response = client.get("/api/v1/health")
    data = response.json()
    components = data.get("components", {})
    assert "redis" in components
    assert "postgres" in components
    assert "celery" in components


@pytest.mark.integration
def test_upload_invalid_extension(client):
    """Subir un archivo con extension incorrecta debe retornar 400."""
    content = b"New Circuit.Test"
    response = client.post(
        "/api/v1/circuit/upload",
        files={"main_dss": ("circuit.txt", io.BytesIO(content), "text/plain")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"] == "INVALID_FILE_EXTENSION"


@pytest.mark.integration
def test_get_nonexistent_circuit(client):
    """Consultar un circuit_id que no existe debe retornar 404."""
    response = client.get("/api/v1/circuit/ckt_nonexistent123")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"] == "CIRCUIT_NOT_FOUND"


@pytest.mark.integration
def test_delete_nonexistent_circuit(client):
    """DELETE de un circuit_id que no existe debe ser idempotente (204)."""
    response = client.delete("/api/v1/circuit/ckt_nonexistent999")
    # 204 No Content — la operacion es idempotente
    assert response.status_code == 204
