"""Data models for Coretact."""

import os
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Optional

from datafiles.decorators import datafile

from coretact.log import logger

# Resolve storage path
STORAGE_PATH = os.getenv("STORAGE_PATH")
if STORAGE_PATH:
    # Use provided path (can be relative or absolute)
    storage_base = Path(STORAGE_PATH).resolve()
    logger.info(f"Using custom storage path: {storage_base}")
else:
    # Default to project root's storage directory
    # This file is in coretact/coretact/models.py, so go up 2 levels to get project root
    project_root = Path(__file__).parent.parent
    storage_base = (project_root / "storage").resolve()
    logger.debug(f"Using default storage path: {storage_base}")

# Ensure the storage directory exists
storage_base.mkdir(parents=True, exist_ok=True)

# Convert to string for datafiles decorator
STORAGE_BASE_PATH = str(storage_base)


@datafile(f"{STORAGE_BASE_PATH}/{{self.discord_server_id}}/{{self.discord_user_id}}/{{self.public_key}}.json")
class Advert:
    """Advertisement stored on disk.

    Each advert is stored as a separate JSON file organized by server and user.
    File path: storage/<server_id>/<user_id>/<public_key>.json
    """

    discord_server_id: str  # Discord guild ID
    discord_user_id: str  # Discord user ID
    public_key: str  # 64-char hex string (32 bytes)
    advert_string: str  # Full meshcore:// URL
    type: int  # Device type (1=companion, 2=repeater, 3=room)
    name: str  # Device name extracted from advert
    flags: int  # Parsed flags from advert
    latitude: float = 0.0  # Location if present
    longitude: float = 0.0  # Location if present
    out_path: str = ""  # Extracted from advert data
    created_at: float = 0.0  # Unix timestamp when advert was added
    updated_at: float = 0.0  # Unix timestamp of last update

    def __post_init__(self):
        """Set timestamps if not provided."""
        if self.created_at == 0.0:
            self.created_at = time()
        if self.updated_at == 0.0:
            self.updated_at = time()


@dataclass
class Contact:
    """Contact model for API responses.

    This is the format sent to clients via the API.
    """

    type: int
    name: str
    custom_name: Optional[str]
    public_key: str
    flags: int
    latitude: str
    longitude: str
    last_advert: int  # Unix timestamp
    last_modified: int  # Unix timestamp
    out_path: str


@dataclass
class ContactsList:
    """Response containing a list of contacts."""

    contacts: list[Contact]
