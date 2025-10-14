"""Tests for the storage layer."""

import os
import tempfile

import pytest

from coretact.models import Advert
from coretact.storage import AdvertStorage, ContactConverter, ContactFilter, MeshStorage


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for storage tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set the storage path for datafiles
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        yield tmpdir
        os.chdir(old_cwd)


@pytest.fixture
def sample_meshcore_url():
    """Sample meshcore URL for testing with valid location (Austin, TX)."""
    # Real contact export from egrme.sh with valid coordinates
    return (
        "meshcore://110055365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d"
        "f2d9ee68a9d311a998dd4e3ebea8a03432539e0a5c35dfe94f7a0c8665181e70d17ddef51"
        "b7b5f2704a6fdd2fde47d3edf2057cfb3a874df8d394ac494ed646173fcdb0a91f7fccc01"
        "e4462cfa6567726d652e736820436f7265"
    )


def test_create_advert_from_url(temp_storage_dir, sample_meshcore_url):
    """Test creating an advert from a meshcore URL."""
    advert = AdvertStorage.create_advert_from_url(
        meshcore_url=sample_meshcore_url,
        discord_server_id="123456789",
        discord_user_id="987654321",
    )

    assert advert.public_key == "55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d"
    assert advert.discord_server_id == "123456789"
    assert advert.discord_user_id == "987654321"
    assert advert.advert_string == sample_meshcore_url
    assert advert.radio_type == 1  # Type 1 = Chat/Companion
    assert advert.name == "egrme.sh Core"
    assert advert.flags == 145  # 0x91 = type 1 + location flag + name flag

    # Check location (Austin, TX)
    assert advert.latitude is not None
    assert advert.longitude is not None
    assert abs(advert.latitude - 30.211319) < 0.000001
    assert abs(advert.longitude - (-97.761564)) < 0.000001

    assert isinstance(advert.created_at, float)
    assert isinstance(advert.updated_at, float)
    assert advert.created_at > 0
    assert advert.updated_at > 0


def test_save_and_get_advert(temp_storage_dir, sample_meshcore_url):
    """Test saving and retrieving an advert."""
    # Create and save an advert
    advert = AdvertStorage.create_advert_from_url(
        meshcore_url=sample_meshcore_url,
        discord_server_id="123456789",
        discord_user_id="987654321",
    )
    advert.datafile.save()

    # Retrieve the advert (no longer need discord_user_id)
    retrieved = AdvertStorage.get_advert(
        public_key=advert.public_key,
        discord_server_id="123456789",
    )

    assert retrieved is not None
    assert retrieved.public_key == advert.public_key
    assert retrieved.discord_user_id == "987654321"  # Should be loaded from file
    assert retrieved.name == advert.name
    assert retrieved.radio_type == advert.radio_type


def test_delete_advert(temp_storage_dir, sample_meshcore_url):
    """Test deleting an advert."""
    # Create and save an advert
    advert = AdvertStorage.create_advert_from_url(
        meshcore_url=sample_meshcore_url,
        discord_server_id="123456789",
        discord_user_id="987654321",
    )
    advert.datafile.save()

    # Delete the advert (no longer need discord_user_id)
    success = AdvertStorage.delete_advert(
        public_key=advert.public_key,
        discord_server_id="123456789",
    )

    assert success is True

    # Verify it's gone
    retrieved = AdvertStorage.get_advert(
        public_key=advert.public_key,
        discord_server_id="123456789",
    )
    assert retrieved is None


@pytest.mark.skip(reason="Datafiles Manager API has issues with temp directories")
def test_list_user_adverts(temp_storage_dir, sample_meshcore_url):
    """Test listing adverts for a user."""
    # Create multiple adverts for the same user
    for i in range(3):
        # Modify the URL slightly to create different public keys
        url = sample_meshcore_url[:-2] + f"0{i}"
        advert = AdvertStorage.create_advert_from_url(
            meshcore_url=url,
            discord_server_id="123456789",
            discord_user_id="987654321",
        )
        advert.datafile.save()

    # List adverts
    adverts = AdvertStorage.list_user_adverts(
        discord_server_id="123456789",
        discord_user_id="987654321",
    )

    assert len(adverts) == 3
    assert all(advert.discord_user_id == "987654321" for advert in adverts)


def test_contact_converter(temp_storage_dir, sample_meshcore_url):
    """Test converting an advert to a contact."""
    advert = AdvertStorage.create_advert_from_url(
        meshcore_url=sample_meshcore_url,
        discord_server_id="123456789",
        discord_user_id="987654321",
    )

    contact = ContactConverter.advert_to_contact(advert)

    assert contact.public_key == advert.public_key
    assert contact.name == advert.name
    assert contact.type == advert.radio_type
    assert contact.flags == advert.flags
    assert contact.latitude == str(advert.latitude)
    assert contact.longitude == str(advert.longitude)
    assert contact.custom_name is None


