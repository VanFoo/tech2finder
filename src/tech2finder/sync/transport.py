"""The seam between this project and the network.

Everything that reaches ESI goes through a Transport, so the sync layer's
policy — bounded concurrency, the error budget, the Expires floor — is
assertable against a fake rather than against the live API.
"""

from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def header(self, name: str) -> str | None:
        """Look a header up without regard to case, as HTTP requires."""
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return None


class Transport(Protocol):
    async def get(self, url: str, headers: dict[str, str] | None = None) -> Response: ...


class HttpxTransport:
    """The real thing. Carries no policy — retries, backoff and the error
    budget belong to the sync layer above, so that they stay testable."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get(self, url: str, headers: dict[str, str] | None = None) -> Response:
        response = await self._client.get(url, headers=headers)
        return Response(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )
