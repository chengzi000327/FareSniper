from fastapi.testclient import TestClient

from backend.__version__ import PRD_VERSION, PRODUCT_NAME, __version__
from backend.main import app


def test_app_title_and_version():
    assert app.title == PRODUCT_NAME
    assert app.version == __version__


def test_openapi_includes_prd_version():
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    assert schema["info"]["x-prd-version"] == PRD_VERSION
    assert schema["info"]["title"] == PRODUCT_NAME
    assert schema["info"]["version"] == __version__
