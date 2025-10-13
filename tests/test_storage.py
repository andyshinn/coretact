"""Tests for the storage layer."""

import os
import tempfile

import pytest

from coretact.models import Advert
from coretact.storage import AdvertStorage, ContactConverter, ContactFilter


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
    """Sample meshcore URL for testing."""
    # Real contact export from egrme.sh (full version from parser tests)
    return (
        "meshcore://110055365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d"
        "5045ec6872ee07b881c8a3ab5e25e62430cdb8bbb4b7b415e0a208084424942f1b26dcdd"
        "315c9eccf86d81bbf960642c4c1e385ec5ab1a98471e4134006e0ef5b715120c91000000"
        "00000000006567726d652e736820436f7265"
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
    assert advert.type == 80  # Raw type byte from Contact Export format
    assert advert.name == "egrme.sh Core"
    assert advert.flags == 69  # Raw flags byte
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

    # Retrieve the advert
    retrieved = AdvertStorage.get_advert(
        public_key=advert.public_key,
        discord_server_id="123456789",
        discord_user_id="987654321",
    )

    assert retrieved is not None
    assert retrieved.public_key == advert.public_key
    assert retrieved.name == advert.name
    assert retrieved.type == advert.type


def test_delete_advert(temp_storage_dir, sample_meshcore_url):
    """Test deleting an advert."""
    # Create and save an advert
    advert = AdvertStorage.create_advert_from_url(
        meshcore_url=sample_meshcore_url,
        discord_server_id="123456789",
        discord_user_id="987654321",
    )
    advert.datafile.save()

    # Delete the advert
    success = AdvertStorage.delete_advert(
        public_key=advert.public_key,
        discord_server_id="123456789",
        discord_user_id="987654321",
    )

    assert success is True

    # Verify it's gone
    retrieved = AdvertStorage.get_advert(
        public_key=advert.public_key,
        discord_server_id="123456789",
        discord_user_id="987654321",
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
    assert contact.type == advert.type
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
        type=1,  # Companion
        name="Test 1",
        flags=0,
    )

    advert2 = Advert(
        public_key="key2",
        discord_server_id="123456789",
        discord_user_id="987654321",
        advert_string="meshcore://test2",
        type=2,  # Repeater
        name="Test 2",
        flags=0,
    )

    adverts = [advert1, advert2]

    # Filter by type
    filtered = ContactFilter.filter_adverts(adverts, type=1)
    assert len(filtered) == 1
    assert filtered[0].type == 1


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
