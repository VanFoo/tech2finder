"""Fetching the published dump. Goes through the Transport seam, so none of
this touches the network."""

import gzip
import hashlib
from pathlib import Path

import pytest

from tech2finder.sde.download import MD5_URL, ensure_dump
from tech2finder.sync.transport import Response

from ..sync.fake_transport import FakeTransport


def published(payload: bytes) -> tuple[Response, Response, str]:
    """A (md5sum, dump) pair as Fuzzwork publishes them, plus the digest."""
    compressed = gzip.compress(payload)
    digest = hashlib.md5(compressed).hexdigest()  # noqa: S324 - matching what is published
    return (
        Response(status=200, headers={}, body=f"{digest}  /some/server/path.gz\n".encode()),
        Response(status=200, headers={}, body=compressed),
        digest,
    )


async def test_downloads_decompresses_and_returns_the_dump(tmp_path: Path) -> None:
    md5, dump, digest = published(b"a pretend sqlite file")
    transport = FakeTransport(responses=[md5, dump])

    result = await ensure_dump(tmp_path, transport)

    assert result.path.read_bytes() == b"a pretend sqlite file"
    assert result.fingerprint == digest
    assert result.downloaded is True


async def test_checks_the_fingerprint_before_downloading_the_dump(tmp_path: Path) -> None:
    # The md5sum file is a few bytes and the dump is 136 MB, so an unchanged
    # SDE should cost the former and not the latter.
    md5, dump, _ = published(b"a pretend sqlite file")
    await ensure_dump(tmp_path, FakeTransport(responses=[md5, dump]))

    transport = FakeTransport(responses=[md5])  # no dump queued: asking for it would fail
    result = await ensure_dump(tmp_path, transport)

    assert result.downloaded is False
    assert [r.url for r in transport.requests] == [MD5_URL]


async def test_downloads_again_when_the_published_fingerprint_changes(tmp_path: Path) -> None:
    first_md5, first_dump, _ = published(b"old data")
    await ensure_dump(tmp_path, FakeTransport(responses=[first_md5, first_dump]))

    second_md5, second_dump, second_digest = published(b"new data")
    result = await ensure_dump(tmp_path, FakeTransport(responses=[second_md5, second_dump]))

    assert result.downloaded is True
    assert result.fingerprint == second_digest
    assert result.path.read_bytes() == b"new data"


async def test_rejects_a_download_whose_fingerprint_does_not_match(tmp_path: Path) -> None:
    md5 = Response(status=200, headers={}, body=b"0" * 32 + b"  /path.gz\n")
    dump = Response(status=200, headers={}, body=gzip.compress(b"corrupted in transit"))

    with pytest.raises(ValueError, match="fingerprint"):
        await ensure_dump(tmp_path, FakeTransport(responses=[md5, dump]))


async def test_does_not_leave_a_corrupt_dump_behind(tmp_path: Path) -> None:
    md5 = Response(status=200, headers={}, body=b"0" * 32 + b"  /path.gz\n")
    dump = Response(status=200, headers={}, body=gzip.compress(b"corrupted in transit"))

    with pytest.raises(ValueError):
        await ensure_dump(tmp_path, FakeTransport(responses=[md5, dump]))

    assert list(tmp_path.glob("*.db")) == []


async def test_reports_an_http_failure_rather_than_writing_the_body(tmp_path: Path) -> None:
    transport = FakeTransport(responses=[Response(status=503, headers={}, body=b"down")])

    with pytest.raises(OSError, match="503"):
        await ensure_dump(tmp_path, transport)
