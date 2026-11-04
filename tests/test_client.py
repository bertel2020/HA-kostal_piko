"""Tests for the page parser and the HTTP client."""
from pathlib import Path

import aiohttp
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.kostal.client import (
    KostalAuthError,
    KostalClient,
    KostalConnectionError,
    KostalParseError,
    PikoBAData,
    PikoData,
    parse_ba,
    parse_index,
    parse_info,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _page(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# raw values of every fixture page, taken from the output of the kostalpiko library
RAW = {
    "library/index2-1.html": ["2336", "33523", "11.71", "338", "236", "3.88", "2336", "336", "3.97", "supply MPP"],
    "library/index55-1.html": [
        "112", "9290", "19.83", "384", "230", "0.20", "0", "278",
        "232", "0.21", "112", "0", "230", "0.00", "0", "Einspeisen MPP",
    ],
    "library/index55-2.html": [
        "3126", "41801", "13.46", "275", "247", "6.27", "1032", "247",
        "241", "6.47", "1027", "0", "246", "0.00", "1069", "toevoer MPP",
    ],
    "real/index.html": [
        "528", "125134", "0.88", "552", "238", "0.30", "0", "680",
        "232", "0.31", "528", "665", "232", "0.30", "0", "Einspeisen (MPP)",
    ],
}


@pytest.mark.parametrize("name", RAW)
def test_parse_index_raw_values(name):
    assert parse_index(_page(name)) == RAW[name]


def test_three_string_inverter_values():
    data = PikoData(parse_index(_page("real/index.html")))
    assert data.get("current_power") == 528
    assert data.get("total_energy") == 125134
    assert data.get("daily_energy") == 0.88
    assert [data.get(f"string{n}_voltage") for n in (1, 2, 3)] == [552, 680, 665]
    assert [data.get(f"string{n}_current") for n in (1, 2, 3)] == [0.3, 0.31, 0.3]
    assert [data.get(f"l{n}_voltage") for n in (1, 2, 3)] == [238, 232, 232]
    assert [data.get(f"l{n}_power") for n in (1, 2, 3)] == [0, 528, 0]
    assert data.get("status") == "Einspeisen (MPP)"


def test_two_string_single_phase_layout():
    data = PikoData(parse_index(_page("library/index2-1.html")))
    assert data.get("current_power") == 2336
    assert data.get("string2_voltage") == 336
    assert data.get("string2_current") == 3.97
    assert data.get("status") == "supply MPP"
    # values this inverter does not have are unknown, not an error
    assert data.get("string3_voltage") is None
    assert data.get("l2_power") is None


def test_other_three_string_layout():
    data = PikoData(parse_index(_page("library/index55-2.html")))
    assert data.get("current_power") == 3126
    assert data.get("l1_power") == 1032
    assert data.get("string3_voltage") == 0
    assert data.get("l3_voltage") == 246
    assert data.get("l3_power") == 1069


def test_standby_placeholder_becomes_zero():
    content = _page("real/index.html").replace(b"  528</td>", b"  x x x</td>", 1)
    assert content != _page("real/index.html")
    assert parse_index(content)[0] == 0


def test_unsupported_layout_is_an_error():
    with pytest.raises(KostalParseError):
        PikoData(["1", "2", "3"])


def test_garbage_page_is_a_parse_error():
    with pytest.raises(KostalParseError):
        parse_index(b"<html><body>nothing here</body></html>")
    with pytest.raises(KostalParseError):
        parse_info(b"<html><body>nothing here</body></html>")


def test_non_numeric_value_is_unknown():
    raw = ["---"] + RAW["real/index.html"][1:]
    assert PikoData(raw).get("current_power") is None


def test_parse_info():
    info = parse_info(_page("real/solar2.html"))
    assert info.serial_number == "TESTSERIAL001"
    assert info.model == "PIKO 10.1"


def test_parse_ba_page_without_sensor():
    values = parse_ba(_page("real/ba.html"))
    assert len(values) == 11
    data = PikoBAData(values)
    assert data.get("solar_generator_power") == 0.0
    assert data.get("consumption_phase_3") == 0.0
    assert PikoBAData([]).get("solar_generator_power") is None


# --- HTTP client ---------------------------------------------------------------

URL = "http://192.168.1.50"


def _client(hass):
    return KostalClient(async_get_clientsession(hass), URL + "/", "pvserver", "pvwr")


async def test_client_reads_all_pages(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/index.fhtml", content=_page("real/index.html"))
    aioclient_mock.get(f"{URL}/BA.fhtml", content=_page("real/ba.html"))
    aioclient_mock.get(f"{URL}/Solar2.fhtml", content=_page("real/solar2.html"))
    client = _client(hass)

    assert (await client.async_get_data()).get("current_power") == 528
    assert (await client.async_get_ba_data()).get("solar_generator_power") == 0.0
    assert (await client.async_get_info()).model == "PIKO 10.1"
    # pvserver:pvwr as Basic-Auth header
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Basic cHZzZXJ2ZXI6cHZ3cg=="


async def test_wrong_password_is_an_auth_error(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/index.fhtml", status=401)
    with pytest.raises(KostalAuthError):
        await _client(hass).async_get_data()


async def test_http_error_is_a_connection_error(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/index.fhtml", status=500)
    with pytest.raises(KostalConnectionError):
        await _client(hass).async_get_data()


@pytest.mark.parametrize("exc", [TimeoutError, aiohttp.ClientConnectionError])
async def test_network_errors_are_connection_errors(hass, aioclient_mock, exc):
    aioclient_mock.get(f"{URL}/index.fhtml", exc=exc)
    with pytest.raises(KostalConnectionError):
        await _client(hass).async_get_data()
