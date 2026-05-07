from backend.__version__ import PRD_VERSION, PRODUCT_NAME, __version__


def test_version_is_semver():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_product_name():
    assert PRODUCT_NAME == "FareSniper"


def test_prd_version():
    assert PRD_VERSION == "v2.0"
