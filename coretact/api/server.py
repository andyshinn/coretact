"""Web server for the Coretact API."""

import os

from aiohttp import web

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

    # Initialize storage
    storage = AdvertStorage()
    app["storage"] = storage

    # Set up routes
    setup_routes(app)

    logger.info("Coretact API application created")
    return app


def run_server(host: str|None = None, port: int|None = None) -> None:
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
