"""MTGJSON HTTP pull + local cache handling."""

from __future__ import annotations

import gzip
import shutil
import tempfile
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from loguru import logger

from settings import Settings


class MtgJsonFileClient:
    """Pull MTGJSON assets with local decompressed cache."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def ensure_cached_json(
        self,
        api_relative_path: str,
        *,
        check_freshness: bool = True,
        bust_cache: bool = False,
    ) -> tuple[Path, bool]:
        """Return cached JSON path and whether a network download occurred.

        ``check_freshness=True`` (SetList): reuse cache only if the file exists and is
        younger than ``mtgjson_cache_max_age_days``. ``check_freshness=False`` (per-set
        JSON): reuse whenever the decompressed ``.json`` file exists.

        ``bust_cache=True``: delete an existing cached ``.json`` file first so the next step
        is always a download (used for volatile sets such as ``SLD``).
        """
        cache_dir = self._resolve_cache_dir()
        rel = api_relative_path.lstrip("/")
        gz_name = Path(rel).name
        dest_json = cache_dir / gz_name.removesuffix(".gz")
        url = f"{self._settings.mtgjson_base_url}/{rel}"
        if bust_cache and dest_json.is_file():
            dest_json.unlink()
            logger.info("Removed cached {} to force re-download.", dest_json.name)
        if self._cache_hit(dest_json, check_freshness=check_freshness):
            return dest_json, False

        cache_dir.mkdir(parents=True, exist_ok=True)
        part = dest_json.with_name(dest_json.name + ".part")
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self._settings.mtgjson_fetch_user_agent,
                "Accept": "*/*",
            },
        )
        try:
            with tempfile.TemporaryDirectory() as td:
                gz_path = Path(td) / gz_name
                logger.info("Downloading {} ...", url)
                _download(request, gz_path)
                with gzip.open(gz_path, "rb") as gz_in, part.open("wb") as out:
                    shutil.copyfileobj(gz_in, out)
            part.replace(dest_json)
            time.sleep(self._settings.mtgjson_fetch_sleep_seconds)
            return dest_json, True
        except Exception:
            if part.is_file():
                part.unlink()
            raise

    def _resolve_cache_dir(self) -> Path:
        raw = Path(self._settings.mtgjson_cache_dir)
        if raw.is_absolute():
            return raw
        return Path.cwd().resolve() / raw

    def _cache_hit(self, path: Path, *, check_freshness: bool) -> bool:
        if not path.is_file():
            return False
        if not check_freshness:
            return True
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        max_age = timedelta(days=self._settings.mtgjson_cache_max_age_days)
        return datetime.now(UTC) - mtime < max_age


def _download(request: urllib.request.Request, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with part.open("wb") as out:
                shutil.copyfileobj(response, out)
        part.replace(dest)
    except Exception:
        if part.is_file():
            part.unlink()
        raise
