"""Serialize :class:`~app.services.batch_client.Request` lists to/from ``batches.payload`` JSON."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.message_schema import schema_path_from_payload_value

from .batch_client import Request

_OUTBOX_VERSION = 1


class BatchSerializationService:
    """Serialize and deserialize Anthropic batch request lists stored on ``batches.payload``."""

    def serialize_requests(self, requests: Sequence[Request]) -> str:
        """Build UTF-8 JSON for ``batches.payload``."""
        body: dict[str, Any] = {
            "v": _OUTBOX_VERSION,
            "requests": [self._request_to_jsonable(r) for r in requests],
        }
        return json.dumps(body, ensure_ascii=False)

    def deserialize_requests(self, payload: str) -> list[Request]:
        """Parse ``batches.payload`` JSON into :class:`Request` instances."""
        data = json.loads(payload)
        if not isinstance(data, dict):
            msg = "outbox payload must be a JSON object"
            raise ValueError(msg)
        if data.get("v") != _OUTBOX_VERSION:
            msg = f"unsupported outbox payload version: {data.get('v')!r}"
            raise ValueError(msg)
        raw_reqs = data.get("requests")
        if not isinstance(raw_reqs, list) or not raw_reqs:
            msg = "outbox payload requests must be a non-empty list"
            raise ValueError(msg)
        return [self._request_from_jsonable(x) for x in raw_reqs]

    @staticmethod
    def _request_to_jsonable(r: Request) -> dict[str, Any]:
        return {
            "custom_id": r.custom_id,
            "messages": list(r.messages),
            "model": r.model,
            "max_tokens": r.max_tokens,
            "system_prompt": r.system_prompt,
            "output_schema_path": r.output_schema_path.name if r.output_schema_path else None,
        }

    @staticmethod
    def _request_from_jsonable(d: object) -> Request:
        if not isinstance(d, dict):
            msg = "each request must be a JSON object"
            raise ValueError(msg)
        custom_id = d.get("custom_id")
        messages = d.get("messages")
        model = d.get("model")
        max_tokens = d.get("max_tokens")
        if not isinstance(custom_id, str):
            msg = "request.custom_id must be a string"
            raise ValueError(msg)
        if not isinstance(messages, list) or not all(isinstance(m, str) for m in messages):
            msg = "request.messages must be a list of strings"
            raise ValueError(msg)
        if not isinstance(model, str):
            msg = "request.model must be a string"
            raise ValueError(msg)
        if not isinstance(max_tokens, int):
            msg = "request.max_tokens must be an int"
            raise ValueError(msg)
        system_prompt = d.get("system_prompt")
        sp = system_prompt if isinstance(system_prompt, str) else ""
        osp = d.get("output_schema_path")
        path: Path | None = None
        if isinstance(osp, str) and osp:
            path = schema_path_from_payload_value(osp)
        return Request(
            custom_id=custom_id,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            system_prompt=sp,
            output_schema_path=path,
        )


def create_batch_serialization_service() -> BatchSerializationService:
    """Default wiring for initializers, workers, and tests."""
    return BatchSerializationService()


__all__ = ["BatchSerializationService", "create_batch_serialization_service"]
