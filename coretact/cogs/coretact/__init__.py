"""Coretact command group cog for managing meshcore contacts."""

import io
import json
from typing import Literal, Optional

from discord import Embed, File, Interaction, app_commands
from discord.ext import commands
from discord.utils import get

from coretact.log import logger
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

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storage = AdvertStorage()

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

    @app_commands.command(name="add", description="Add or update your meshcore contact advertisement")
    @app_commands.describe(meshcore_url="The meshcore:// URL from your device")
    async def add_advert(self, interaction: Interaction, meshcore_url: str):
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

    @app_commands.command(name="list", description="List your meshcore contact advertisements")
    @app_commands.describe(user="Optional: List adverts for a specific user (defaults to yourself)")
    async def list_adverts(self, interaction: Interaction, user: Optional[str] = None):
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

        # Create response embed
        embed = Embed(
            title=f"Advertisements for {target_user_name}",
            description=f"Found {len(adverts)} advertisement(s)",
            color=0x0099FF,
        )

        for advert in adverts[:25]:  # Discord embed field limit
            field_value = (
                f"**Type:** {self._type_to_string(advert.radio_type)}\n"
                f"**Key:** `{advert.public_key}`\n"
                f"**Updated:** <t:{int(advert.updated_at)}:R>"
            )
            embed.add_field(
                name=advert.name,
                value=field_value,
                inline=False,
            )

        if len(adverts) > 25:
            embed.set_footer(text=f"Showing first 25 of {len(adverts)} advertisements")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Listed {len(adverts)} adverts for user {target_user_id} in guild {interaction.guild_id}")


    @app_commands.check(is_coretact_admin_or_owner)
    @app_commands.command(name="remove", description="Remove a meshcore contact advertisement")
    @app_commands.describe(public_key="The full public key of the advertisement to remove (64 characters)")
    async def remove_advert(self, interaction: Interaction, public_key: str):
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

    @app_commands.command(name="search", description="Search meshcore contact advertisements in this server")
    @app_commands.describe(
        type="Filter by device type",
        key_prefix="Filter by public key prefix (first 8+ characters)",
        name="Filter by name (partial match)",
        user="Filter by specific user",
    )
    async def search_adverts(
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
        filtered_adverts = ContactFilter.filter_adverts(
            all_adverts,
            type=type_id,
            key_prefix=key_prefix,
            name=name,
            user_id=user_id,
        )

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

    @app_commands.command(name="download", description="Download contacts as a JSON file")
    @app_commands.describe(
        type="Filter by device type",
        key_prefix="Filter by public key prefix (first 8+ characters)",
        name="Filter by name (partial match)",
        user="Filter by specific user",
    )
    async def download_contacts(
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
        filtered_adverts = ContactFilter.filter_adverts(
            all_adverts,
            type=type_id,
            key_prefix=key_prefix,
            name=name,
            user_id=user_id,
        )

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


async def setup(bot: commands.Bot):
    """Set up the Coretact cog.

    Args:
        bot: The bot instance
    """
    await bot.add_cog(CoretactCog(bot))
