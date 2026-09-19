from typing import Any, cast

import httpx
from fastapi import HTTPException
from pydantic import TypeAdapter

from .schemas import PendingSend, SendResult, ThreadDetail, ThreadList, ThreadSummary, validate_thread_summary

MAX_RESPONSE_BYTES = 1_000_000
UPSTREAM_TIMEOUT = httpx.Timeout(connect=2.0, read=90, write=5.0, pool=2.0)


class AgentOSClient:
    """One reusable, bounded upstream client per BFF process."""

    def __init__(self, base_url: str, pat: str, transport: httpx.BaseTransport | None = None):
        self.base_url, self.pat = base_url.rstrip("/"), pat
        self.timeout = UPSTREAM_TIMEOUT
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            headers = {"Authorization": f"Bearer {self.pat}"} if self.pat else {}
            response = self._client.request(
                method,
                path,
                headers=headers,
                **kwargs,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "Support service unavailable") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, "Support service unavailable") from exc
        if len(response.content) > MAX_RESPONSE_BYTES or response.status_code >= 400:
            raise HTTPException(502, "Support service unavailable")
        return response

    def threads(self) -> list[ThreadSummary]:
        try:
            envelope = ThreadList.model_validate(self._request("GET", "/api/support/threads").json())
            return [validate_thread_summary(item) for item in envelope.threads]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, "Support service unavailable") from exc

    def thread(self, session_id: str) -> ThreadDetail:
        try:
            return ThreadDetail.model_validate(self._request("GET", f"/api/support/threads/{session_id}").json())
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, "Support service unavailable") from exc

    def send(self, payload: dict[str, str]) -> tuple[int, SendResult]:
        try:
            response = self._request("POST", "/api/support/emails", json=payload)
            result_type = PendingSend if response.status_code == 202 else ThreadDetail
            result = TypeAdapter(result_type).validate_python(response.json())
            return response.status_code, cast(SendResult, result)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, "Support service unavailable") from exc
