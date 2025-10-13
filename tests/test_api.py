"""Tests for the Web API."""

import json
from time import time

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from coretact.api.server import create_app
from coretact.models import Advert
from coretact.storage import AdvertStorage


class TestWebAPI(AioHTTPTestCase):
    """Test cases for the Web API."""

    async def get_application(self):
        """Create the test application."""
        return create_app()

    async def test_health_check(self):
        """Test the health check endpoint."""
        resp = await self.client.get("/health")
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    async def test_mesh_contacts_empty(self):
        """Test getting contacts for an empty mesh."""
        resp = await self.client.get("/api/v1/mesh/test_server/contacts")
        assert resp.status == 200

        data = await resp.json()
        assert "contacts" in data
        assert len(data["contacts"]) == 0

    async def test_mesh_contacts_with_data(self):
        """Test getting contacts with data."""
        # Create test adverts
        storage = self.app["storage"]

        advert1 = Advert(
            discord_server_id="test_server",
            discord_user_id="user1",
            public_key="a" * 64,
            advert_string="meshcore://test1",
            type=1,
            name="Test Device 1",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert1.datafile.save()

        advert2 = Advert(
            discord_server_id="test_server",
            discord_user_id="user2",
            public_key="b" * 64,
            advert_string="meshcore://test2",
            type=2,
            name="Test Device 2",
            flags=0,
            latitude=1.0,
            longitude=2.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert2.datafile.save()

        try:
            # Get all contacts
            resp = await self.client.get("/api/v1/mesh/test_server/contacts")
            assert resp.status == 200

            data = await resp.json()
            assert len(data["contacts"]) == 2

            # Test filtering by type
            resp = await self.client.get("/api/v1/mesh/test_server/contacts?type=1")
            assert resp.status == 200

            data = await resp.json()
            assert len(data["contacts"]) == 1
            assert data["contacts"][0]["type"] == 1

            # Test filtering by key prefix
            resp = await self.client.get("/api/v1/mesh/test_server/contacts?key_prefix=a")
            assert resp.status == 200

            data = await resp.json()
            assert len(data["contacts"]) == 1
            assert data["contacts"][0]["public_key"] == "a" * 64

            # Test filtering by name
            resp = await self.client.get("/api/v1/mesh/test_server/contacts?name=Device 1")
            assert resp.status == 200

            data = await resp.json()
            assert len(data["contacts"]) == 1
            assert "Device 1" in data["contacts"][0]["name"]

        finally:
            # Clean up
            advert1.datafile.path.unlink(missing_ok=True)
            advert2.datafile.path.unlink(missing_ok=True)

    async def test_contact_by_key(self):
        """Test getting a single contact by public key."""
        # Create test advert
        advert = Advert(
            discord_server_id="test_server",
            discord_user_id="user1",
            public_key="c" * 64,
            advert_string="meshcore://test3",
            type=1,
            name="Test Device 3",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert.datafile.save()

        try:
            # Get contact by key
            resp = await self.client.get(f"/api/v1/contact/{'c' * 64}")
            assert resp.status == 200

            data = await resp.json()
            assert data["public_key"] == "c" * 64
            assert data["name"] == "Test Device 3"
            assert "advert_string" in data
            assert "discord_server_id" in data

            # Test not found
            resp = await self.client.get(f"/api/v1/contact/{'d' * 64}")
            assert resp.status == 404

        finally:
            # Clean up
            advert.datafile.path.unlink(missing_ok=True)

    async def test_bulk_contacts(self):
        """Test bulk contacts endpoint."""
        # Create test adverts
        advert1 = Advert(
            discord_server_id="test_server",
            discord_user_id="user1",
            public_key="e" * 64,
            advert_string="meshcore://test4",
            type=1,
            name="Test Device 4",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert1.datafile.save()

        advert2 = Advert(
            discord_server_id="test_server",
            discord_user_id="user2",
            public_key="f" * 64,
            advert_string="meshcore://test5",
            type=2,
            name="Test Device 5",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert2.datafile.save()

        try:
            # Request specific contacts
            payload = {
                "public_keys": ["e" * 64, "f" * 64],
            }
            resp = await self.client.post(
                "/api/v1/mesh/test_server/contacts/bulk",
                json=payload,
            )
            assert resp.status == 200

            data = await resp.json()
            assert len(data["contacts"]) == 2

            # Test with metadata
            payload = {
                "public_keys": ["e" * 64],
                "include_metadata": True,
            }
            resp = await self.client.post(
                "/api/v1/mesh/test_server/contacts/bulk",
                json=payload,
            )
            assert resp.status == 200

            data = await resp.json()
            assert len(data["contacts"]) == 1
            assert "discord_server_id" in data["contacts"][0]

            # Test with invalid payload
            resp = await self.client.post(
                "/api/v1/mesh/test_server/contacts/bulk",
                json={},
            )
            assert resp.status == 400

        finally:
            # Clean up
            advert1.datafile.path.unlink(missing_ok=True)
            advert2.datafile.path.unlink(missing_ok=True)

    async def test_user_contacts(self):
        """Test getting user contacts endpoint."""
        # Create test adverts
        advert1 = Advert(
            discord_server_id="test_server",
            discord_user_id="user1",
            public_key="g" * 64,
            advert_string="meshcore://test6",
            type=1,
            name="Test Device 6",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert1.datafile.save()

        advert2 = Advert(
            discord_server_id="test_server",
            discord_user_id="user1",
            public_key="h" * 64,
            advert_string="meshcore://test7",
            type=2,
            name="Test Device 7",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert2.datafile.save()

        try:
            # Get user contacts
            resp = await self.client.get("/api/v1/mesh/test_server/user/user1/contacts")
            assert resp.status == 200

            data = await resp.json()
            assert len(data["contacts"]) == 2

            # Test non-existent user
            resp = await self.client.get("/api/v1/mesh/test_server/user/user999/contacts")
            assert resp.status == 200

            data = await resp.json()
            assert len(data["contacts"]) == 0

        finally:
            # Clean up
            advert1.datafile.path.unlink(missing_ok=True)
            advert2.datafile.path.unlink(missing_ok=True)

    async def test_mesh_stats(self):
        """Test mesh stats endpoint."""
        # Create test adverts
        advert1 = Advert(
            discord_server_id="test_server",
            discord_user_id="user1",
            public_key="i" * 64,
            advert_string="meshcore://test8",
            type=1,
            name="Test Device 8",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert1.datafile.save()

        advert2 = Advert(
            discord_server_id="test_server",
            discord_user_id="user2",
            public_key="j" * 64,
            advert_string="meshcore://test9",
            type=2,
            name="Test Device 9",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert2.datafile.save()

        try:
            # Get stats
            resp = await self.client.get("/api/v1/mesh/test_server/stats")
            assert resp.status == 200

            data = await resp.json()
            assert data["server_id"] == "test_server"
            assert data["total_adverts"] == 2
            assert data["unique_users"] == 2
            assert data["by_type"]["companion"] == 1
            assert data["by_type"]["repeater"] == 1
            assert data["last_updated"] > 0

        finally:
            # Clean up
            advert1.datafile.path.unlink(missing_ok=True)
            advert2.datafile.path.unlink(missing_ok=True)

    async def test_cors_headers(self):
        """Test CORS headers are present."""
        resp = await self.client.get("/health")
        assert resp.status == 200

        assert "Access-Control-Allow-Origin" in resp.headers
        assert resp.headers["Access-Control-Allow-Origin"] == "*"
