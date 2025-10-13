"""Main entry point for Coretact CLI."""

import argparse
import sys

from coretact import __version__
from coretact.bot import main as bot_main
from coretact.api import run_server


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
    bot_parser = subparsers.add_parser("bot", help="Run the Discord bot")

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

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "bot":
        bot_main()

    elif args.command == "api":
        run_server(host=args.host, port=args.port)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
