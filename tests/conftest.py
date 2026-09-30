import pytest

from app.config import get_settings

TEST_JWT_SECRET = "secreto-solo-para-tests-" + "x" * 40  # de 64


@pytest.fixture(autouse=True)
def settings_de_test(monkeypatch):
    """Cada test arranca con una configuración conocida y sin caché previa."""
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.delenv("JWT_ALGORITHM", raising=False)
    monkeypatch.delenv("JWT_EXPIRE_MINUTES", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
