"""Coretact command group cog for managing meshcore contacts."""

import io
import json
from typing import Literal, Optional

from discord import Embed, File, Interaction, Member, User, app_commands
from discord.ext import commands
from discord.utils import get

from coretact.log import logger
from coretact.models import Marks
from coretact.storage import AdvertStorage, ContactConverter, ContactFilter

# Role name constant
CORETACT_ADMIN_ROLE = "Coretact Admin"


def is_coretact_admin(interaction: Interaction) -> bool:
    """Check if user has the Coretact Admin role.

    Args:
        interaction: Discord interaction

    Returns:
        True if user has Coretact Admin role, False otherwise
    """
    if not interaction.guild:
        return False

    # interaction.user should be a Member in guild context, but check to be safe
    if not hasattr(interaction.user, "roles"):
        return False

    coretact_admin_role = get(interaction.guild.roles, name=CORETACT_ADMIN_ROLE)
    has_admin_role = bool(coretact_admin_role and coretact_admin_role in interaction.user.roles)  # type: ignore[attr-defined]
    logger.debug(f"User {interaction.user} has admin role: {has_admin_role}")
    return has_admin_role


def check_advert_owner(interaction: Interaction) -> bool:
    """Check if the user owns the specified advert.

    Extracts the public_key parameter from the interaction data and checks
    if the user owns that advert.

    Args:
        interaction: Discord interaction

    Returns:
        True if user owns the advert, False otherwise
    """
    # Extract public_key from interaction options
    public_key = None
    if "options" in interaction.data:
        for option in interaction.data["options"]:
            if option["name"] == "public_key":
                public_key = option.get("value")
                break

    if not public_key or not interaction.guild_id:
        return False

    # Ensure public_key is a string and normalize to lowercase
    if not isinstance(public_key, str):
        return False
    public_key = public_key.lower()

    # Use AdvertStorage to fetch the advert
    storage = AdvertStorage()
    advert = storage.get_advert(
        public_key=public_key,
        discord_server_id=str(interaction.guild_id),
    )

    if not advert:
        return False

    # Check if user owns this advert
    return str(interaction.user.id) == advert.discord_user_id


def is_coretact_admin_or_owner(interaction: Interaction) -> bool:
    """Check if user is either a Coretact admin or owns the advert.

    Extracts the public_key from the interaction and checks if the user
    is either an admin or the owner of that advert.

    Args:
        interaction: Discord interaction

    Returns:
        True if user is admin or owns the advert, False otherwise
    """
    # Check admin role first (more efficient)
    if is_coretact_admin(interaction):
        logger.debug(f"User {interaction.user} has Coretact Admin role")
        return True

    # If not admin, check if they own the specific advert
    try:
        is_owner = check_advert_owner(interaction)
        logger.debug(f"User {interaction.user} advert ownership check: {is_owner}")
        return is_owner
    except Exception as e:
        logger.warning(f"Error checking advert ownership: {e}")
        return False


