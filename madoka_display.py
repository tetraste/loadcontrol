#!/usr/bin/env python3
"""Control the display brightness of a Daikin Madoka via ESPHome native API.

The Madoka BRC1H "eye" LED brightness is exposed by ESPHome as a Number entity
(range 0-19).  Value 0 turns the indicator off; 19 is maximum.

Usage examples:
  python madoka_display.py 192.168.1.50 --off
  python madoka_display.py 192.168.1.50 --brightness 5
  python madoka_display.py 192.168.1.50 --on
  python madoka_display.py 192.168.1.50 --get
  python madoka_display.py 192.168.1.50 --off --password mypass
  python madoka_display.py 192.168.1.50 --get --entity "Display"
"""

import asyncio
import argparse
import sys
from typing import Optional

try:
    from aioesphomeapi import APIClient
    from aioesphomeapi.model import NumberInfo, NumberEntityState
except ImportError:
    print("ERROR: aioesphomeapi not installed.  Run: pip install aioesphomeapi>=13.0", file=sys.stderr)
    sys.exit(1)

BRIGHTNESS_MIN = 0
BRIGHTNESS_MAX = 19

# Keywords used to auto-detect the brightness entity when --entity is not given
_SEARCH_TERMS = ("bright", "eye", "display", "lumin", "schermo", "madoka")


def _find_entity(entities: list, name_filter: Optional[str]) -> Optional[NumberInfo]:
    numbers = [e for e in entities if isinstance(e, NumberInfo)]
    if not numbers:
        return None
    if name_filter:
        hit = next((e for e in numbers if name_filter.lower() in e.name.lower()), None)
        return hit
    return next(
        (e for e in numbers if any(t in e.name.lower() for t in _SEARCH_TERMS)),
        None,
    )


async def _get_state(cli: APIClient, key: int) -> Optional[float]:
    """Subscribe to states and return the first value for the given entity key."""
    future: asyncio.Future = asyncio.get_event_loop().create_future()

    def on_state(state):
        if isinstance(state, NumberEntityState) and state.key == key:
            if not future.done():
                future.set_result(state.state)

    cli.subscribe_states(on_state)
    try:
        return await asyncio.wait_for(future, timeout=5.0)
    except asyncio.TimeoutError:
        return None


async def run(
    host: str,
    port: int,
    password: Optional[str],
    action: str,
    value: Optional[int],
    name_filter: Optional[str],
) -> None:
    cli = APIClient(host, port, password or "")
    try:
        await cli.connect(login=True)
    except Exception as exc:
        print(f"ERROR: cannot connect to {host}:{port} — {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        entities, _ = await cli.list_entities_services()
        entity = _find_entity(entities, name_filter)

        if entity is None:
            numbers = [e for e in entities if isinstance(e, NumberInfo)]
            print("ERROR: no matching Number entity found.", file=sys.stderr)
            if numbers:
                print("Available Number entities:", file=sys.stderr)
                for e in numbers:
                    print(f"  • {e.name!r}  (key={e.key})", file=sys.stderr)
                print(
                    "\nHint: use --entity <partial-name> to select one explicitly.",
                    file=sys.stderr,
                )
            else:
                print(
                    "No Number entities at all.  "
                    "Check that eye_brightness: is configured in the ESPHome YAML "
                    "(see esphome_eye_brightness.yaml for the snippet to add).",
                    file=sys.stderr,
                )
            sys.exit(1)

        if action == "get":
            current = await _get_state(cli, entity.key)
            if current is None:
                print("ERROR: timed out waiting for state update.", file=sys.stderr)
                sys.exit(1)
            print(f"{entity.name}: {int(current)}/{BRIGHTNESS_MAX}")
        else:
            target = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, value))  # type: ignore[arg-type]
            await cli.number_command(entity.key, float(target))
            print(f"{entity.name}: set to {target}")

    finally:
        await cli.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Control Daikin Madoka display brightness via ESPHome native API."
    )
    parser.add_argument("host", help="IP address or hostname of the ESP32 running ESPHome")
    parser.add_argument("--port", type=int, default=6053, help="ESPHome API port (default 6053)")
    parser.add_argument("--password", default=None, help="ESPHome API password (if set)")
    parser.add_argument(
        "--entity",
        default=None,
        metavar="NAME",
        help="Partial name of the Number entity to use (auto-detected if omitted)",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--off",
        dest="action",
        action="store_const",
        const="off",
        help="Turn off the eye LED (brightness = 0)",
    )
    group.add_argument(
        "--on",
        dest="action",
        action="store_const",
        const="on",
        help="Turn on the eye LED at maximum brightness (= 19)",
    )
    group.add_argument(
        "--brightness",
        dest="brightness_value",
        type=int,
        metavar="N",
        help=f"Set brightness to N (0 = off, {BRIGHTNESS_MAX} = max)",
    )
    group.add_argument(
        "--get",
        dest="action",
        action="store_const",
        const="get",
        help="Read current brightness value",
    )

    args = parser.parse_args()

    if args.brightness_value is not None:
        action = "set"
        value: Optional[int] = args.brightness_value
    elif args.action == "off":
        action, value = "set", BRIGHTNESS_MIN
    elif args.action == "on":
        action, value = "set", BRIGHTNESS_MAX
    else:
        action, value = "get", None

    asyncio.run(
        run(
            host=args.host,
            port=args.port,
            password=args.password,
            action=action,
            value=value,
            name_filter=args.entity,
        )
    )


if __name__ == "__main__":
    main()
