"""Read an inverter with the client of this integration and print the values.

Usage (the password is asked for, or taken from KOSTAL_PASSWORD):

    uv run --with aiohttp --with lxml scripts/check_inverter.py http://192.168.1.50 pvserver

Needs only aiohttp and lxml, not Home Assistant.
"""

import asyncio
import getpass
import importlib.util
import os
import sys
import time
from pathlib import Path

import aiohttp

CLIENT = Path(__file__).parent.parent / "custom_components" / "kostal" / "client.py"
spec = importlib.util.spec_from_file_location("kostal_client", CLIENT)
client_module = importlib.util.module_from_spec(spec)
sys.modules["kostal_client"] = client_module  # needed for the dataclass
spec.loader.exec_module(client_module)


async def main(host: str, username: str, password: str) -> int:
    async with aiohttp.ClientSession() as session:
        client = client_module.KostalClient(session, host, username, password)
        try:
            started = time.monotonic()
            info = await client.async_get_info()
            data = await client.async_get_data()
            ba_data = await client.async_get_ba_data()
            elapsed = time.monotonic() - started
        except client_module.KostalAuthError:
            print("Login rejected: wrong username or password.")
            return 2
        except client_module.KostalError as err:
            print(f"Error ({type(err).__name__}): {err}")
            return 1

    print(f"Model: {info.model}, serial number: {info.serial_number}")
    print(f"Three requests took {elapsed:.2f} s\n")
    for name in client_module.LAYOUTS[16]:
        print(f"  {name:18} {data.get(name)}")
    print("\nBA page:")
    for name in client_module._BA_INDICES:
        print(f"  {name:22} {ba_data.get(name)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    pw = os.environ.get("KOSTAL_PASSWORD") or getpass.getpass("Password: ")
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2], pw)))
