"""Ustawienia aplikacji odczytywane z pliku `.env` i zmiennych środowiskowych.

Zmienne środowiskowe mają pierwszeństwo przed wartościami z pliku `.env`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


def read_env_file(path: Path) -> dict[str, str]:
    """Wczytuje plik w formacie KEY=VALUE. Pomija puste linie i komentarze."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


@dataclass(frozen=True)
class Settings:
    database_url: str


def load_settings(env_file: Path | None = None) -> Settings:
    """Zwraca ustawienia. Brak `DATABASE_URL` → błąd z jasnym komunikatem."""
    file_values = read_env_file(env_file or DEFAULT_ENV_FILE)
    database_url = os.environ.get("DATABASE_URL") or file_values.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Brak DATABASE_URL. Skopiuj .env.example do .env i uzupełnij wartości.")
    return Settings(database_url=normalize_database_url(database_url))


def normalize_database_url(url: str) -> str:
    """`postgresql://` / `postgres://` (format np. Neon) → sterownik psycopg 3 używany w projekcie.

    SQLAlchemy dla `postgresql://` wybiera domyślnie psycopg2, którego projekt nie instaluje.
    Parametry (np. `?sslmode=require`) zostają bez zmian.
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url
