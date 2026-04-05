import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent


def get_expected_password() -> str | None:
    """Password from APP_PASSWORD in project `.env` or `src/.env`."""
    load_dotenv(_REPO_ROOT / ".env")
    load_dotenv(_REPO_ROOT / "src" / ".env", override=False)
    return os.getenv("APP_PASSWORD")
