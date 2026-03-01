"""Load repo-root .env so tasks have POSTGRES_* and other vars."""

from pathlib import Path

from dotenv import load_dotenv

_API_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _API_DIR.parent
_ENV_FILE = _REPO_ROOT / ".env"


def load_repo_env() -> bool:
    """Load .env from repo root; return True if file was found."""
    return bool(load_dotenv(_ENV_FILE))
