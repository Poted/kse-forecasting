import importlib

import pytest

from common.config import PROJECT_ROOT, load_settings, read_env_file


@pytest.mark.parametrize("name", ["common", "p2", "inz", "app", "common.config"])
def test_import_packages(name):
    importlib.import_module(name)


def test_settings_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "# komentarz\n\nDATABASE_URL='postgresql+psycopg://u:p@localhost:5432/db'\n",
        encoding="utf-8",
    )
    assert load_settings(env).database_url == "postgresql+psycopg://u:p@localhost:5432/db"


def test_environment_overrides_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgresql+psycopg://file/db\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env/db")
    assert load_settings(env).database_url == "postgresql+psycopg://env/db"


def test_missing_database_url_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        load_settings(tmp_path / "brak.env")


def test_read_env_file_missing_returns_empty(tmp_path):
    assert read_env_file(tmp_path / "brak.env") == {}


def test_env_example_has_database_url():
    assert "DATABASE_URL" in read_env_file(PROJECT_ROOT / ".env.example")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/neondb?sslmode=require",
            "postgresql+psycopg://u:p@ep-x.eu-central-1.aws.neon.tech/neondb?sslmode=require",
        ),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ],
)
def test_database_url_normalized_for_psycopg3(url, expected, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", url)
    assert load_settings(tmp_path / "brak.env").database_url == expected
