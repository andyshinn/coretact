"""Storage layer for managing adverts."""

from time import time
from typing import Optional

from coretact.meshcore.parser import AdvertParser
from coretact.models import Advert, Contact, ContactsList, Mesh


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
            radio_type=parsed.adv_type or 0,
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
        advert.radio_type = parsed.adv_type or 0
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
    ) -> Optional[Advert]:
        """Get an advert by public key and server.

        Args:
            public_key: 64-char hex public key
            discord_server_id: Discord guild ID

        Returns:
            Advert object if found, None otherwise
        """
        # Use datafiles get_or_none() which will return None if file doesn't exist
        # The discord_user_id will be loaded from the JSON file
        return Advert.objects.get_or_none(  # type: ignore[return-value]
            discord_server_id=discord_server_id,
            public_key=public_key,
        )

    @staticmethod
    def delete_advert(
        public_key: str,
        discord_server_id: str,
    ) -> bool:
        """Delete an advert by public key and server.

        Args:
            public_key: 64-char hex public key
            discord_server_id: Discord guild ID

        Returns:
            True if deleted, False if not found
        """
        advert = AdvertStorage.get_advert(public_key, discord_server_id)
        if advert and advert.datafile.exists: # type: ignore[attr-defined]
            # Delete the file using pathlib
            advert.datafile.path.unlink() # type: ignore[attr-defined]
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
        # Get all adverts for the server, then filter by user
        all_server_adverts = AdvertStorage.list_server_adverts(discord_server_id)
        user_adverts = [advert for advert in all_server_adverts if advert.discord_user_id == discord_user_id]
        return user_adverts

    @staticmethod
    def list_server_adverts(discord_server_id: str) -> list[Advert]:
        """List all adverts for a server.

        Args:
            discord_server_id: Discord guild ID

        Returns:
            List of Advert objects
        """
        from pathlib import Path
        from coretact.models import STORAGE_BASE_PATH

        # Path to server's adverts directory
        server_adverts_path = Path(STORAGE_BASE_PATH) / discord_server_id / "adverts"

        if not server_adverts_path.exists():
            return []

        adverts = []
        # Iterate through all .json files in the adverts directory
        for advert_file in server_adverts_path.glob("*.json"):
            # Extract public key from filename (without .json extension)
            public_key = advert_file.stem

            # Load the advert
            advert = AdvertStorage.get_advert(public_key, discord_server_id)
            if advert:
                adverts.append(advert)

        return adverts

    @staticmethod
    def find_advert_by_public_key(public_key: str) -> Optional[Advert]:
        """Find an advert by public key across all servers.

        Args:
            public_key: 64-char hex public key

        Returns:
            Advert object if found, None otherwise
        """
        from pathlib import Path
        from coretact.models import STORAGE_BASE_PATH

        public_key = public_key.lower()
        storage_path = Path(STORAGE_BASE_PATH)

        # Search through all server directories
        for server_dir in storage_path.iterdir():
            if not server_dir.is_dir():
                continue

            # Look for adverts subdirectory
            adverts_dir = server_dir / "adverts"
            if not adverts_dir.exists():
                continue

            # Check if this public key exists in this server
            advert_file = adverts_dir / f"{public_key}.json"
            if advert_file.exists():
                # Load and return the advert
                server_id = server_dir.name
                advert = AdvertStorage.get_advert(public_key, server_id)
                if advert:
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
            type=advert.radio_type,
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
            filtered = [advert for advert in filtered if advert.radio_type == type]

        if key_prefix is not None:
            filtered = [advert for advert in filtered if advert.public_key.startswith(key_prefix.lower())]

        if name is not None:
            name_lower = name.lower()
            filtered = [advert for advert in filtered if name_lower in advert.name.lower()]

        if user_id is not None:
            filtered = [advert for advert in filtered if advert.discord_user_id == user_id]

        return filtered


class MeshStorage:
    """Storage operations for mesh/server metadata."""

    @staticmethod
    def create_mesh(
        discord_server_id: str,
        name: str,
        description: str = "",
        icon_url: str = "",
    ) -> Mesh:
        """Create a new Mesh metadata object.

        Args:
            discord_server_id: Discord guild ID
            name: Discord server name
            description: Discord server description
            icon_url: Discord server icon URL

        Returns:
            Mesh object ready to be saved
        """

        return Mesh(
            discord_server_id=discord_server_id,
            name=name,
            description=description,
            icon_url=icon_url,
            created_at=time(),
            updated_at=time(),
        )

    @staticmethod
    def get_mesh(discord_server_id: str) -> Optional["Mesh"]:
        """Get mesh metadata for a server.

        Args:
            discord_server_id: Discord guild ID

        Returns:
            Mesh object if found, None otherwise
        """
        return Mesh.objects.get_or_none(discord_server_id=discord_server_id)  # type: ignore[attr-defined]

    @staticmethod
    def update_mesh(mesh: "Mesh", **kwargs) -> "Mesh":
        """Update an existing mesh with new data.

        Args:
            mesh: Existing Mesh object
            **kwargs: Fields to update (name, description, icon_url)

        Returns:
            Updated Mesh object
        """
        if "name" in kwargs:
            mesh.name = kwargs["name"]
        if "description" in kwargs:
            mesh.description = kwargs["description"]
        if "icon_url" in kwargs:
            mesh.icon_url = kwargs["icon_url"]

        mesh.updated_at = time()
        return mesh

    @staticmethod
    def delete_mesh(discord_server_id: str) -> bool:
        """Delete mesh metadata.

        Args:
            discord_server_id: Discord guild ID

        Returns:
            True if deleted, False if not found
        """
        mesh = MeshStorage.get_mesh(discord_server_id)
        if mesh and hasattr(mesh, "datafile") and mesh.datafile.exists:  # type: ignore
            # Delete the file using pathlib
            mesh.datafile.path.unlink()  # type: ignore
            return True
        return False

    @staticmethod
    def list_all_meshes() -> list["Mesh"]:
        """List all mesh metadata entries.

        Returns:
            List of Mesh objects
        """
        from coretact.models import Mesh

        all_meshes = Mesh.objects.all()
        return list(all_meshes)
