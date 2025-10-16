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
        from coretact.meshcore import decode_advert_to_dict
        import json
        from datetime import datetime

        try:
            # Use shared utility to decode
            data = decode_advert_to_dict(args.url)

            if args.json:
                # Output as JSON (with some field name adjustments for backwards compatibility)
                output = {
                    "format_type": data["format_type"],
                    "public_key": data["public_key"],
                    "type": data["type_name"],
                    "type_id": data["adv_type"],
                    "timestamp": data.get("timestamp"),
                    "signature": data.get("signature"),
                    "signature_valid": data.get("signature_valid"),
                    "name": data["name"],
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "battery_mv": data.get("battery"),
                    "temperature_c": data.get("temperature"),
                    "flags": data.get("flags"),
                }
                print(json.dumps(output, indent=2))
            else:
                # Human-readable output
                print("=== Meshcore Advertisement ===")
                print(f"Format: {data['format_type']}")
                print(f"Type: {data['type_name']} ({data['adv_type']})")
                print()
                print(f"Public Key: {data['public_key']}")
                print()
                if data.get("timestamp"):
                    dt = datetime.fromtimestamp(data["timestamp"])
                    print(f"Timestamp: {data['timestamp']} ({dt.isoformat()})")
                if data.get("signature"):
                    print(f"Signature: {data['signature']}")
                    is_valid = data.get("signature_valid", False)
                    if is_valid:
                        print("Signature Status: ✓ VALID")
                    else:
                        print("Signature Status: ✗ INVALID")
                print()
                if data["name"]:
                    print(f"Name: {data['name']}")
                if data.get("latitude") is not None and data.get("longitude") is not None:
                    print(f"Location: {data['latitude']}, {data['longitude']}")
                if data.get("battery") is not None:
                    print(f"Battery: {data['battery']} mV")
                if data.get("temperature") is not None:
                    print(f"Temperature: {data['temperature']} °C")
                print()
                if data.get("flags") is not None:
                    print(f"Flags: 0x{data['flags']:02x} ({data['flags']:08b}b)")

        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