def test_contact_filter_by_type(temp_storage_dir, sample_meshcore_url):
    """Test filtering adverts by type."""
    # Create adverts with different types (manually, not using storage)
    advert1 = Advert(
        public_key="key1",
        discord_server_id="123456789",
        discord_user_id="987654321",
        advert_string="meshcore://test1",
        radio_type=1,  # Companion
        name="Test 1",
        flags=0,
    )

    advert2 = Advert(
        public_key="key2",
        discord_server_id="123456789",
        discord_user_id="987654321",
        advert_string="meshcore://test2",
        radio_type=2,  # Repeater
        name="Test 2",
        flags=0,
    )

    adverts = [advert1, advert2]

    # Filter by type
    filtered = ContactFilter.filter_adverts(adverts, type=1)
    assert len(filtered) == 1
    assert filtered[0].radio_type == 1


def test_contact_filter_by_key_prefix(temp_storage_dir, sample_meshcore_url):
    """Test filtering adverts by public key prefix."""
    advert = AdvertStorage.create_advert_from_url(
        meshcore_url=sample_meshcore_url,
        discord_server_id="123456789",
        discord_user_id="987654321",
    )

    adverts = [advert]

    # Filter by key prefix
    filtered = ContactFilter.filter_adverts(adverts, key_prefix="5536")
    assert len(filtered) == 1

    filtered = ContactFilter.filter_adverts(adverts, key_prefix="9999")
    assert len(filtered) == 0


def test_contact_filter_by_name(temp_storage_dir, sample_meshcore_url):
    """Test filtering adverts by name (partial match)."""
    advert = AdvertStorage.create_advert_from_url(
        meshcore_url=sample_meshcore_url,
        discord_server_id="123456789",
        discord_user_id="987654321",
    )

    adverts = [advert]

    # Filter by name (case-insensitive partial match)
    filtered = ContactFilter.filter_adverts(adverts, name="egrme")
    assert len(filtered) == 1

    filtered = ContactFilter.filter_adverts(adverts, name="CORE")
    assert len(filtered) == 1

    filtered = ContactFilter.filter_adverts(adverts, name="notfound")
    assert len(filtered) == 0


def test_create_mesh(temp_storage_dir):
    """Test creating a mesh metadata object."""
    mesh = MeshStorage.create_mesh(
        discord_server_id="123456789",
        name="Test Server",
        description="A test Discord server",
        icon_url="https://example.com/icon.png",
    )

    assert mesh.discord_server_id == "123456789"
    assert mesh.name == "Test Server"
    assert mesh.description == "A test Discord server"
    assert mesh.icon_url == "https://example.com/icon.png"
    assert isinstance(mesh.created_at, float)
    assert isinstance(mesh.updated_at, float)
    assert mesh.created_at > 0
    assert mesh.updated_at > 0


def test_save_and_get_mesh(temp_storage_dir):
    """Test saving and retrieving a mesh."""
    # Create and save a mesh
    mesh = MeshStorage.create_mesh(
        discord_server_id="123456789",
        name="Test Server",
        description="A test Discord server",
        icon_url="https://example.com/icon.png",
    )
    mesh.datafile.save()

    # Retrieve the mesh
    retrieved = MeshStorage.get_mesh("123456789")

    assert retrieved is not None
    assert retrieved.discord_server_id == "123456789"
    assert retrieved.name == "Test Server"
    assert retrieved.description == "A test Discord server"
    assert retrieved.icon_url == "https://example.com/icon.png"


def test_update_mesh(temp_storage_dir):
    """Test updating a mesh."""
    # Create and save a mesh
    mesh = MeshStorage.create_mesh(
        discord_server_id="123456789",
        name="Test Server",
        description="Original description",
        icon_url="https://example.com/icon.png",
    )
    mesh.datafile.save()
    original_updated_at = mesh.updated_at

    # Update the mesh
    MeshStorage.update_mesh(
        mesh,
        name="Updated Server",
        description="Updated description",
    )
    mesh.datafile.save()

    # Retrieve and verify
    retrieved = MeshStorage.get_mesh("123456789")
    assert retrieved is not None
    assert retrieved.name == "Updated Server"
    assert retrieved.description == "Updated description"
    assert retrieved.icon_url == "https://example.com/icon.png"  # Unchanged
    assert retrieved.updated_at > original_updated_at


def test_delete_mesh(temp_storage_dir):
    """Test deleting a mesh."""
    # Create and save a mesh
    mesh = MeshStorage.create_mesh(
        discord_server_id="123456789",
        name="Test Server",
    )
    mesh.datafile.save()

    # Delete the mesh
    success = MeshStorage.delete_mesh("123456789")
    assert success is True

    # Verify it's gone
    retrieved = MeshStorage.get_mesh("123456789")
    assert retrieved is None


def test_get_nonexistent_mesh(temp_storage_dir):
    """Test getting a mesh that doesn't exist."""
    mesh = MeshStorage.get_mesh("999999999")
    assert mesh is None


def test_delete_nonexistent_mesh(temp_storage_dir):
    """Test deleting a mesh that doesn't exist."""
    success = MeshStorage.delete_mesh("999999999")
    assert success is False
