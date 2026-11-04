"""Client for the web interface of Kostal Piko inverters.

The inverter has no API; the values are read from its web pages. The page
parsing (value positions, XPath expressions, layout detection) is derived from
the Python library "kostalpiko" (MIT, see NOTICE).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import aiohttp
from lxml import etree, html

TIMEOUT = aiohttp.ClientTimeout(total=15)

# Value positions per page layout, identified by the number of values on the
# page (including the status text that is appended last).
_BASE = {
    "current_power": 0,
    "total_energy": 1,
    "daily_energy": 2,
    "string1_voltage": 3,
    "l1_voltage": 4,
    "string1_current": 5,
    "l1_power": 6,
}
LAYOUTS: dict[int, dict[str, int]] = {
    # one string
    8: {**_BASE, "status": 7},
    # two strings, one phase
    10: {**_BASE, "string2_voltage": 7, "string2_current": 8, "status": 9},
    # two strings, two phases
    12: {
        **_BASE,
        "string2_voltage": 7,
        "l2_voltage": 8,
        "string2_current": 9,
        "l2_power": 10,
        "status": 11,
    },
    # two strings, three phases
    14: {
        **_BASE,
        "string2_voltage": 7,
        "l2_voltage": 8,
        "string2_current": 9,
        "l2_power": 10,
        "l3_voltage": 11,
        "l3_power": 12,
        "status": 13,
    },
    # three strings
    16: {
        **_BASE,
        "string2_voltage": 7,
        "l2_voltage": 8,
        "string2_current": 9,
        "l2_power": 10,
        "string3_voltage": 11,
        "l3_voltage": 12,
        "string3_current": 13,
        "l3_power": 14,
        "status": 15,
    },
}

# Conversion of the raw text of each value.
_CASTS = {
    "current_power": int,
    "total_energy": int,
    "daily_energy": float,
    "string1_voltage": int,
    "string1_current": float,
    "string2_voltage": int,
    "string2_current": float,
    "string3_voltage": int,
    "string3_current": float,
    "l1_voltage": int,
    "l1_power": int,
    "l2_voltage": int,
    "l2_power": int,
    "l3_voltage": int,
    "l3_power": int,
    "status": str,
}

# Positions of the values on the BA (own consumption) page.
_BA_INDICES = {
    "solar_generator_power": 5,
    "consumption_phase_1": 8,
    "consumption_phase_2": 9,
    "consumption_phase_3": 10,
}


class KostalError(Exception):
    """Base class of all client errors."""


class KostalConnectionError(KostalError):
    """The inverter did not answer (timeout, connection error, HTTP error)."""


class KostalAuthError(KostalError):
    """The inverter rejected the credentials (HTTP 401)."""


class KostalParseError(KostalError):
    """The page does not have the expected structure."""


@dataclass(frozen=True)
class PikoInfo:
    """Static information about the inverter."""

    serial_number: str
    model: str


class PikoData:
    """Values of the main page (index.fhtml)."""

    def __init__(self, raw: list) -> None:
        indices = LAYOUTS.get(len(raw))
        if indices is None:
            raise KostalParseError(f"Unsupported page layout with {len(raw)} values")
        self._raw = raw
        self._indices = indices

    def get(self, name: str):
        """Return a value converted to its type, or None if not available."""
        index = self._indices.get(name)
        if index is None:
            return None  # this inverter has no such value (e.g. third string)
        try:
            return _CASTS[name](self._raw[index])
        except (ValueError, TypeError):
            return None


class PikoBAData:
    """Values of the BA (own consumption) page (BA.fhtml)."""

    def __init__(self, raw: list) -> None:
        self._raw = raw

    def get(self, name: str):
        """Return a value, or None if the page does not contain it."""
        index = _BA_INDICES.get(name)
        if index is None or index >= len(self._raw):
            return None
        return self._raw[index]


def parse_index(content: bytes) -> list:
    """Parse index.fhtml into the list of raw values (status text last)."""
    try:
        page = html.fromstring(content)
        values = []
        for cell in page.xpath("//td[@bgcolor='#FFFFFF']"):
            text = cell.text.strip()
            values.append(0 if "x x x" in text else text)
        values.append(page.xpath("/html/body/form/font/table[2]/tr[8]/td[3]")[0].text.strip())
    except (IndexError, AttributeError, etree.LxmlError) as err:
        raise KostalParseError(f"Unexpected main page: {err!r}") from err
    return values


def parse_ba(content: bytes) -> list[float]:
    """Parse BA.fhtml into the list of values."""
    try:
        page = html.fromstring(content)
        values = []
        for bold in page.xpath("//b"):
            text = bold.text.strip()[:-1]  # remove the unit
            try:
                values.append(float(text))
            except ValueError:
                values.append(0)
    except (AttributeError, etree.LxmlError) as err:
        raise KostalParseError(f"Unexpected BA page: {err!r}") from err
    return values


def parse_info(content: bytes) -> PikoInfo:
    """Parse Solar2.fhtml into serial number and model."""
    try:
        page = html.fromstring(content)
        serial = page.xpath("/html/body/form/font/table/tr[2]/td[3]")[0].text.strip()
        model = page.xpath("/html/body/form/table/tr[2]/td[2]/font[1]")[0].text.strip()
    except (IndexError, AttributeError, etree.LxmlError) as err:
        raise KostalParseError(f"Unexpected info page: {err!r}") from err
    return PikoInfo(serial_number=serial, model=model)


class KostalClient:
    """Asynchronous client for one inverter."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._host = host.rstrip("/")
        try:
            credentials = f"{username}:{password}".encode("latin-1")
        except UnicodeEncodeError:
            credentials = f"{username}:{password}".encode("utf-8")
        self._headers = {"Authorization": "Basic " + base64.b64encode(credentials).decode("ascii")}

    async def _async_get(self, page: str) -> bytes:
        try:
            async with self._session.get(
                f"{self._host}/{page}", headers=self._headers, timeout=TIMEOUT
            ) as response:
                if response.status == 401:
                    raise KostalAuthError("Invalid username or password")
                if response.status != 200:
                    raise KostalConnectionError(f"HTTP {response.status} for {page}")
                return await response.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise KostalConnectionError(f"{page}: {err!r}") from err

    async def async_get_info(self) -> PikoInfo:
        """Return serial number and model."""
        return parse_info(await self._async_get("Solar2.fhtml"))

    async def async_get_data(self) -> PikoData:
        """Return the values of the main page."""
        return PikoData(parse_index(await self._async_get("index.fhtml")))

    async def async_get_ba_data(self) -> PikoBAData:
        """Return the values of the BA page."""
        return PikoBAData(parse_ba(await self._async_get("BA.fhtml")))
