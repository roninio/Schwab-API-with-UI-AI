import os
import shutil
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
import schwabdev


def _schwab_tokens_db_path() -> Path:
    """SQLite path for schwabdev OAuth tokens (NiceGUI-era default under .nicegui/)."""
    root = Path.cwd()
    nicegui_dir = root / ".nicegui"
    nicegui_dir.mkdir(parents=True, exist_ok=True)
    path = nicegui_dir / "schwab_tokens.db"
    legacy = root / ".streamlit" / "schwab_tokens.db"
    if not path.exists() and legacy.exists():
        shutil.copy2(legacy, path)
    return path


def create_client(timeout: int = 9) -> schwabdev.Client:
    """Build a new Schwab client (own HTTP session). Use for parallel API calls."""
    load_dotenv()
    app_key = os.getenv("APP_KEY")
    app_secret = os.getenv("APP_SECRET")
    if not app_key or not app_secret:
        raise RuntimeError("APP_KEY or APP_SECRET is missing from environment.")

    tokens_db = str(_schwab_tokens_db_path())
    client = schwabdev.Client(
        app_key,
        app_secret,
        timeout=timeout,
        tokens_db=tokens_db,
    )
    client.update_tokens()
    return client


@lru_cache(maxsize=1)
def get_client(timeout: int = 9) -> schwabdev.Client:
    return create_client(timeout)
