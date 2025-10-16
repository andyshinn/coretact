"""Web server for the Coretact API."""

import os
from pathlib import Path

from aiohttp import web

from coretact.api.app_keys import DISCORD_INVITE_URL_KEY, STORAGE_KEY
from coretact.api.middleware import cors_middleware, error_middleware, logging_middleware
from coretact.api.routes import setup_routes
from coretact.log import logger
from coretact.storage import AdvertStorage


def create_app() -> web.Application:
    """Create and configure the aiohttp application.

    Returns:
        Configured aiohttp application
    """
    # Create application with middleware
    app = web.Application(
        middlewares=[
            logging_middleware,
            error_middleware,
            cors_middleware,
        ]
    )

    # Store configuration in app
    discord_invite = os.getenv("DISCORD_INVITE_URL")
    if discord_invite:
        app[DISCORD_INVITE_URL_KEY] = discord_invite

    # Initialize storage
    storage = AdvertStorage()
    app[STORAGE_KEY] = storage

    # Set up routes
    setup_routes(app)

    # Set up static file serving for landing page
    static_dir = Path(__file__).parent / "static"
    app.router.add_static("/static", static_dir, name="static")

    # Set up assets directory serving (for images, etc.)
    # Assets directory is at the project root
    assets_dir = Path(__file__).parent.parent.parent / "assets"
    if assets_dir.exists():
        app.router.add_static("/assets", assets_dir, name="assets")
        logger.info(f"Serving assets directory from {assets_dir}")

    # Serve index.html at root
    async def serve_index(_: web.Request) -> web.FileResponse:
        """Serve the index.html landing page."""
        return web.FileResponse(static_dir / "index.html")

    app.router.add_get("/", serve_index)

    logger.info("Coretact API application created")
    return app


def run_server(host: str | None = None, port: int | None = None) -> None:
    """Run the web server.

    Args:
        host: Host to bind to (defaults to WEB_API_HOST env or 0.0.0.0)
        port: Port to bind to (defaults to WEB_API_PORT env or 8080)
    """
    # Get configuration from environment or use defaults
    host = host or os.getenv("WEB_API_HOST", "0.0.0.0")
    port = port or int(os.getenv("WEB_API_PORT", "8080"))

    # Create app
    app = create_app()

    # Run server
    logger.info(f"Starting Coretact API server on {host}:{port}")
    web.run_app(app, host=host, port=port)
