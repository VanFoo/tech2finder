"""A Transport that answers from a queue instead of the network.

Lives in the test tree because it is test infrastructure, but is shared: the
ESI sync ticket asserts its rate-limit and staleness policy through this.
"""

from dataclasses import dataclass, field

from tech2finder.sync.transport import Response


@dataclass
class Request:
    url: str
    headers: dict[str, str]


@dataclass
class FakeTransport:
    """Returns queued responses in order, recording what was asked for."""

    responses: list[Response] = field(default_factory=list)
    requests: list[Request] = field(default_factory=list)

    async def get(self, url: str, headers: dict[str, str] | None = None) -> Response:
        self.requests.append(Request(url=url, headers=dict(headers or {})))
        if not self.responses:
            raise AssertionError(f"FakeTransport has no queued response for {url}")
        return self.responses.pop(0)
