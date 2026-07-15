import pytest
from pydantic import ValidationError

from trialsync.config import Settings


def test_database_url_is_required() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_database_url_rejects_non_postgresql_scheme() -> None:
    with pytest.raises(ValidationError, match="must use PostgreSQL"):
        Settings(_env_file=None, DATABASE_URL="sqlite:///test.db")


def test_secret_database_url_is_not_exposed_in_repr() -> None:
    password = "a-sensitive-test-password"
    settings = Settings(
        _env_file=None,
        DATABASE_URL=f"postgresql+psycopg://user:{password}@localhost/test",
    )

    assert password not in repr(settings)
