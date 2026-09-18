"""Fetching the published SDE dump.

Fuzzwork publishes a stable symlink plus a companion md5sum file. The md5sum is
a few dozen bytes and the dump is 136 MB, so the fingerprint is always checked
first: an unchanged SDE costs one tiny request.

The URL that older references give — ``dump/latest/sqlite-latest.sqlite.bz2`` —
404s, and the timestamped files inside ``dump/latest/`` are not stable. Only the
root-level symlinks below are.
"""

import gzip
import hashlib
from dataclasses import dataclass
from pathlib import Path

from tech2finder.sync.transport import Transport

BASE = "https://www.fuzzwork.co.uk/dump"
DUMP_URL = f"{BASE}/latest-sqlite.db.gz"
MD5_URL = f"{DUMP_URL}.md5sum"

DUMP_NAME = "sde.db"
FINGERPRINT_NAME = "sde.db.md5"


@dataclass(frozen=True)
class Dump:
    path: Path
    fingerprint: str
    #: False when the local copy already matched what is published.
    downloaded: bool


async def ensure_dump(directory: Path, transport: Transport) -> Dump:
    """Make ``directory`` hold the current SDE, downloading only if it does not."""
    directory.mkdir(parents=True, exist_ok=True)
    dump = directory / DUMP_NAME
    fingerprint_file = directory / FINGERPRINT_NAME

    published = _parse_md5sum(await _get(transport, MD5_URL))

    if (
        dump.is_file()
        and fingerprint_file.is_file()
        and fingerprint_file.read_text().strip() == published
    ):
        return Dump(path=dump, fingerprint=published, downloaded=False)

    # Held in memory once. At 136 MB that is cheaper than a second transport
    # abstraction for streaming, and this runs at most once per SDE release.
    compressed = await _get(transport, DUMP_URL)

    actual = hashlib.md5(compressed).hexdigest()  # noqa: S324 - matching what is published
    if actual != published:
        raise ValueError(
            f"downloaded SDE fingerprint {actual} does not match the published {published}"
        )

    # Decompress beside the target and move into place, so an interrupted run
    # never leaves a half-written dump that looks complete.
    staging = directory / f"{DUMP_NAME}.partial"
    staging.write_bytes(gzip.decompress(compressed))
    staging.replace(dump)
    fingerprint_file.write_text(published)

    return Dump(path=dump, fingerprint=published, downloaded=True)


async def _get(transport: Transport, url: str) -> bytes:
    response = await transport.get(url)
    if response.status != 200:
        raise OSError(f"GET {url} returned {response.status}")
    return response.body


def _parse_md5sum(body: bytes) -> str:
    """``md5sum`` output is ``<digest>  <path>``; only the digest matters."""
    digest = body.decode().split()[0].strip()
    if len(digest) != 32:
        raise ValueError(f"unexpected md5sum file contents: {body!r}")
    return digest
