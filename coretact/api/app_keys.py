"""Application keys for type-safe aiohttp app state."""

from aiohttp import web

from coretact.storage import AdvertStorage

# Define AppKey instances for type-safe application state
DISCORD_INVITE_URL_KEY = web.AppKey("discord_invite_url", str)
STORAGE_KEY = web.AppKey("storage", AdvertStorage)
