"""Discord bot initialization for Coretact."""

import os
import sys

from discord import Intents
from discord.ext import commands

from coretact.log import logger

# Load environment variables
try:
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    DISCORD_BOT_OWNER_ID = os.getenv("DISCORD_BOT_OWNER_ID")
    AUTO_SYNC_COMMANDS = bool(os.getenv("AUTO_SYNC_COMMANDS", "true"))

    if not DISCORD_BOT_TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

    # Owner ID is optional
    if DISCORD_BOT_OWNER_ID:
        DISCORD_BOT_OWNER_ID = int(DISCORD_BOT_OWNER_ID)
    else:
        DISCORD_BOT_OWNER_ID = None
        logger.warning("DISCORD_BOT_OWNER_ID not set - owner commands will be disabled")

except (TypeError, ValueError) as e:
    logger.error(f"Failed to load environment variables: {e}")
    sys.exit(1)


class CoretactBot(commands.Bot):
    """Main bot class for Coretact."""

    def __init__(self, **kwargs):
        super().__init__(command_prefix="./coretact ", **kwargs)

        self.initial_extensions = [
            "coretact.cogs.coretact",
        ]

    async def setup_hook(self):
        """Called when the bot is starting up."""
        logger.info("Setting up Coretact bot...")

        # Load cogs
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}")

    async def on_ready(self):
        """Called when the bot is ready."""
        if self.user:
            logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # Auto-sync commands on startup if enabled
        if AUTO_SYNC_COMMANDS:
            try:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} command(s)")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")
        else:
            logger.info("Command auto-sync is disabled")

        logger.info("Bot is ready!")


# Set up intents - minimal intents for slash commands only
intents = Intents.none()

# Create bot instance
bot = CoretactBot(
    intents=intents,
    owner_id=DISCORD_BOT_OWNER_ID,
)


def main():
    """Main entry point for the bot."""
    if not DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN is not set")
        sys.exit(1)

    try:
        bot.run(DISCORD_BOT_TOKEN)
    except Exception as e:
        logger.error(f"Failed to run bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