class CoretactCog(commands.GroupCog, name="coretact"):
    """Cog for managing meshcore contact advertisements."""

    # Color map for device types
    TYPE_COLORS = {
        1: 0x00FF00,  # Companion - Green
        2: 0xFF9900,  # Repeater - Orange
        3: 0x0099FF,  # Room - Blue
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storage = AdvertStorage()

    # Advert subcommand group
    advert_group = app_commands.Group(name="advert", description="Manage contact advertisements")

    # Marks subcommand group
    marks_group = app_commands.Group(name="marks", description="Manage marked contacts")

    async def cog_app_command_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        """Handle errors from app commands."""
        logger.error(f"App command error: {type(error).__name__}: {error}")

        if isinstance(error, app_commands.errors.CommandInvokeError):
            original_error = error.original
            if isinstance(original_error, ValueError):
                await interaction.response.send_message(
                    f"Invalid input: {original_error}",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"An error occurred: {original_error}",
                    ephemeral=True,
                )
        elif isinstance(error, app_commands.errors.CheckFailure):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"An unexpected error occurred: {error}",
                ephemeral=True,
            )

    @advert_group.command(name="add", description="Add or update your meshcore contact advertisement")
    @app_commands.describe(meshcore_url="The meshcore:// URL from your device")
    async def advert_add(self, interaction: Interaction, meshcore_url: str):
        """Add or update a meshcore contact advertisement.

        Args:
            interaction: Discord interaction
            meshcore_url: The meshcore:// URL to add
        """
        # Validate URL format
        if not meshcore_url.startswith("meshcore://"):
            await interaction.response.send_message(
                "Invalid URL format. Must start with `meshcore://`",
                ephemeral=True,
            )
            return

        try:
            # Parse and create/update advert
            advert = self.storage.create_advert_from_url(
                meshcore_url=meshcore_url,
                discord_server_id=str(interaction.guild_id),
                discord_user_id=str(interaction.user.id),
            )

            # Check if this advert already exists (by server and public key only)
            existing = self.storage.get_advert(
                public_key=advert.public_key,
                discord_server_id=str(interaction.guild_id),
            )

            if existing:
                # Update existing advert (keep the same user)
                self.storage.update_advert(existing, meshcore_url)
                existing.datafile.save()
                action = "updated"
            else:
                # Save new advert
                advert.datafile.save()
                action = "added"

            # Create response embed
            embed = Embed(
                title=f"Advertisement {action}!",
                description=f"Your meshcore contact has been {action}.",
                color=0x00FF00,
            )
            embed.add_field(name="Name", value=advert.name, inline=True)
            embed.add_field(
                name="Type",
                value=self._type_to_string(advert.radio_type),
                inline=True,
            )
            embed.add_field(
                name="Public Key",
                value=advert.public_key,
                inline=False,
            )

            if advert.latitude != 0.0 or advert.longitude != 0.0:
                embed.add_field(
                    name="Location",
                    value=f"{advert.latitude}, {advert.longitude}",
                    inline=True,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(
                f"Advert {action} by user {interaction.user.id} in guild {interaction.guild_id}: {advert.public_key}"
            )

        except ValueError as e:
            await interaction.response.send_message(
                f"Failed to parse meshcore URL: {e}",
                ephemeral=True,
            )
            logger.error(f"Failed to parse URL from user {interaction.user.id}: {e}")
        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred while saving your advertisement: {e}",
                ephemeral=True,
            )
            logger.error(f"Error saving advert for user {interaction.user.id}: {e}")

    @advert_group.command(name="list", description="List meshcore contact advertisements")
    @app_commands.describe(user="Optional: List adverts for a specific user (defaults to yourself)")
    async def advert_list(self, interaction: Interaction, user: Optional[str] = None):
        """List all adverts for a user.

        Args:
            interaction: Discord interaction
            user: Optional Discord user mention or ID
        """
        # Determine which user to list adverts for
        if user:
            # Try to parse user mention or ID
            user_id = user.strip("<@!>")
            try:
                target_user = await interaction.guild.fetch_member(int(user_id))
                target_user_id = str(target_user.id)
                target_user_name = target_user.display_name
            except (ValueError, Exception):
                await interaction.response.send_message(
                    "Invalid user. Please mention a user or provide their ID.",
                    ephemeral=True,
                )
                return
        else:
            target_user_id = str(interaction.user.id)
            target_user_name = interaction.user.display_name

        # Get adverts for the user
        adverts = self.storage.list_user_adverts(
            discord_server_id=str(interaction.guild_id),
            discord_user_id=target_user_id,
        )

        if not adverts:
            await interaction.response.send_message(
                f"No advertisements found for {target_user_name}.",
                ephemeral=True,
            )
            return

        # Create message content with header
        content = f"**Advertisements for {target_user_name}**\nFound {len(adverts)} advertisement(s)"

        # Create one embed per advert (limit to 10 due to Discord's embed limit per message)
        max_adverts = 10
        embeds = []
        for advert in adverts[:max_adverts]:
            # Get color based on device type
            color = self.TYPE_COLORS.get(advert.radio_type, 0x808080)  # Default to gray if unknown

            # Create an embed for this advert with public key as title
            embed = Embed(
                color=color,
            )
            # Add Name field inline
            embed.add_field(
                name="Name",
                value=advert.name,
                inline=True,
            )
            # Add Type field inline
            embed.add_field(
                name="Type",
                value=self._type_to_string(advert.radio_type),
                inline=True,
            )
            embed.add_field(
                name="Updated",
                value=f"<t:{int(advert.updated_at)}:R>",
                inline=True,
            )
            embed.add_field(
                name="Public Key",
                value=advert.public_key,
                inline=False,
            )
            embeds.append(embed)

        # Add footer note to the message if there are more adverts
        if len(adverts) > max_adverts:
            content += f"\n_Showing first {max_adverts} of {len(adverts)} advertisements_"

        await interaction.response.send_message(content=content, embeds=embeds, ephemeral=True)
        logger.info(f"Listed {len(adverts)} adverts for user {target_user_id} in guild {interaction.guild_id}")

    @app_commands.check(is_coretact_admin_or_owner)
    @advert_group.command(name="remove", description="Remove a meshcore contact advertisement")
    @app_commands.describe(public_key="The full public key of the advertisement to remove (64 characters)")
    async def advert_remove(self, interaction: Interaction, public_key: str):
        """Remove a meshcore contact advertisement.

        Users can remove their own adverts. Users with the Coretact Admin role can remove any advert.

        Args:
            interaction: Discord interaction
            public_key: Full public key to remove (must be exact 64-character key)
        """
        # Normalize to lowercase
        public_key = public_key.lower()

        # Ensure we're in a guild
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        # Get the advert by exact public key match
        # The @app_commands.check decorator ensures only owners/admins can delete
        advert = self.storage.get_advert(
            public_key=public_key,
            discord_server_id=str(interaction.guild_id),
        )

        if not advert:
            await interaction.response.send_message(
                f"No advertisement found with public key `{public_key}`.",
                ephemeral=True,
            )
            return

        # Permission check is handled by @app_commands.check decorator

        # Delete the advert
        success = self.storage.delete_advert(
            public_key=advert.public_key,
            discord_server_id=str(interaction.guild_id),
        )

        if success:
            embed = Embed(
                title="Advertisement removed",
                description=f"Advertisement for **{advert.name}** has been removed.",
                color=0xFF9900,
            )
            embed.add_field(
                name="Public Key",
                value=f"`{advert.public_key}`",
                inline=False,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(
                f"Advert removed by user {interaction.user.id} in guild {interaction.guild_id}: "
                f"{advert.public_key} (owner={advert.discord_user_id})"
            )
        else:
            await interaction.response.send_message(
                "Failed to remove advertisement. Please try again.",
                ephemeral=True,
            )
            logger.error(f"Failed to delete advert {advert.public_key} for user {advert.discord_user_id}")

    @advert_group.command(name="search", description="Search meshcore contact advertisements in this server")
    @app_commands.describe(
        type="Filter by device type",
        key_prefix="Filter by public key prefix (first 8+ characters)",
        name="Filter by name (partial match)",
        user="Filter by specific user",
    )
    async def advert_search(
        self,
        interaction: Interaction,
        type: Optional[Literal["companion", "repeater", "room"]] = None,
        key_prefix: Optional[str] = None,
        name: Optional[str] = None,
        user: Optional[str] = None,
    ):
        """Search for contact advertisements in the server.

        Args:
            interaction: Discord interaction
            type: Device type filter
            key_prefix: Public key prefix filter
            name: Name filter (partial match)
            user: User ID or mention
        """
        # Parse user filter if provided
        user_id = None
        if user:
            user_id = user.strip("<@!>")
            try:
                await interaction.guild.fetch_member(int(user_id))
            except (ValueError, Exception):
                await interaction.response.send_message(
                    "Invalid user. Please mention a user or provide their ID.",
                    ephemeral=True,
                )
                return

        # Convert type string to int
        type_id = None
        if type:
            type_map = {"companion": 1, "repeater": 2, "room": 3}
            type_id = type_map.get(type)

        # Get all adverts for the server
        all_adverts = self.storage.list_server_adverts(
            discord_server_id=str(interaction.guild_id),
        )

        # Apply filters
        filtered_adverts = list(ContactFilter.filter_adverts(
            all_adverts,
            type=type_id,
            key_prefix=key_prefix,
            name=name,
            user_id=user_id,
        ))

        if not filtered_adverts:
            await interaction.response.send_message(
                "No advertisements found matching your criteria.",
                ephemeral=True,
            )
            return

        # Create response embed
        filter_desc = []
        if type:
            filter_desc.append(f"Type: **{type}**")
        if key_prefix:
            filter_desc.append(f"Key prefix: `{key_prefix}`")
        if name:
            filter_desc.append(f"Name: **{name}**")
        if user:
            filter_desc.append(f"User: <@{user_id}>")

        embed = Embed(
            title="Search Results",
            description=f"Found {len(filtered_adverts)} advertisement(s)\n" + " | ".join(filter_desc)
            if filter_desc
            else f"Found {len(filtered_adverts)} advertisement(s)",
            color=0x00FF00,
        )

        for advert in filtered_adverts[:25]:  # Discord embed field limit
            field_value = (
                f"**Type:** {self._type_to_string(advert.radio_type)}\n"
                f"**Key:** `{advert.public_key}`\n"
                f"**User:** <@{advert.discord_user_id}>\n"
                f"**Updated:** <t:{int(advert.updated_at)}:R>"
            )
            embed.add_field(
                name=advert.name,
                value=field_value,
                inline=False,
            )

        if len(filtered_adverts) > 25:
            embed.set_footer(text=f"Showing first 25 of {len(filtered_adverts)} advertisements")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(
            f"Search returned {len(filtered_adverts)} results for user {interaction.user.id} in guild {interaction.guild_id}"
        )

    @advert_group.command(name="download", description="Download contacts as a JSON file")
    @app_commands.describe(
        type="Filter by device type",
        key_prefix="Filter by public key prefix (first 8+ characters)",
        name="Filter by name (partial match)",
        user="Filter by specific user",
    )
    async def advert_download(
        self,
        interaction: Interaction,
        type: Optional[Literal["companion", "repeater", "room"]] = None,
        key_prefix: Optional[str] = None,
        name: Optional[str] = None,
        user: Optional[str] = None,
    ):
        """Download contacts as a JSON file.

        Args:
            interaction: Discord interaction
            type: Device type filter
            key_prefix: Public key prefix filter
            name: Name filter (partial match)
            user: User ID or mention
        """
        # Parse user filter if provided
        user_id = None
        if user:
            user_id = user.strip("<@!>")
            try:
                await interaction.guild.fetch_member(int(user_id))
            except (ValueError, Exception):
                await interaction.response.send_message(
                    "Invalid user. Please mention a user or provide their ID.",
                    ephemeral=True,
                )
                return

        # Convert type string to int
        type_id = None
        if type:
            type_map = {"companion": 1, "repeater": 2, "room": 3}
            type_id = type_map.get(type)

        # Get all adverts for the server
        all_adverts = self.storage.list_server_adverts(
            discord_server_id=str(interaction.guild_id),
        )

        # Apply filters
        filtered_adverts = list(ContactFilter.filter_adverts(
            all_adverts,
            type=type_id,
            key_prefix=key_prefix,
            name=name,
            user_id=user_id,
        ))

        if not filtered_adverts:
            await interaction.response.send_message(
                "No advertisements found matching your criteria.",
                ephemeral=True,
            )
            return

        # Convert to ContactsList format
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

        json_str = json.dumps(contacts_dict, indent=2)
        json_bytes = io.BytesIO(json_str.encode("utf-8"))

        # Create Discord file
        file = File(json_bytes, filename=f"contacts_{interaction.guild_id}.json")

        # Send file as ephemeral response
        await interaction.response.send_message(
            f"Here's your contacts file with {len(filtered_adverts)} contact(s):",
            file=file,
            ephemeral=True,
        )
        logger.info(
            f"Downloaded {len(filtered_adverts)} contacts for user {interaction.user.id} in guild {interaction.guild_id}"
        )

    @marks_group.command(name="add", description="Mark one or more contact public keys for later download")
    @app_commands.describe(public_keys="Comma-separated list of public keys to mark (e.g., abc123...,def456...)")
    async def marks_add(self, interaction: Interaction, public_keys: str):
        """Mark one or more contact public keys for later download.

        Args:
            interaction: Discord interaction
            public_keys: Comma-separated list of public keys to mark
        """
        if not interaction.guild_id:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        # Parse and normalize public keys
        keys_list = [key.strip().lower() for key in public_keys.split(",") if key.strip()]

        if not keys_list:
            await interaction.response.send_message(
                "Please provide at least one public key to mark.",
                ephemeral=True,
            )
            return

        # Get or create marks for the user
        marks = Marks.objects.get_or_none(  # type: ignore[attr-defined]
            discord_server_id=str(interaction.guild_id),
            discord_user_id=str(interaction.user.id),
        )

        if not marks:
            marks = Marks(  # type: ignore[call-arg]
                discord_server_id=str(interaction.guild_id),
                discord_user_id=str(interaction.user.id),
                public_keys=[],
            )

        # Mark the public keys (only add new ones)
        marked_count = 0
        already_marked_count = 0
        not_found_count = 0

        for public_key in keys_list:
            # Verify the advert exists in this server
            advert = self.storage.get_advert(public_key, str(interaction.guild_id))
            if not advert:
                not_found_count += 1
                continue

            if public_key not in marks.public_keys:
                marks.public_keys.append(public_key)
                marked_count += 1
            else:
                already_marked_count += 1

        # Save the marks
        from time import time

        marks.updated_at = time()
        marks.datafile.save()  # type: ignore[attr-defined]

        # Create response embed
        color = 0x00FF00
        description_parts = []
        if marked_count > 0:
            description_parts.append(f"Marked {marked_count} contact(s)")
        if already_marked_count > 0:
            description_parts.append(f"{already_marked_count} already marked")
        if not_found_count > 0:
            description_parts.append(f"{not_found_count} not found in this server")

        description = "\n".join(description_parts) if description_parts else "No contacts marked"

        embed = Embed(
            title="Contacts marked",
            description=description,
            color=color,
        )

        embed.add_field(
            name="Total Marked",
            value=str(len(marks.public_keys)),
            inline=True,
        )

        embed.set_footer(text="Use /coretact marks download to download all marked contacts")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(
            f"User {interaction.user.id} marked {marked_count} contacts in guild {interaction.guild_id}"
        )

    @marks_group.command(name="remove", description="Unmark one or more contact public keys")
    @app_commands.describe(public_keys="Comma-separated list of public keys to unmark (e.g., abc123...,def456...)")
    async def marks_remove(self, interaction: Interaction, public_keys: str):
        """Unmark one or more contact public keys.

        Args:
            interaction: Discord interaction
            public_keys: Comma-separated list of public keys to unmark
        """
        if not interaction.guild_id:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        # Parse and normalize public keys
        keys_list = [key.strip().lower() for key in public_keys.split(",") if key.strip()]

        if not keys_list:
            await interaction.response.send_message(
                "Please provide at least one public key to unmark.",
                ephemeral=True,
            )
            return

        # Get marks for the user
        marks = Marks.objects.get_or_none(  # type: ignore[attr-defined]
            discord_server_id=str(interaction.guild_id),
            discord_user_id=str(interaction.user.id),
        )

        if not marks or not marks.public_keys:
            await interaction.response.send_message(
                "You haven't marked any contacts yet.",
                ephemeral=True,
            )
            return

        # Unmark the public keys
        unmarked_count = 0
        not_marked_count = 0

        for public_key in keys_list:
            if public_key in marks.public_keys:
                marks.public_keys.remove(public_key)
                unmarked_count += 1
            else:
                not_marked_count += 1

        # Save the marks
        from time import time

        marks.updated_at = time()
        marks.datafile.save()  # type: ignore[attr-defined]

        # Create response embed
        color = 0xFF9900
        description_parts = []
        if unmarked_count > 0:
            description_parts.append(f"Unmarked {unmarked_count} contact(s)")
        if not_marked_count > 0:
            description_parts.append(f"{not_marked_count} were not marked")

        description = "\n".join(description_parts) if description_parts else "No contacts unmarked"

        embed = Embed(
            title="Contacts unmarked",
            description=description,
            color=color,
        )

        embed.add_field(
            name="Total Marked",
            value=str(len(marks.public_keys)),
            inline=True,
        )

        embed.set_footer(text="Use /coretact marks download to download all marked contacts")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(
            f"User {interaction.user.id} unmarked {unmarked_count} contacts in guild {interaction.guild_id}"
        )

    @marks_group.command(name="download", description="Download all contacts you've marked")
    async def marks_download(self, interaction: Interaction):
        """Download all marked contacts as a JSON file.

        Args:
            interaction: Discord interaction
        """
        if not interaction.guild_id:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        # Get marks for the user
        marks = Marks.objects.get_or_none(  # type: ignore[attr-defined]
            discord_server_id=str(interaction.guild_id),
            discord_user_id=str(interaction.user.id),
        )

        if not marks or not marks.public_keys:
            await interaction.response.send_message(
                "You haven't marked any contacts yet. Use the 'Mark Contact' option when right-clicking on a user.",
                ephemeral=True,
            )
            return

        # Get all marked adverts
        marked_adverts = []
        for public_key in marks.public_keys:
            advert = self.storage.get_advert(public_key, str(interaction.guild_id))
            if advert:
                marked_adverts.append(advert)

        if not marked_adverts:
            await interaction.response.send_message(
                "None of your marked contacts are currently available.",
                ephemeral=True,
            )
            return

        # Convert to ContactsList format
        contacts_list = ContactConverter.adverts_to_contacts_list(marked_adverts)

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

        json_str = json.dumps(contacts_dict, indent=2)
        json_bytes = io.BytesIO(json_str.encode("utf-8"))

        # Create Discord file
        file = File(json_bytes, filename=f"marked_contacts_{interaction.guild_id}.json")

        # Send file as ephemeral response
        await interaction.response.send_message(
            f"Here are your {len(marked_adverts)} marked contact(s):",
            file=file,
            ephemeral=True,
        )
        logger.info(
            f"Downloaded {len(marked_adverts)} marked contacts for user {interaction.user.id} in guild {interaction.guild_id}"
        )

    @marks_group.command(name="list", description="List all contacts you've marked")
    async def marks_list(self, interaction: Interaction):
        """List all marked contacts.

        Args:
            interaction: Discord interaction
        """
        if not interaction.guild_id:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        # Get marks for the user
        marks = Marks.objects.get_or_none(  # type: ignore[attr-defined]
            discord_server_id=str(interaction.guild_id),
            discord_user_id=str(interaction.user.id),
        )

        if not marks or not marks.public_keys:
            await interaction.response.send_message(
                "You haven't marked any contacts yet. Use the 'Mark Contact' option when right-clicking on a user.",
                ephemeral=True,
            )
            return

        # Get all marked adverts
        marked_adverts = []
        missing_count = 0
        for public_key in marks.public_keys:
            advert = self.storage.get_advert(public_key, str(interaction.guild_id))
            if advert:
                marked_adverts.append(advert)
            else:
                missing_count += 1

        if not marked_adverts:
            await interaction.response.send_message(
                f"You have {len(marks.public_keys)} marked contact(s), but none are currently available in this server.",
                ephemeral=True,
            )
            return

        # Create message content with header
        content = f"**Your Marked Contacts**\nYou have {len(marks.public_keys)} marked contact(s) total"
        if missing_count > 0:
            content += f"\n_{missing_count} marked contact(s) not found in this server_"

        # Create one embed per advert (limit to 10 due to Discord's embed limit per message)
        max_adverts = 10
        embeds = []
        for advert in marked_adverts[:max_adverts]:
            # Get color based on device type
            color = self.TYPE_COLORS.get(advert.radio_type, 0x808080)  # Default to gray if unknown

            # Create an embed for this advert
            embed = Embed(
                color=color,
            )
            # Add Name field inline
            embed.add_field(
                name="Name",
                value=advert.name,
                inline=True,
            )
            # Add Type field inline
            embed.add_field(
                name="Type",
                value=self._type_to_string(advert.radio_type),
                inline=True,
            )
            # Add Updated field inline
            embed.add_field(
                name="Updated",
                value=f"<t:{int(advert.updated_at)}:R>",
                inline=True,
            )
            # Add Public Key field non-inline
            embed.add_field(
                name="Public Key",
                value=advert.public_key,
                inline=False,
            )
            # Add Owner field non-inline
            embed.add_field(
                name="Owner",
                value=f"<@{advert.discord_user_id}>",
                inline=False,
            )
            embeds.append(embed)

        # Add footer note to the message if there are more adverts
        if len(marked_adverts) > max_adverts:
            content += f"\n_Showing first {max_adverts} of {len(marked_adverts)} available contacts_"

        await interaction.response.send_message(content=content, embeds=embeds, ephemeral=True)
        logger.info(
            f"Listed {len(marked_adverts)} marked contacts for user {interaction.user.id} in guild {interaction.guild_id}"
        )

    @app_commands.command(name="info", description="Show statistics about contacts in this server")
    async def server_info(self, interaction: Interaction):
        """Show server contact statistics.

        Args:
            interaction: Discord interaction
        """
        # Get all adverts for the server
        all_adverts = self.storage.list_server_adverts(
            discord_server_id=str(interaction.guild_id),
        )

        if not all_adverts:
            await interaction.response.send_message(
                "No advertisements found in this server.",
                ephemeral=True,
            )
            return

        # Calculate statistics
        total_adverts = len(all_adverts)
        by_type = {"companion": 0, "repeater": 0, "room": 0, "unknown": 0}
        unique_users = set()
        last_updated = 0

        for advert in all_adverts:
            unique_users.add(advert.discord_user_id)
            last_updated = max(last_updated, advert.updated_at)

            # Count by type (using the raw type values from the advert)
            type_str = self._type_to_string(advert.radio_type).lower()
            if type_str in by_type:
                by_type[type_str] += 1
            else:
                by_type["unknown"] += 1

        # Create response embed
        embed = Embed(
            title="📊 Contact Statistics",
            description=f"Statistics for {interaction.guild.name}",
            color=0x5865F2,
        )

        embed.add_field(name="Total Contacts", value=str(total_adverts), inline=True)
        embed.add_field(name="Unique Users", value=str(len(unique_users)), inline=True)
        embed.add_field(name="Last Updated", value=f"<t:{int(last_updated)}:R>", inline=True)

        # Add breakdown by type
        type_breakdown = "\n".join([f"**{k.capitalize()}:** {v}" for k, v in by_type.items() if v > 0])
        embed.add_field(name="By Type", value=type_breakdown or "No data", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(
            f"Info displayed for guild {interaction.guild_id}: {total_adverts} adverts, {len(unique_users)} users"
        )

    @app_commands.checks.has_role(CORETACT_ADMIN_ROLE)
    @app_commands.command(name="refresh-meshes", description="[Admin] Update mesh information for all servers")
    async def refresh_meshes(self, interaction: Interaction):
        """Update mesh metadata for all joined Discord servers.

        This command is useful for updating servers that joined before mesh tracking
        was implemented, or for manually refreshing server information.

        Requires the Coretact Admin role.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True)

        updated_count = 0
        error_count = 0

        # Get the bot instance to access _create_or_update_mesh
        bot = self.bot

        # Iterate through all guilds the bot is in
        for guild in bot.guilds:
            try:
                # Call the bot's _create_or_update_mesh method
                if hasattr(bot, "_create_or_update_mesh"):
                    await bot._create_or_update_mesh(guild)
                    updated_count += 1
                    logger.info(f"Refreshed mesh for guild {guild.id}: {guild.name}")
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to refresh mesh for guild {guild.id}: {e}")

        # Create response embed
        embed = Embed(
            title="Mesh Refresh Complete",
            description=f"Updated mesh information for {updated_count} server(s)",
            color=0x00FF00 if error_count == 0 else 0xFFAA00,
        )

        embed.add_field(name="Total Servers", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Successfully Updated", value=str(updated_count), inline=True)

        if error_count > 0:
            embed.add_field(name="Errors", value=str(error_count), inline=True)
            embed.set_footer(text="Check logs for error details")

        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(
            f"Mesh refresh completed by user {interaction.user.id}: {updated_count} updated, {error_count} errors"
        )

    @staticmethod
    def _type_to_string(type_id: int) -> str:
        """Convert device type ID to human-readable string.

        Args:
            type_id: Device type (1, 2, or 3)

        Returns:
            Human-readable type string
        """
        type_map = {
            1: "Companion",
            2: "Repeater",
            3: "Room",
        }
        return type_map.get(type_id, f"Unknown ({type_id})")


# Context menus must be defined outside the cog class
@app_commands.context_menu(name="Show Meshcore Contacts")
async def show_user_contacts(interaction: Interaction, user: Member | User):
    """User context menu: Show all contacts for a user.

    Args:
        interaction: Discord interaction
        user: The user whose contacts to show
    """
    if not interaction.guild_id:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )
        return

    # Get adverts for the user
    storage = AdvertStorage()
    adverts = storage.list_user_adverts(
        discord_server_id=str(interaction.guild_id),
        discord_user_id=str(user.id),
    )

    if not adverts:
        await interaction.response.send_message(
            f"No advertisements found for {user.display_name}.",
            ephemeral=True,
        )
        return

    # Create response embed
    embed = Embed(
        title=f"Contacts for {user.display_name}",
        description=f"Found {len(adverts)} contact(s)",
        color=0x0099FF,
    )

    type_map = {1: "Companion", 2: "Repeater", 3: "Room"}
    for advert in adverts[:25]:  # Discord embed field limit
        type_str = type_map.get(advert.radio_type, f"Unknown ({advert.radio_type})")
        field_value = (
            f"**Type:** {type_str}\n**Key:** `{advert.public_key}`\n**Updated:** <t:{int(advert.updated_at)}:R>"
        )
        embed.add_field(
            name=advert.name,
            value=field_value,
            inline=False,
        )

    if len(adverts) > 25:
        embed.set_footer(text=f"Showing first 25 of {len(adverts)} contacts")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(
        f"Showed {len(adverts)} contacts for user {user.id} to {interaction.user.id} in guild {interaction.guild_id}"
    )


@app_commands.context_menu(name="Mark MeshCore Contact")
async def mark_user_contact(interaction: Interaction, user: Member | User):
    """User context menu: Mark all contacts for a user.

    This allows users to mark contacts from other users for later download.

    Args:
        interaction: Discord interaction
        user: The user whose contacts to mark
    """
    if not interaction.guild_id:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )
        return

    # Get adverts for the target user
    storage = AdvertStorage()
    adverts = storage.list_user_adverts(
        discord_server_id=str(interaction.guild_id),
        discord_user_id=str(user.id),
    )

    if not adverts:
        await interaction.response.send_message(
            f"No advertisements found for {user.display_name}.",
            ephemeral=True,
        )
        return

    # Get or create marks for the requesting user
    marks = Marks.objects.get_or_none(  # type: ignore[attr-defined]
        discord_server_id=str(interaction.guild_id),
        discord_user_id=str(interaction.user.id),
    )

    if not marks:
        marks = Marks(  # type: ignore[call-arg]
            discord_server_id=str(interaction.guild_id),
            discord_user_id=str(interaction.user.id),
            public_keys=[],
        )

    # Mark all of the target user's adverts (only add new ones)
    marked_count = 0
    already_marked_count = 0

    for advert in adverts:
        public_key = advert.public_key.lower()
        if public_key not in marks.public_keys:
            marks.public_keys.append(public_key)
            marked_count += 1
        else:
            already_marked_count += 1

    # Save the marks
    from time import time

    marks.updated_at = time()
    marks.datafile.save()  # type: ignore[attr-defined]

    # Create response embed
    color = 0x00FF00
    if marked_count > 0:
        description = f"Marked {marked_count} contact(s) from {user.display_name}"
        if already_marked_count > 0:
            description += f"\n({already_marked_count} already marked)"
    else:
        description = f"All {already_marked_count} contact(s) from {user.display_name} were already marked"

    embed = Embed(
        title="Contacts marked",
        description=description,
        color=color,
    )

    embed.add_field(
        name="Total Marked",
        value=str(len(marks.public_keys)),
        inline=True,
    )

    embed.set_footer(text="Use /coretact marks download to download all marked contacts")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(
        f"User {interaction.user.id} marked {marked_count} contacts from user {user.id} in guild {interaction.guild_id}"
    )


@app_commands.context_menu(name="Unmark MeshCore Contact")
async def unmark_user_contact(interaction: Interaction, user: Member | User):
    """User context menu: Unmark all contacts for a user.

    This allows users to unmark contacts from other users.

    Args:
        interaction: Discord interaction
        user: The user whose contacts to unmark
    """
    if not interaction.guild_id:
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True,
        )
        return

    # Get adverts for the target user
    storage = AdvertStorage()
    adverts = storage.list_user_adverts(
        discord_server_id=str(interaction.guild_id),
        discord_user_id=str(user.id),
    )

    if not adverts:
        await interaction.response.send_message(
            f"No advertisements found for {user.display_name}.",
            ephemeral=True,
        )
        return

    # Get marks for the requesting user
    marks = Marks.objects.get_or_none(  # type: ignore[attr-defined]
        discord_server_id=str(interaction.guild_id),
        discord_user_id=str(interaction.user.id),
    )

    if not marks or not marks.public_keys:
        await interaction.response.send_message(
            "You haven't marked any contacts yet.",
            ephemeral=True,
        )
        return

    # Unmark all of the target user's adverts
    unmarked_count = 0
    not_marked_count = 0

    for advert in adverts:
        public_key = advert.public_key.lower()
        if public_key in marks.public_keys:
            marks.public_keys.remove(public_key)
            unmarked_count += 1
        else:
            not_marked_count += 1

    # Save the marks
    from time import time

    marks.updated_at = time()
    marks.datafile.save()  # type: ignore[attr-defined]

    # Create response embed
    color = 0xFF9900
    if unmarked_count > 0:
        description = f"Unmarked {unmarked_count} contact(s) from {user.display_name}"
        if not_marked_count > 0:
            description += f"\n({not_marked_count} were not marked)"
    else:
        description = f"No contacts from {user.display_name} were marked"

    embed = Embed(
        title="Contacts unmarked",
        description=description,
        color=color,
    )

    embed.add_field(
        name="Total Marked",
        value=str(len(marks.public_keys)),
        inline=True,
    )

    embed.set_footer(text="Use /coretact marks download to download all marked contacts")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    logger.info(
        f"User {interaction.user.id} unmarked {unmarked_count} contacts from user {user.id} in guild {interaction.guild_id}"
    )


async def setup(bot: commands.Bot):
    """Set up the Coretact cog.

    Args:
        bot: The bot instance
    """
    await bot.add_cog(CoretactCog(bot))

    # Add context menus to the command tree
    bot.tree.add_command(show_user_contacts)
    bot.tree.add_command(mark_user_contact)
    bot.tree.add_command(unmark_user_contact)
