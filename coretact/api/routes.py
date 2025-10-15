"""API routes for the Coretact Web API."""

from typing import List, Optional

from aiohttp import web

from coretact.version import __version__
from coretact.log import logger
from coretact.models import Mesh
from coretact.storage import AdvertStorage, ContactConverter, ContactFilter


async def invite_redirect(request: web.Request) -> web.Response:
    """Redirect to Discord bot invite URL.

    Returns:
        HTTP redirect to Discord invite URL or 404 if not configured
    """
    discord_invite_url = request.app.get("discord_invite_url")

    if not discord_invite_url:
        raise web.HTTPNotFound(reason="Discord invite URL not configured")

    logger.info(f"Redirecting to Discord invite URL")
    raise web.HTTPFound(discord_invite_url)


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint.

    Returns:
        JSON response with status and version
    """
    return web.json_response({"status": "ok", "version": __version__})


async def get_mesh_contacts(request: web.Request) -> web.Response:
    """Get all contacts for a mesh (Discord server).

    Query Parameters:
        type: Filter by device type (1, 2, or 3)
        key_prefix: Filter by public key prefix
        name: Filter by name (partial match)
        user_id: Filter by Discord user ID

    Returns:
        JSON response with ContactsList
    """
    storage: AdvertStorage = request.app["storage"]
    server_id = request.match_info["server_id"]

    # Parse query parameters
    type_filter = request.query.get("type")
    key_prefix = request.query.get("key_prefix")
    name = request.query.get("name")
    user_id = request.query.get("user_id")

    # Convert type to int if provided
    type_id: Optional[int] = None
    if type_filter:
        try:
            type_id = int(type_filter)
            if type_id not in (1, 2, 3):
                raise ValueError("Type must be 1, 2, or 3")
        except ValueError as e:
            raise web.HTTPBadRequest(reason=f"Invalid type parameter: {e}")

    # Get all adverts for the server
    adverts = list(storage.list_server_adverts(discord_server_id=server_id))

    # Apply filters
    filtered_adverts = ContactFilter.filter_adverts(
        adverts,
        type=type_id,
        key_prefix=key_prefix,
        name=name,
        user_id=user_id,
    )

    # Convert to ContactsList
    contacts_list = ContactConverter.adverts_to_contacts_list(filtered_adverts)

    # Serialize to JSON
    contacts_dict = {
        "contacts": [
            {
                "type": c.type,
                "name": c.name,
                "custom_name": c.custom_name,
                "public_key": c.public_key,
                "flags": c.flags,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "last_advert": c.last_advert,
                "last_modified": c.last_modified,
                "out_path": c.out_path,
            }
            for c in contacts_list.contacts
        ]
    }

    logger.info(f"Returned {len(contacts_list.contacts)} contacts for mesh {server_id}")
    return web.json_response(contacts_dict)


async def get_contact_by_key(request: web.Request) -> web.Response:
    """Get a single contact by public key.

    Searches across all meshes to find the advert.

    Returns:
        JSON response with Contact including metadata
    """
    storage: AdvertStorage = request.app["storage"]
    public_key = request.match_info["public_key"].lower()

    # Search for the public key across all servers
    advert = storage.find_advert_by_public_key(public_key)

    if not advert:
        raise web.HTTPNotFound(reason=f"Contact with public key {public_key} not found")

    # Convert to Contact
    contact = ContactConverter.advert_to_contact(advert)

    # Serialize with additional metadata
    contact_dict = {
        "type": contact.type,
        "name": contact.name,
        "custom_name": contact.custom_name,
        "public_key": contact.public_key,
        "flags": contact.flags,
        "latitude": contact.latitude,
        "longitude": contact.longitude,
        "last_advert": contact.last_advert,
        "last_modified": contact.last_modified,
        "out_path": contact.out_path,
        # Additional metadata
        "advert_string": advert.advert_string,
        "discord_server_id": advert.discord_server_id,
        "discord_user_id": advert.discord_user_id,
    }

    logger.info(f"Returned contact for public key {public_key}")
    return web.json_response(contact_dict)


async def bulk_contacts(request: web.Request) -> web.Response:
    """Get specific contacts by public keys.

    Request body:
        {
            "public_keys": ["key1", "key2", ...],
            "include_metadata": true  // optional
        }

    Returns:
        JSON response with ContactsList containing only matching contacts
    """
    storage: AdvertStorage = request.app["storage"]
    server_id = request.match_info["server_id"]

    # Parse request body
    try:
        data = await request.json()
    except Exception as e:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {e}")

    # Validate request body
    if "public_keys" not in data:
        raise web.HTTPBadRequest(reason="Missing 'public_keys' field")

    public_keys: List[str] = data["public_keys"]
    include_metadata: bool = data.get("include_metadata", False)

    if not isinstance(public_keys, list):
        raise web.HTTPBadRequest(reason="'public_keys' must be a list")

    if not public_keys:
        raise web.HTTPBadRequest(reason="'public_keys' cannot be empty")

    # Normalize keys to lowercase
    public_keys = [key.lower() for key in public_keys]

    # Get all adverts for the server
    all_adverts = list(storage.list_server_adverts(discord_server_id=server_id))

    # Filter to only requested keys
    matching_adverts = [advert for advert in all_adverts if advert.public_key in public_keys]

    # Convert to ContactsList
    contacts_list = ContactConverter.adverts_to_contacts_list(matching_adverts)

    # Serialize to JSON
    if include_metadata:
        # Include full advert metadata
        contacts_dict = {
            "contacts": [
                {
                    "type": c.type,
                    "name": c.name,
                    "custom_name": c.custom_name,
                    "public_key": c.public_key,
                    "flags": c.flags,
                    "latitude": c.latitude,
                    "longitude": c.longitude,
                    "last_advert": c.last_advert,
                    "last_modified": c.last_modified,
                    "out_path": c.out_path,
                    # Additional metadata
                    "advert_string": advert.advert_string,
                    "discord_server_id": advert.discord_server_id,
                    "discord_user_id": advert.discord_user_id,
                }
                for c, advert in zip(contacts_list.contacts, matching_adverts)
            ]
        }
    else:
        contacts_dict = {
            "contacts": [
                {
                    "type": c.type,
                    "name": c.name,
                    "custom_name": c.custom_name,
                    "public_key": c.public_key,
                    "flags": c.flags,
                    "latitude": c.latitude,
                    "longitude": c.longitude,
                    "last_advert": c.last_advert,
                    "last_modified": c.last_modified,
                    "out_path": c.out_path,
                }
                for c in contacts_list.contacts
            ]
        }

    logger.info(f"Returned {len(matching_adverts)} of {len(public_keys)} requested contacts for mesh {server_id}")
    return web.json_response(contacts_dict)


async def get_user_contacts(request: web.Request) -> web.Response:
    """Get all contacts for a specific Discord user.

    Returns:
        JSON response with ContactsList
    """
    storage: AdvertStorage = request.app["storage"]
    server_id = request.match_info["server_id"]
    user_id = request.match_info["user_id"]

    # Get user's adverts
    adverts = storage.list_user_adverts(
        discord_server_id=server_id,
        discord_user_id=user_id,
    )

    # Convert to ContactsList
    contacts_list = ContactConverter.adverts_to_contacts_list(adverts)

    # Serialize to JSON
    contacts_dict = {
        "contacts": [
            {
                "type": c.type,
                "name": c.name,
                "custom_name": c.custom_name,
                "public_key": c.public_key,
                "flags": c.flags,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "last_advert": c.last_advert,
                "last_modified": c.last_modified,
                "out_path": c.out_path,
            }
            for c in contacts_list.contacts
        ]
    }

    logger.info(f"Returned {len(contacts_list.contacts)} contacts for user {user_id} in mesh {server_id}")
    return web.json_response(contacts_dict)


async def get_mesh_stats(request: web.Request) -> web.Response:
    """Get statistics for a mesh.

    Returns:
        JSON response with mesh statistics
    """
    storage: AdvertStorage = request.app["storage"]
    server_id = request.match_info["server_id"]

    # Get all adverts for the server
    adverts = list(storage.list_server_adverts(discord_server_id=server_id))

    if not adverts:
        stats = {
            "server_id": server_id,
            "total_adverts": 0,
            "by_type": {"companion": 0, "repeater": 0, "room": 0},
            "unique_users": 0,
            "last_updated": 0,
        }
    else:
        # Calculate statistics
        by_type = {"companion": 0, "repeater": 0, "room": 0}
        unique_users = set()
        last_updated = 0

        for advert in adverts:
            unique_users.add(advert.discord_user_id)
            last_updated = max(last_updated, advert.updated_at)

            # Count by type
            if advert.radio_type == 1:
                by_type["companion"] += 1
            elif advert.radio_type == 2:
                by_type["repeater"] += 1
            elif advert.radio_type == 3:
                by_type["room"] += 1

        stats = {
            "server_id": server_id,
            "total_adverts": len(adverts),
            "by_type": by_type,
            "unique_users": len(unique_users),
            "last_updated": int(last_updated),
        }

    logger.info(f"Returned stats for mesh {server_id}: {stats['total_adverts']} adverts")
    return web.json_response(stats)


async def list_all_meshes(request: web.Request) -> web.Response:
    """List all meshes with their basic information.

    Returns:
        JSON response with list of all meshes
    """
    storage: AdvertStorage = request.app["storage"]

    # Get all meshes
    all_meshes = Mesh.objects.all()  # type: ignore[attr-defined]

    # Build response with contact counts
    meshes_list = []
    for mesh in all_meshes:
        # Get contact count for this mesh
        adverts = list(storage.list_server_adverts(discord_server_id=mesh.discord_server_id))

        meshes_list.append(
            {
                "server_id": mesh.discord_server_id,
                "name": mesh.name,
                "description": mesh.description,
                "icon_url": mesh.icon_url,
                "contact_count": len(list(adverts)),
                "created_at": int(mesh.created_at),
                "updated_at": int(mesh.updated_at),
            }
        )

    logger.info(f"Returned {len(meshes_list)} meshes")
    return web.json_response({"meshes": meshes_list})


async def get_mesh_info(request: web.Request) -> web.Response:
    """Get information about a mesh (Discord server).

    Returns:
        JSON response with mesh information including name, ID, and contact count
    """
    storage: AdvertStorage = request.app["storage"]
    server_id = request.match_info["server_id"]

    # Get mesh metadata
    mesh = Mesh.objects.get_or_none(discord_server_id=server_id)  # type: ignore[attr-defined]

    if not mesh:
        raise web.HTTPNotFound(reason=f"Mesh {server_id} not found")

    # Get all adverts to count them
    adverts = list(storage.list_server_adverts(discord_server_id=server_id))

    # Build response
    mesh_info = {
        "server_id": mesh.discord_server_id,
        "name": mesh.name,
        "description": mesh.description,
        "icon_url": mesh.icon_url,
        "contact_count": len(adverts),
        "created_at": int(mesh.created_at),
        "updated_at": int(mesh.updated_at),
    }

    logger.info(f"Returned info for mesh {server_id}: {mesh.name} with {len(adverts)} contacts")
    return web.json_response(mesh_info)


def setup_routes(app: web.Application) -> None:
    """Set up API routes.

    Args:
        app: The aiohttp application
    """
    # Discord invite redirect
    app.router.add_get("/invite", invite_redirect)

    # Health check
    app.router.add_get("/health", health_check)

    # API routes
    app.router.add_get("/api/v1/mesh", list_all_meshes)
    app.router.add_get("/api/v1/mesh/{server_id}", get_mesh_info)
    app.router.add_get("/api/v1/mesh/{server_id}/contacts", get_mesh_contacts)
    app.router.add_get("/api/v1/contact/{public_key}", get_contact_by_key)
    app.router.add_post("/api/v1/mesh/{server_id}/contacts/bulk", bulk_contacts)
    app.router.add_get("/api/v1/mesh/{server_id}/user/{user_id}/contacts", get_user_contacts)
    app.router.add_get("/api/v1/mesh/{server_id}/stats", get_mesh_stats)
