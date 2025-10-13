"""
MeshCore Advertisement Parser

Parses meshcore:// URLs containing advertisement data.
Supports two formats:

1. Contact Export Format (from CMD_EXPORT_CONTACT):
   - Byte 0: Format version/type (often 0x11)
   - Byte 1: Reserved (0x00)
   - Bytes 2-34: Public key (32 bytes)
   - Bytes 34-111: Other data (flags, paths, etc.)
   - Bytes 111-124: Name (null-padded, 13+ bytes)

2. Advertisement Broadcast Format:
   - Byte 0: Flags/Type byte
     - Bits 0-3: Advertisement type
     - Bit 4 (0x10): Location data present
     - Bit 5 (0x20): Feature 1 present
     - Bit 6 (0x40): Feature 2 present
     - Bit 7 (0x80): Name present
   - Optional fields based on flags

This parser primarily handles the Contact Export Format which is what
users will be sharing as meshcore:// URLs.
"""

import struct
from dataclasses import dataclass
from typing import Optional


# Advertisement type constants
ADV_TYPE_NONE = 0
ADV_TYPE_CHAT = 1  # Also called "Companion"
ADV_TYPE_REPEATER = 2
ADV_TYPE_ROOM = 3
ADV_TYPE_SENSOR = 4

# Flag masks (for broadcast format)
ADV_LATLON_MASK = 0x10  # Bit 4: Location present
ADV_FEAT1_MASK = 0x20   # Bit 5: Feature 1 present
ADV_FEAT2_MASK = 0x40   # Bit 6: Feature 2 present
ADV_NAME_MASK = 0x80    # Bit 7: Name present
ADV_TYPE_MASK = 0x0F    # Bits 0-3: Type


@dataclass
class ParsedAdvert:
    """Parsed advertisement data."""

    # Raw data
    advert_string: str  # Full meshcore:// URL
    raw_hex: str        # Hex data after meshcore://
    raw_bytes: bytes    # Raw byte data

    # Format information
    format_type: str    # "contact_export" or "broadcast"

    # Core fields
    public_key: Optional[str] = None  # Only in contact export format
    type: Optional[int] = None        # Advertisement type (0-15)
    type_name: Optional[str] = None   # Human-readable type name
    flags: Optional[int] = None       # Flags from contact export
    name: Optional[str] = None        # Device/contact name

    # Location (contact export format)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Timestamps (contact export format)
    last_advert: Optional[int] = None   # Unix timestamp
    last_modified: Optional[int] = None # Unix timestamp

    # Path information (contact export format)
    out_path: Optional[str] = None
    out_path_len: Optional[int] = None


