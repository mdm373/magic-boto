"""MTGJSON HTTP pull + local cache handling."""

from __future__ import annotations

import gzip
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path

from loguru import logger

from settings import Settings


class MtgJsonFileClient:
    """Pull MTGJSON assets with local decompressed cache."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _dest_json_path(self, api_relative_path: str) -> Path:
        cache_dir = self._resolve_cache_dir()
        rel = api_relative_path.lstrip("/")
        gz_name = Path(rel).name
        return cache_dir / gz_name.removesuffix(".gz")

    def delete_cached_json(self, api_relative_path: str) -> None:
        """Remove the cached decompressed JSON for this asset if it exists."""
        dest_json = self._dest_json_path(api_relative_path)
        if dest_json.is_file():
            dest_json.unlink()
            logger.info("Removed cached {} to force re-download.", dest_json.name)

    def ensure_cached_json(
        self,
        api_relative_path: str,
        *,
        bust_cache: bool = False,
    ) -> tuple[Path, bool]:
        """Return cached JSON path and whether a network download occurred."""
        dest_json = self._dest_json_path(api_relative_path)
        url = f"{self._settings.mtgjson_base_url}/{api_relative_path.lstrip('/')}"
        if bust_cache and dest_json.is_file():
            dest_json.unlink()
            logger.info("Removed cached {} to force re-download.", dest_json.name)
        if dest_json.is_file():
            return dest_json, False

        cache_dir = self._resolve_cache_dir()
        rel = api_relative_path.lstrip("/")
        gz_name = Path(rel).name
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
