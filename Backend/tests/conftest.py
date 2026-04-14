"""
Configuracion de pytest y fixtures compartidas.

Los tests de integracion requieren que Redis y PostgreSQL esten corriendo.
Los tests unitarios del motor DSS requieren opendssdirect instalado.

Ejecutar todos los tests:
    pytest tests/

Solo tests unitarios (sin dependencias externas):
    pytest tests/ -m unit

Solo tests de integracion:
    pytest tests/ -m integration
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """Cliente HTTP para tests de la API FastAPI."""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_dss_content():
    """
    Contenido DSS minimo para tests unitarios del motor.
    Circuito de un solo bus con una carga simple.
    """
    return """
Clear
New Circuit.TestCircuit Bus1=SourceBus BasekV=4.16 pu=1.0 Phases=3
New Load.Load1 Bus1=SourceBus Phases=3 kV=4.16 kW=100 kvar=50
Set VoltageBases=[4.16]
CalcVoltageBases
Solve
"""


@pytest.fixture
def ieee13_dss_path():
    """
    Ruta al archivo IEEE 13 Nodos del repositorio (si existe).
    Los tests que lo usan se saltean si no esta presente.
    """
    import os

    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "Referencia",
        "OpenDSS",
        "IEEETestCases",
        "13Bus",
        "IEEE13Nodeckt.dss",
    )
    return os.path.abspath(path)
