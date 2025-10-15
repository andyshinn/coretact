"""Middleware for the Coretact Web API."""

from typing import Callable

from aiohttp import web
from aiohttp.web_middlewares import middleware

from coretact.log import logger


@middleware
async def cors_middleware(request: web.Request, handler: Callable) -> web.Response:
    """Add CORS headers to all responses.

    Args:
        request: The incoming request
        handler: The request handler

    Returns:
        Response with CORS headers
    """
    # Handle preflight OPTIONS requests
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)

    # Add CORS headers
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Max-Age"] = "3600"

    return response


@middleware
async def error_middleware(request: web.Request, handler: Callable) -> web.Response:
    """Handle errors and return JSON error responses.

    Args:
        request: The incoming request
        handler: The request handler

    Returns:
        Response or JSON error response
    """
    try:
        return await handler(request)
    except web.HTTPException as ex:
        # Let redirects (3xx status codes) pass through as-is
        if 300 <= ex.status < 400:
            raise

        # HTTPException already has status code and reason
        error_data = {
            "error": ex.reason,
            "status": ex.status,
        }
        logger.warning(f"HTTP {ex.status}: {ex.reason} - {request.path}")
        return web.json_response(error_data, status=ex.status)
    except ValueError as e:
        # Validation errors
        error_data = {
            "error": str(e),
            "status": 400,
        }
        logger.warning(f"Validation error: {e} - {request.path}")
        return web.json_response(error_data, status=400)
    except Exception as e:
        # Unexpected errors
        error_data = {
            "error": "Internal server error",
            "status": 500,
        }
        logger.error(f"Unexpected error: {type(e).__name__}: {e} - {request.path}")
        return web.json_response(error_data, status=500)


@middleware
async def logging_middleware(request: web.Request, handler: Callable) -> web.Response:
    """Log all requests.

    Args:
        request: The incoming request
        handler: The request handler

    Returns:
        Response from handler
    """
    logger.info(f"{request.method} {request.path} - {request.remote}")
    response = await handler(request)
    logger.info(f"{request.method} {request.path} - {response.status}")
    return response
