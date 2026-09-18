"""The ESI client: the only thing in this project that talks to CCP.

Three endpoints, and only the first scales per item:

- market history — one call **per type id**; the Valuation Basis and daily
  traded volume.
- market prices — one call for **every** type; CCP's ``adjusted_price``, which
  job installation fees are assessed on. Not a market price, and not derivable
  from one.
- industry systems — one call for **every** system; the System Cost Index, read
  and never computed (the published formula is known-stale).

Retries and backoff live here rather than in the budget, which only decides how
many requests may be in flight.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode

from tech2finder.sync.budget import ErrorBudget
from tech2finder.sync.transport import Transport

BASE = "https://esi.evetech.net/latest"

#: The Forge, the region Jita is in. ADR-0001 prices everything at one hub.
THE_FORGE = 10000002

#: Retried: 420 means already error-limited, 5xx means ESI is unwell. A 4xx will
#: not become a 200 by asking again, and retrying it only spends budget.
RETRYABLE = frozenset({420, 500, 502, 503, 504})

#: Rejected as contact addresses. Shipping a config example means the
#: placeholder will sometimes be left in it.
PLACEHOLDERS = ("your-email", "youremail", "example.com", "change-me", "changeme", "todo")


class UnidentifiedClient(Exception):
    """Raised rather than making a request CCP cannot attribute to anyone."""


@dataclass(frozen=True)
class HistoryRow:
    date: str
    average: float
    highest: float
    lowest: float
    order_count: int
    volume: int


@dataclass(frozen=True)
class History:
    type_id: int
    #: Only days that actually traded: ESI emits no row for a day with no
    #: trades, never a row with volume 0. So the row count is itself a
    #: liquidity signal.
    rows: tuple[HistoryRow, ...]
    expires: datetime | None


@dataclass(frozen=True)
class AdjustedPrice:
    type_id: int
    adjusted_price: float | None
    average_price: float | None


@dataclass(frozen=True)
class Prices:
    prices: dict[int, AdjustedPrice]
    expires: datetime | None


@dataclass(frozen=True)
class CostIndices:
    #: (solar_system_id, activity) -> index
    indices: dict[tuple[int, str], float]
    expires: datetime | None


class EsiClient:
    def __init__(
        self,
        transport: Transport,
        budget: ErrorBudget,
        user_agent: str,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        retries: int = 3,
    ) -> None:
        _reject_unidentified(user_agent)
        self._transport = transport
        self.budget = budget
        self._user_agent = user_agent
        self._sleep = sleep
        self._retries = retries

    async def market_history(self, region_id: int, type_id: int) -> History:
        query = urlencode({"type_id": type_id})
        payload, expires = await self._get(f"{BASE}/markets/{region_id}/history/?{query}")
        return History(
            type_id=type_id,
            rows=tuple(
                HistoryRow(
                    date=str(row["date"]),
                    average=float(row["average"]),
                    highest=float(row["highest"]),
                    lowest=float(row["lowest"]),
                    order_count=int(row["order_count"]),
                    volume=int(row["volume"]),
                )
                for row in payload
            ),
            expires=expires,
        )

    async def market_prices(self) -> Prices:
        payload, expires = await self._get(f"{BASE}/markets/prices/")
        return Prices(
            prices={
                int(row["type_id"]): AdjustedPrice(
                    type_id=int(row["type_id"]),
                    # Absent is not zero: an item CCP publishes no adjusted
                    # price for cannot have its job fee computed.
                    adjusted_price=_optional_float(row.get("adjusted_price")),
                    average_price=_optional_float(row.get("average_price")),
                )
                for row in payload
            },
            expires=expires,
        )

    async def industry_systems(self) -> CostIndices:
        payload, expires = await self._get(f"{BASE}/industry/systems/")
        return CostIndices(
            indices={
                (int(row["solar_system_id"]), str(index["activity"])): float(index["cost_index"])
                for row in payload
                for index in row["cost_indices"]
            },
            expires=expires,
        )

    async def _get(self, url: str) -> tuple[Any, datetime | None]:
        """Returns parsed JSON, which is genuinely untyped; callers coerce."""
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        backoff = 1.0
        attempt = 0

        while True:
            async with self.budget.slot():
                response = await self._transport.get(url, headers=headers)

            # Learned from every response, success included: ESI reports the
            # budget on a 200, so a scan finds out it is in trouble without
            # having to fail first.
            self.budget.observe(response)

            if response.status == 200:
                payload = json.loads(response.body)
                return payload, _expires(response.header("Expires"))

            if response.status not in RETRYABLE or attempt >= self._retries:
                raise OSError(f"GET {url} returned {response.status}")

            await self._sleep(backoff)
            backoff *= 2
            attempt += 1


def _optional_float(value: Any) -> float | None:
    """Absent stays absent: a missing adjusted price is not a price of zero."""
    return None if value is None else float(value)


def _reject_unidentified(user_agent: str) -> None:
    lowered = user_agent.strip().lower()
    if not lowered:
        raise UnidentifiedClient("ESI requires a User-Agent naming the app and a contact address")
    if "@" not in lowered:
        raise UnidentifiedClient(
            f"User-Agent {user_agent!r} carries no contact address; CCP asks third-party "
            f"clients to be reachable, and unidentified traffic is what gets blocked"
        )
    if any(marker in lowered for marker in PLACEHOLDERS):
        raise UnidentifiedClient(
            f"User-Agent {user_agent!r} still contains a placeholder contact address"
        )


def _expires(header: str | None) -> datetime | None:
    """ESI's Expires is an HTTP date. It is a floor on re-fetching, never a trigger."""
    if header is None:
        return None
    try:
        return parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return None
