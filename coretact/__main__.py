"""Main entry point for Coretact CLI."""

import argparse
import sys

from coretact.version import __version__


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Coretact - Meshcore Contact Management System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"Coretact {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Bot command
    subparsers.add_parser("bot", help="Run the Discord bot")

    # API server command
    api_parser = subparsers.add_parser("api", help="Run the Web API server")
    api_parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind to (default: WEB_API_HOST env or 0.0.0.0)",
    )
    api_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: WEB_API_PORT env or 8080)",
    )

    # Decode command
    decode_parser = subparsers.add_parser("decode", help="Decode a meshcore:// advertisement URL")
    decode_parser.add_argument(
        "url",
        type=str,
        help="The meshcore:// URL to decode",
    )
    decode_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of human-readable text",
    )

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "bot":
        from coretact.bot import main as bot_main

        bot_main()

    elif args.command == "api":
        from coretact.api import run_server

        run_server(host=args.host, port=args.port)

    elif args.command == "decode":
        from coretact.meshcore.parser import AdvertParser
        import json
        from datetime import datetime

        try:
            parsed = AdvertParser.parse(args.url)

            if args.json:
                # Output as JSON
                data = {
                    "format_type": parsed.format_type,
                    "public_key": parsed.public_key,
                    "type": parsed.type_name,
                    "type_id": parsed.adv_type,
                    "timestamp": parsed.timestamp,
                    "signature": parsed.signature,
                    "signature_valid": parsed.verify_signature(),
                    "name": parsed.name,
                    "latitude": parsed.latitude,
                    "longitude": parsed.longitude,
                    "battery_mv": parsed.battery,
                    "temperature_c": parsed.temperature,
                    "flags": parsed.flags,
                }
                print(json.dumps(data, indent=2))
            else:
                # Human-readable output
                print("=== Meshcore Advertisement ===")
                print(f"Format: {parsed.format_type}")
                print(f"Type: {parsed.type_name} ({parsed.adv_type})")
                print()
                print(f"Public Key: {parsed.public_key}")
                print()
                if parsed.timestamp:
                    dt = datetime.fromtimestamp(parsed.timestamp)
                    print(f"Timestamp: {parsed.timestamp} ({dt.isoformat()})")
                if parsed.signature:
                    print(f"Signature: {parsed.signature}")
                    is_valid = parsed.verify_signature()
                    if is_valid:
                        print("Signature Status: ✓ VALID")
                    else:
                        print("Signature Status: ✗ INVALID")
                print()
                if parsed.name:
                    print(f"Name: {parsed.name}")
                if parsed.latitude is not None and parsed.longitude is not None:
                    print(f"Location: {parsed.latitude}, {parsed.longitude}")
                if parsed.battery is not None:
                    print(f"Battery: {parsed.battery} mV")
                if parsed.temperature is not None:
                    print(f"Temperature: {parsed.temperature} °C")
                print()
                print(f"Flags: 0x{parsed.flags:02x} ({parsed.flags:08b}b)")

        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