class AdvertParser:
    """Parser for MeshCore advertisement URLs."""

    PROTOCOL = "meshcore://"

    TYPE_NAMES = {
        ADV_TYPE_NONE: "None",
        ADV_TYPE_CHAT: "Companion",
        ADV_TYPE_REPEATER: "Repeater",
        ADV_TYPE_ROOM: "Room",
        ADV_TYPE_SENSOR: "Sensor",
    }

    @classmethod
    def parse(cls, meshcore_url: str) -> ParsedAdvert:
        """
        Parse a meshcore:// URL into structured advertisement data.

        Args:
            meshcore_url: Full meshcore:// URL string

        Returns:
            ParsedAdvert object with all parsed fields

        Raises:
            ValueError: If URL is invalid or cannot be parsed
        """
        if not meshcore_url or not isinstance(meshcore_url, str):
            raise ValueError("URL must be a non-empty string")

        if not meshcore_url.startswith(cls.PROTOCOL):
            raise ValueError(f"URL must start with {cls.PROTOCOL}")

        # Extract hex data
        hex_data = meshcore_url[len(cls.PROTOCOL):]

        if not hex_data:
            raise ValueError("URL contains no data after protocol")

        # Validate hex format
        if not all(c in '0123456789abcdefABCDEF' for c in hex_data):
            raise ValueError("URL contains invalid hex characters")

        # Convert to bytes
        try:
            raw_bytes = bytes.fromhex(hex_data)
        except ValueError as e:
            raise ValueError(f"Failed to decode hex data: {e}")

        if len(raw_bytes) < 1:
            raise ValueError("Advertisement data is too short (minimum 1 byte)")

        # Parse the advertisement data
        return cls._parse_bytes(meshcore_url, hex_data, raw_bytes)

    @classmethod
    def _parse_bytes(cls, advert_string: str, raw_hex: str, data: bytes) -> ParsedAdvert:
        """Parse the raw bytes into advertisement fields."""

        # Detect format based on length and structure
        # Contact export format is typically 123-148 bytes with public key at offset 2-34
        # Broadcast format is much shorter (typically < 50 bytes)

        if len(data) >= 123 and data[1] == 0x00:
            # Likely contact export format
            return cls._parse_contact_export(advert_string, raw_hex, data)
        else:
            # Likely broadcast format
            return cls._parse_broadcast(advert_string, raw_hex, data)

    @classmethod
    def _parse_contact_export(cls, advert_string: str, raw_hex: str, data: bytes) -> ParsedAdvert:
        """
        Parse contact export format.

        The meshcore:// export format has a 2-byte header, then the standard CONTACT packet:
        - Byte 0: Format version (often 0x11)
        - Byte 1: Reserved (0x00)

        Then follows the standard CONTACT packet format (meshcore_py offsets are relative to packet start):
        - Bytes 2-33: Public key (32 bytes) [meshcore_py offset 1-33]
        - Byte 34: Type [meshcore_py offset 33]
        - Byte 35: Flags [meshcore_py offset 34]
        - Byte 36: Out path length (signed byte) [meshcore_py offset 35]
        - Bytes 37-100: Out path (64 bytes) [meshcore_py offset 36-99]
        - Bytes 101-132: Name (32 bytes, null-terminated) [meshcore_py offset 100-131]
        - Bytes 133-136: Last advert timestamp (uint32, little-endian) [meshcore_py offset 132-135]
        - Bytes 137-140: Latitude * 1E6 (int32, little-endian) [meshcore_py offset 136-139]
        - Bytes 141-144: Longitude * 1E6 (int32, little-endian) [meshcore_py offset 140-143]
        - Bytes 145-148: Last modified timestamp (uint32, little-endian) [meshcore_py offset 144-147]
        """

        if len(data) < 111:  # Minimum for headers + public key + type + name start
            raise ValueError(f"Contact export data too short: {len(data)} bytes (expected >= 111)")

        # Parse 2-byte header
        version_byte = data[0]
        reserved = data[1]

        # CONTACT packet data starts at byte 2
        # meshcore_py format (with code byte stripped):
        #   offset 1-33: public_key (32 bytes)
        #   offset 33: type
        #   offset 34: flags
        #   ... etc
        # Maps to our buffer starting at byte 2:
        #   data[2:34]: public_key (32 bytes)
        #   data[34]: type
        #   data[35]: flags
        #   ... etc

        offset = 2  # Start of CONTACT packet data (after 2-byte header)

        # Parse public key (32 bytes from offset to offset+32)
        public_key = data[offset:offset+32].hex()

        # Parse type (at offset+32)
        adv_type = data[offset+32] if len(data) > offset+32 else 0
        type_name = cls.TYPE_NAMES.get(adv_type, f"Unknown({adv_type})")

        # Parse flags (at offset+33)
        flags = data[offset+33] if len(data) > offset+33 else 0

        # Parse out_path_len (at offset+34, signed)
        out_path_len = struct.unpack('b', bytes([data[offset+34]]))[0] if len(data) > offset+34 else -1
        if out_path_len == -1:
            out_path_len = 0

        # Parse out_path (starts at offset+35, up to out_path_len bytes)
        out_path = None
        if len(data) > offset+35 and out_path_len > 0:
            out_path = data[offset+35:offset+35+out_path_len].hex()

        # Parse name (32 bytes at offset+99 to offset+131, null-terminated/null-padded)
        # meshcore_py offset 100-131 maps to our offset+99 to offset+131
        # Note: name may be null-padded at the beginning or end
        name = None
        if len(data) > offset+99:
            name_bytes = data[offset+99:min(offset+131, len(data))]
            # Decode the full field and strip all null bytes and whitespace
            name = name_bytes.decode('utf-8', errors='ignore').replace('\x00', '').strip()
            if not name:  # If empty after cleaning, set to None
                name = None

        # Parse timestamps and location
        # meshcore_py offset 132-135: last_advert -> our offset+131 to offset+135
        last_advert = None
        last_modified = None
        latitude = None
        longitude = None

        if len(data) >= offset+135:
            last_advert = struct.unpack('<I', data[offset+131:offset+135])[0]

        if len(data) >= offset+143:
            lat_raw = struct.unpack('<i', data[offset+135:offset+139])[0]
            lon_raw = struct.unpack('<i', data[offset+139:offset+143])[0]
            latitude = lat_raw / 1e6
            longitude = lon_raw / 1e6

        if len(data) >= offset+147:
            last_modified = struct.unpack('<I', data[offset+143:offset+147])[0]

        return ParsedAdvert(
            advert_string=advert_string,
            raw_hex=raw_hex,
            raw_bytes=data,
            format_type="contact_export",
            public_key=public_key,
            type=adv_type,
            type_name=type_name,
            flags=flags,
            name=name,
            latitude=latitude,
            longitude=longitude,
            last_advert=last_advert,
            last_modified=last_modified,
            out_path=out_path,
            out_path_len=out_path_len,
        )

    @classmethod
    def _parse_broadcast(cls, advert_string: str, raw_hex: str, data: bytes) -> ParsedAdvert:
        """
        Parse broadcast advertisement format.

        Format:
        - Byte 0: Flags/Type
        - Optional location (8 bytes)
        - Optional feature1 (2 bytes)
        - Optional feature2 (2 bytes)
        - Optional name (variable, null-terminated)
        """

        # Parse flags byte
        flags = data[0]
        adv_type = flags & ADV_TYPE_MASK
        type_name = cls.TYPE_NAMES.get(adv_type, f"Unknown({adv_type})")

        # Check which optional fields are present
        has_location = bool(flags & ADV_LATLON_MASK)
        has_feature1 = bool(flags & ADV_FEAT1_MASK)
        has_feature2 = bool(flags & ADV_FEAT2_MASK)
        has_name = bool(flags & ADV_NAME_MASK)

        # Start parsing after flags byte
        offset = 1

        # Parse optional fields
        latitude = None
        longitude = None

        # Parse location (8 bytes: lat + lon)
        if has_location:
            if offset + 8 > len(data):
                raise ValueError("Not enough data for location field")

            lat_bytes = data[offset:offset + 4]
            lon_bytes = data[offset + 4:offset + 8]

            # Convert bytes to signed int32 (little-endian) and scale
            latitude = struct.unpack('<i', lat_bytes)[0] / 1e6
            longitude = struct.unpack('<i', lon_bytes)[0] / 1e6

            offset += 8

        # Parse feature 1 (2 bytes, little-endian)
        if has_feature1:
            if offset + 2 > len(data):
                raise ValueError("Not enough data for feature1 field")
            offset += 2

        # Parse feature 2 (2 bytes, little-endian)
        if has_feature2:
            if offset + 2 > len(data):
                raise ValueError("Not enough data for feature2 field")
            offset += 2

        # Parse name (null-terminated string)
        name = None
        if has_name:
            if offset >= len(data):
                raise ValueError("Not enough data for name field")

            name_bytes = data[offset:]

            # Find null terminator
            null_pos = name_bytes.find(b'\x00')
            if null_pos != -1:
                name_bytes = name_bytes[:null_pos]

            name = name_bytes.decode('utf-8', errors='ignore').strip()

        return ParsedAdvert(
            advert_string=advert_string,
            raw_hex=raw_hex,
            raw_bytes=data,
            format_type="broadcast",
            type=adv_type,
            type_name=type_name,
            flags=flags,
            name=name,
            latitude=latitude,
            longitude=longitude,
        )

    @classmethod
    def validate(cls, meshcore_url: str) -> bool:
        """
        Validate a meshcore:// URL without fully parsing it.

        Args:
            meshcore_url: URL to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            cls.parse(meshcore_url)
            return True
        except (ValueError, Exception):
            return False

    @classmethod
    def extract_public_key(cls, meshcore_url: str) -> Optional[str]:
        """
        Extract public key from meshcore:// URL if present.

        Only works with contact export format. Broadcast format does not
        include the public key.

        Args:
            meshcore_url: URL to parse

        Returns:
            Public key as hex string, or None if not present/not contact export format
        """
        try:
            parsed = cls.parse(meshcore_url)
            return parsed.public_key
        except (ValueError, Exception):
            return None
