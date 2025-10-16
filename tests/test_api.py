"""Tests for the Web API."""

from time import time

from aiohttp.test_utils import AioHTTPTestCase

from coretact.api.server import create_app
from coretact.models import Advert, Mesh


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

        advert1 = Advert(
            discord_server_id="test_server",
            discord_user_id="user1",
            public_key="a" * 64,
            advert_string="meshcore://test1",
            radio_type=1,
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
            radio_type=2,
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
            radio_type=1,
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
            radio_type=1,
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
            radio_type=2,
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
            radio_type=1,
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
            radio_type=2,
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
            radio_type=1,
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
            radio_type=2,
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

    async def test_list_all_meshes(self):
        """Test listing all meshes endpoint."""
        # Create multiple meshes with contacts
        mesh1 = Mesh(
            discord_server_id="test_server_1",
            name="Test Server 1",
            description="First test server",
            icon_url="https://example.com/icon1.png",
            created_at=time(),
            updated_at=time(),
        )
        mesh1.datafile.save()

        mesh2 = Mesh(
            discord_server_id="test_server_2",
            name="Test Server 2",
            description="Second test server",
            icon_url="https://example.com/icon2.png",
            created_at=time(),
            updated_at=time(),
        )
        mesh2.datafile.save()

        # Add contacts to mesh1
        advert1 = Advert(
            discord_server_id="test_server_1",
            discord_user_id="user1",
            public_key="m" * 64,
            advert_string="meshcore://test12",
            radio_type=1,
            name="Test Device 12",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert1.datafile.save()

        advert2 = Advert(
            discord_server_id="test_server_1",
            discord_user_id="user2",
            public_key="n" * 64,
            advert_string="meshcore://test13",
            radio_type=2,
            name="Test Device 13",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert2.datafile.save()

        # Add contact to mesh2
        advert3 = Advert(
            discord_server_id="test_server_2",
            discord_user_id="user3",
            public_key="o" * 64,
            advert_string="meshcore://test14",
            radio_type=3,
            name="Test Device 14",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert3.datafile.save()

        try:
            # List all meshes
            resp = await self.client.get("/api/v1/mesh")
            assert resp.status == 200

            data = await resp.json()
            assert "meshes" in data
            assert len(data["meshes"]) == 2

            # Find mesh1 and mesh2 in response
            mesh1_data = next((m for m in data["meshes"] if m["server_id"] == "test_server_1"), None)
            mesh2_data = next((m for m in data["meshes"] if m["server_id"] == "test_server_2"), None)

            assert mesh1_data is not None
            assert mesh1_data["name"] == "Test Server 1"
            assert mesh1_data["description"] == "First test server"
            assert mesh1_data["contact_count"] == 2

            assert mesh2_data is not None
            assert mesh2_data["name"] == "Test Server 2"
            assert mesh2_data["description"] == "Second test server"
            assert mesh2_data["contact_count"] == 1

        finally:
            # Clean up
            mesh1.datafile.path.unlink(missing_ok=True)
            mesh2.datafile.path.unlink(missing_ok=True)
            advert1.datafile.path.unlink(missing_ok=True)
            advert2.datafile.path.unlink(missing_ok=True)
            advert3.datafile.path.unlink(missing_ok=True)

    async def test_mesh_info(self):
        """Test mesh info endpoint."""
        # Create mesh metadata
        mesh = Mesh(
            discord_server_id="test_server_info",
            name="Test Server",
            description="A test server",
            icon_url="https://example.com/icon.png",
            created_at=time(),
            updated_at=time(),
        )
        mesh.datafile.save()

        # Create test adverts for this mesh
        advert1 = Advert(
            discord_server_id="test_server_info",
            discord_user_id="user1",
            public_key="k" * 64,
            advert_string="meshcore://test10",
            radio_type=1,
            name="Test Device 10",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert1.datafile.save()

        advert2 = Advert(
            discord_server_id="test_server_info",
            discord_user_id="user2",
            public_key="l" * 64,
            advert_string="meshcore://test11",
            radio_type=2,
            name="Test Device 11",
            flags=0,
            latitude=0.0,
            longitude=0.0,
            out_path="",
            created_at=time(),
            updated_at=time(),
        )
        advert2.datafile.save()

        try:
            # Get mesh info
            resp = await self.client.get("/api/v1/mesh/test_server_info")
            assert resp.status == 200

            data = await resp.json()
            assert data["server_id"] == "test_server_info"
            assert data["name"] == "Test Server"
            assert data["description"] == "A test server"
            assert data["icon_url"] == "https://example.com/icon.png"
            assert data["contact_count"] == 2
            assert "created_at" in data
            assert "updated_at" in data

            # Test non-existent mesh
            resp = await self.client.get("/api/v1/mesh/nonexistent_server")
            assert resp.status == 404

        finally:
            # Clean up
            mesh.datafile.path.unlink(missing_ok=True)
            advert1.datafile.path.unlink(missing_ok=True)
            advert2.datafile.path.unlink(missing_ok=True)

    async def test_cors_headers(self):
        """Test CORS headers are present."""
        resp = await self.client.get("/health")
        assert resp.status == 200

        assert "Access-Control-Allow-Origin" in resp.headers
        assert resp.headers["Access-Control-Allow-Origin"] == "*"

    async def test_decode_binary_advert(self):
        """Test decoding a binary advertisement format."""
        # Use the real contact export from the parser tests
        advert_url = (
            "meshcore://110055365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d6608"
            "7df2d9ee68a9d311a998dd4e3ebea8a03432539e0a5c35dfe94f7a0c8665181e70d17dde"
            "f51b7b5f2704a6fdd2fde47d3edf2057cfb3a874df8d394ac494ed646173fcdb0a91f7fc"
            "cc01e4462cfa6567726d652e736820436f7265"
        )

        payload = {"advert_url": advert_url}

        resp = await self.client.post("/api/v1/decode", json=payload)
        assert resp.status == 200

        data = await resp.json()

        # Verify basic fields
        assert data["format_type"] == "advertisement"
        assert data["public_key"] == "55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d"
        assert data["name"] == "egrme.sh Core"
        assert data["adv_type"] == 1
        assert data["type_name"] == "Chat"

        # Verify binary format specific fields
        assert "timestamp" in data
        assert data["timestamp"] > 0
        assert "signature" in data
        assert len(data["signature"]) == 128  # 64 bytes as hex
        assert "signature_valid" in data
        assert data["signature_valid"] is True
        assert "flags" in data

        # Verify location data
        assert "latitude" in data
        assert "longitude" in data
        assert abs(data["latitude"] - 30.211319) < 0.000001
        assert abs(data["longitude"] - (-97.761564)) < 0.000001

    async def test_decode_qr_contact(self):
        """Test decoding a QR code contact format."""
        advert_url = (
            "meshcore://contact/add?name=egrme.sh+Core&"
            "public_key=55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d&"
            "type=1"
        )

        payload = {"advert_url": advert_url}

        resp = await self.client.post("/api/v1/decode", json=payload)
        assert resp.status == 200

        data = await resp.json()

        # Verify basic fields
        assert data["format_type"] == "qr_contact"
        assert data["public_key"] == "55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d"
        assert data["name"] == "egrme.sh Core"
        assert data["adv_type"] == 1
        assert data["type_name"] == "Chat"

        # QR format should not have these fields
        assert "timestamp" not in data
        assert "signature" not in data
        assert "signature_valid" not in data
        assert "flags" not in data
        assert "latitude" not in data
        assert "longitude" not in data

    async def test_decode_missing_advert_url(self):
        """Test decode with missing advert_url field."""
        payload = {}

        resp = await self.client.post("/api/v1/decode", json=payload)
        assert resp.status == 400

        text = await resp.text()
        assert "advert_url" in text

    async def test_decode_invalid_advert_url(self):
        """Test decode with invalid advertisement URL."""
        payload = {"advert_url": "invalid://not-a-meshcore-url"}

        resp = await self.client.post("/api/v1/decode", json=payload)
        assert resp.status == 400

        text = await resp.text()
        assert "parse" in text.lower()

    async def test_decode_malformed_json(self):
        """Test decode with malformed JSON."""
        resp = await self.client.post(
            "/api/v1/decode",
            data="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    async def test_decode_non_string_advert_url(self):
        """Test decode with non-string advert_url."""
        payload = {"advert_url": 12345}

        resp = await self.client.post("/api/v1/decode", json=payload)
        assert resp.status == 400

        text = await resp.text()
        assert "string" in text.lower()

    async def test_decode_qr_with_url_encoding(self):
        """Test decoding QR format with different URL encoding styles."""
        # Test with + for spaces
        advert_url1 = (
            "meshcore://contact/add?name=Test+Device&"
            "public_key=1111111111111111111111111111111111111111111111111111111111111111&"
            "type=2"
        )

        payload = {"advert_url": advert_url1}
        resp = await self.client.post("/api/v1/decode", json=payload)
        assert resp.status == 200

        data = await resp.json()
        assert data["name"] == "Test Device"
        assert data["adv_type"] == 2
        assert data["type_name"] == "Repeater"

        # Test with %20 for spaces
        advert_url2 = (
            "meshcore://contact/add?name=Test%20Device&"
            "public_key=2222222222222222222222222222222222222222222222222222222222222222&"
            "type=3"
        )

        payload = {"advert_url": advert_url2}
        resp = await self.client.post("/api/v1/decode", json=payload)
        assert resp.status == 200

        data = await resp.json()
        assert data["name"] == "Test Device"
        assert data["adv_type"] == 3
        assert data["type_name"] == "Room"
