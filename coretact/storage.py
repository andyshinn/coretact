"""Storage layer for managing adverts."""

from time import time
from typing import Optional

from coretact.meshcore.parser import AdvertParser
from coretact.models import Advert, Contact, ContactsList


class AdvertStorage:
    """Storage operations for adverts."""

    @staticmethod
    def create_advert_from_url(
        meshcore_url: str,
        discord_server_id: str,
        discord_user_id: str,
    ) -> Advert:
        """Parse a meshcore URL and create an Advert object.

        Args:
            meshcore_url: The meshcore:// URL to parse
            discord_server_id: Discord guild ID
            discord_user_id: Discord user ID

        Returns:
            Advert object ready to be saved

        Raises:
            ValueError: If the URL is invalid or cannot be parsed
        """
        parsed = AdvertParser.parse(meshcore_url)

        return Advert(
            discord_server_id=discord_server_id,
            discord_user_id=discord_user_id,
            public_key=parsed.public_key,
            advert_string=meshcore_url,
            type=parsed.type,
            name=parsed.name,
            flags=parsed.flags,
            latitude=parsed.latitude,
            longitude=parsed.longitude,
            out_path=parsed.out_path,
            created_at=time(),
            updated_at=time(),
        )

    @staticmethod
    def update_advert(
        advert: Advert,
        meshcore_url: str,
    ) -> Advert:
        """Update an existing advert with new data from a meshcore URL.

        Args:
            advert: Existing Advert object
            meshcore_url: New meshcore:// URL to parse

        Returns:
            Updated Advert object

        Raises:
            ValueError: If the URL is invalid or cannot be parsed
        """
        parsed = AdvertParser.parse(meshcore_url)

        # Update fields from parsed data
        advert.advert_string = meshcore_url
        advert.type = parsed.type
        advert.name = parsed.name
        advert.flags = parsed.flags
        advert.latitude = parsed.latitude
        advert.longitude = parsed.longitude
        advert.out_path = parsed.out_path
        advert.updated_at = time()

        return advert

    @staticmethod
    def get_advert(
        public_key: str,
        discord_server_id: str,
        discord_user_id: str,
    ) -> Optional[Advert]:
        """Get an advert by public key, server, and user.

        Args:
            public_key: 64-char hex public key
            discord_server_id: Discord guild ID
            discord_user_id: Discord user ID

        Returns:
            Advert object if found, None otherwise
        """
        try:
            advert = Advert(
                discord_server_id=discord_server_id,
                discord_user_id=discord_user_id,
                public_key=public_key,
                advert_string="",
                type=0,
                name="",
                flags=0,
            )
            # Check if file exists before trying to load
            if not advert.datafile.path.exists():
                return None
            # Try to load from disk
            advert.datafile.load()
            return advert
        except (FileNotFoundError, ValueError):
            return None

    @staticmethod
    def delete_advert(
        public_key: str,
        discord_server_id: str,
        discord_user_id: str,
    ) -> bool:
        """Delete an advert.

        Args:
            public_key: 64-char hex public key
            discord_server_id: Discord guild ID
            discord_user_id: Discord user ID

        Returns:
            True if deleted, False if not found
        """
        advert = AdvertStorage.get_advert(public_key, discord_server_id, discord_user_id)
        if advert and advert.datafile.exists:
            # Delete the file using pathlib
            advert.datafile.path.unlink()
            return True
        return False

    @staticmethod
    def list_user_adverts(
        discord_server_id: str,
        discord_user_id: str,
    ) -> list[Advert]:
        """List all adverts for a specific user in a server.

        Args:
            discord_server_id: Discord guild ID
            discord_user_id: Discord user ID

        Returns:
            List of Advert objects
        """
        # Query using datafiles Manager API
        # This will find all adverts matching the server and user
        all_adverts = Advert.objects.filter(discord_server_id=discord_server_id, discord_user_id=discord_user_id)
        return list(all_adverts)

    @staticmethod
    def list_server_adverts(discord_server_id: str) -> list[Advert]:
        """List all adverts for a server.

        Args:
            discord_server_id: Discord guild ID

        Returns:
            List of Advert objects
        """
        all_adverts = Advert.objects.all()
        server_adverts = [advert for advert in all_adverts if advert.discord_server_id == discord_server_id]
        return server_adverts

    @staticmethod
    def find_advert_by_public_key(public_key: str) -> Optional[Advert]:
        """Find an advert by public key across all servers.

        Args:
            public_key: 64-char hex public key

        Returns:
            Advert object if found, None otherwise
        """
        public_key = public_key.lower()
        all_adverts = Advert.objects.all()
        for advert in all_adverts:
            if advert.public_key == public_key:
                return advert
        return None


class ContactConverter:
    """Convert between Advert and Contact models."""

    @staticmethod
    def advert_to_contact(advert: Advert) -> Contact:
        """Convert Advert model to Contact model for API responses.

        Args:
            advert: Advert object from storage

        Returns:
            Contact object for API response
        """
        return Contact(
            type=advert.type,
            name=advert.name,
            custom_name=None,  # Not implemented yet
            public_key=advert.public_key,
            flags=advert.flags,
            latitude=str(advert.latitude),
            longitude=str(advert.longitude),
            last_advert=int(advert.created_at),
            last_modified=int(advert.updated_at),
            out_path=advert.out_path,
        )

    @staticmethod
    def adverts_to_contacts_list(adverts: list[Advert]) -> ContactsList:
        """Convert multiple adverts to ContactsList.

        Args:
            adverts: List of Advert objects

        Returns:
            ContactsList object for API response
        """
        contacts = [ContactConverter.advert_to_contact(advert) for advert in adverts]
        return ContactsList(contacts=contacts)


class ContactFilter:
    """Filter adverts by various criteria."""

    @staticmethod
    def filter_adverts(
        adverts: list[Advert],
        type: Optional[int] = None,
        key_prefix: Optional[str] = None,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> list[Advert]:
        """Apply filters to a list of adverts.

        Args:
            adverts: List of Advert objects to filter
            type: Filter by device type (1, 2, or 3)
            key_prefix: Filter by public key prefix
            name: Filter by name (partial match, case-insensitive)
            user_id: Filter by Discord user ID

        Returns:
            Filtered list of Advert objects
        """
        filtered = adverts

        if type is not None:
            filtered = [advert for advert in filtered if advert.type == type]

        if key_prefix is not None:
            filtered = [advert for advert in filtered if advert.public_key.startswith(key_prefix.lower())]

        if name is not None:
            name_lower = name.lower()
            filtered = [advert for advert in filtered if name_lower in advert.name.lower()]

        if user_id is not None:
            filtered = [advert for advert in filtered if advert.discord_user_id == user_id]

        return filtered
