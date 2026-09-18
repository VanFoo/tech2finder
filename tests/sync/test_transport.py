"""Seam 2: everything that talks to ESI goes through Transport, so the sync
layer's policy is assertable without a network."""

from tech2finder.sync.transport import Response, Transport

from .fake_transport import FakeTransport


def test_the_fake_satisfies_the_transport_protocol() -> None:
    transport: Transport = FakeTransport()

    assert transport is not None


async def test_the_fake_answers_from_its_queue_in_order() -> None:
    transport = FakeTransport(
        responses=[
            Response(status=200, headers={}, body=b"first"),
            Response(status=200, headers={}, body=b"second"),
        ]
    )

    assert (await transport.get("https://esi.example/a")).body == b"first"
    assert (await transport.get("https://esi.example/b")).body == b"second"


async def test_the_fake_records_what_was_requested() -> None:
    transport = FakeTransport(responses=[Response(status=200, headers={}, body=b"")])

    await transport.get("https://esi.example/a", headers={"User-Agent": "tech2finder"})

    assert transport.requests[0].url == "https://esi.example/a"
    assert transport.requests[0].headers["User-Agent"] == "tech2finder"


def test_response_headers_are_matched_without_regard_to_case() -> None:
    # ESI's rate-limit and Expires headers are read by name; HTTP header names
    # are case-insensitive and servers do not agree on capitalisation.
    response = Response(status=200, headers={"X-Esi-Error-Limit-Remain": "100"}, body=b"")

    assert response.header("x-esi-error-limit-remain") == "100"
    assert response.header("X-ESI-Error-Limit-Remain") == "100"
    assert response.header("Expires") is None
