"""
MeshCore Advertisement Parser

Parses meshcore:// URLs containing signed advertisement data.

Format (based on meshcore.js):

Packet Header (2 bytes):
  - Byte 0: Header byte
    - Bits 0-1: Route type
    - Bits 2-5: Payload type (4 = Node Advertisement)
    - Bits 6-7: Version
  - Byte 1: Path length

Path (variable, usually 0 bytes)

Advertisement Payload:
  - Public key (32 bytes)
  - Timestamp (4 bytes, uint32 little-endian)
  - Signature (64 bytes, Ed25519)
  - App data (variable):
    - Byte 0: Flags
      - Bits 0-3: Advertisement type (0=None, 1=Chat/Companion, 2=Repeater, 3=Room)
      - Bit 4 (0x10): Location present
      - Bit 5 (0x20): Battery present
      - Bit 6 (0x40): Temperature present
      - Bit 7 (0x80): Name present
    - Latitude (4 bytes, int32 LE) [if flag 0x10 set]
    - Longitude (4 bytes, int32 LE) [if flag 0x10 set]
    - Battery (2 bytes, uint16 LE, millivolts) [if flag 0x20 set]
    - Temperature (2 bytes, int16 LE, celsius * 100) [if flag 0x40 set]
    - Name (remaining bytes, UTF-8 string) [if flag 0x80 set]
"""

import struct
from dataclasses import dataclass
from typing import Optional

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError


# Advertisement type constants (from meshcore.js)
ADV_TYPE_NONE = 0
ADV_TYPE_CHAT = 1  # Also called "Companion"
ADV_TYPE_REPEATER = 2
ADV_TYPE_ROOM = 3
ADV_TYPE_SENSOR = 4  # Sensor node

# Flag masks (from meshcore.js Advert class)
ADV_LATLON_MASK = 0x10  # Bit 4: Location (lat/lon) present
ADV_BATTERY_MASK = 0x20  # Bit 5: Battery voltage present
ADV_TEMPERATURE_MASK = 0x40  # Bit 6: Temperature present
ADV_NAME_MASK = 0x80  # Bit 7: Name present
ADV_TYPE_MASK = 0x0F  # Bits 0-3: Type

# Packet constants
PACKET_PAYLOAD_TYPE_ADVERTISEMENT = 4


@dataclass
class ParsedAdvert:
    """Parsed advertisement data."""

    # Raw data
    advert_string: str  # Full meshcore:// URL
    raw_hex: str  # Hex data after meshcore://
    raw_bytes: bytes  # Raw byte data

    # Format information
    format_type: str  # "contact_export" or "broadcast"

    # Core fields
    public_key: Optional[str] = None  # 32-byte public key (hex string)
    adv_type: Optional[int] = None  # Advertisement type (0-15)
    type_name: Optional[str] = None  # Human-readable type name
    flags: Optional[int] = None  # Flags byte from app data
    name: Optional[str] = None  # Device/contact name

    # Signature and timestamp (from advertisement packet)
    timestamp: Optional[int] = None  # Unix timestamp from packet
    signature: Optional[str] = None  # 64-byte Ed25519 signature (hex string)

    # Location
    latitude: Optional[float] = None  # Latitude in degrees
    longitude: Optional[float] = None  # Longitude in degrees

    # Sensor data
    battery: Optional[int] = None  # Battery voltage in millivolts
    temperature: Optional[float] = None  # Temperature in Celsius

    def verify_signature(self) -> bool:
        """
        Verify the Ed25519 signature of this advertisement.

        The signature covers: public_key + timestamp + app_data
        (This matches the meshcore.js Advert.isVerified() implementation)

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.public_key or not self.signature or self.timestamp is None:
            return False

        try:
            # Convert hex strings to bytes
            public_key_bytes = bytes.fromhex(self.public_key)
            signature_bytes = bytes.fromhex(self.signature)

            # Build the signed message (matches meshcore.js)
            # signed_data = public_key + timestamp + app_data
            timestamp_bytes = struct.pack("<I", self.timestamp)

            # Reconstruct app data from parsed fields
            app_data = self._reconstruct_app_data()

            message = public_key_bytes + timestamp_bytes + app_data

            # Verify signature using PyNaCl
            verify_key = VerifyKey(public_key_bytes)
            verify_key.verify(message, signature_bytes)
            return True

        except (BadSignatureError, ValueError):
            return False

    def _reconstruct_app_data(self) -> bytes:
        """
        Reconstruct the app data bytes from parsed fields.

        This is needed for signature verification.
        """
        if self.flags is None:
            return b""

        app_data = bytes([self.flags])

        # Add optional fields in order
        if self.flags & ADV_LATLON_MASK and self.latitude is not None and self.longitude is not None:
            lat_raw = int(self.latitude * 1e6)
            lon_raw = int(self.longitude * 1e6)
            app_data += struct.pack("<ii", lat_raw, lon_raw)

        if self.flags & ADV_BATTERY_MASK and self.battery is not None:
            app_data += struct.pack("<H", self.battery)

        if self.flags & ADV_TEMPERATURE_MASK and self.temperature is not None:
            temp_raw = int(self.temperature * 100)
            app_data += struct.pack("<h", temp_raw)

        if self.flags & ADV_NAME_MASK and self.name is not None:
            app_data += self.name.encode("utf-8")

        return app_data


class AdvertParser:
    """Parser for MeshCore advertisement URLs."""

    PROTOCOL = "meshcore://"

    TYPE_NAMES = {
        ADV_TYPE_NONE: "None",
        ADV_TYPE_CHAT: "Chat",  # meshcore.js uses "CHAT"
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
        hex_data = meshcore_url[len(cls.PROTOCOL) :]

        if not hex_data:
            raise ValueError("URL contains no data after protocol")

        # Validate hex format
        if not all(c in "0123456789abcdefABCDEF" for c in hex_data):
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
        """
        Parse the raw bytes into advertisement fields.

        Only supports the signed advertisement packet format (payload type 4).
        """

        if len(data) < 2:
            raise ValueError("Data too short for packet header")

        # Check packet header
        # Byte 0: header with payload type in bits 2-5
        header = data[0]
        payload_type = (header >> 2) & 0x0F

        # Only accept Advertisement packets (payload type 4)
        if payload_type != PACKET_PAYLOAD_TYPE_ADVERTISEMENT:
            raise ValueError(
                f"Invalid packet type: expected payload_type=4 (Advertisement), "
                f"got payload_type={payload_type}"
            )

        if len(data) < 100:
            raise ValueError(
                f"Advertisement packet too short: {len(data)} bytes "
                f"(minimum 100 bytes required)"
            )

        return cls._parse_advertisement_packet(advert_string, raw_hex, data)

    @classmethod
    def _parse_advertisement_packet(cls, advert_string: str, raw_hex: str, data: bytes) -> ParsedAdvert:
        """
        Parse modern advertisement packet format (based on meshcore.js).

        Structure:
          - Packet header (2 bytes)
          - Path (variable length, specified in header byte 1)
          - Public key (32 bytes)
          - Timestamp (4 bytes, uint32 LE)
          - Signature (64 bytes)
          - App data (flags + optional fields)
        """

        # Parse packet header
        header = data[0]
        path_len = data[1]

        # Skip path (if any) to get to payload
        payload_offset = 2 + path_len

        if len(data) < payload_offset + 100:  # 32 + 4 + 64 = 100 minimum
            raise ValueError(
                f"Packet too short for advertisement payload: {len(data)} bytes "
                f"(need at least {payload_offset + 100})"
            )

        payload = data[payload_offset:]

        # Parse advertisement payload
        offset = 0

        # Public key (32 bytes)
        public_key = payload[offset : offset + 32].hex()
        offset += 32

        # Timestamp (4 bytes, uint32 LE)
        timestamp = struct.unpack("<I", payload[offset : offset + 4])[0]
        offset += 4

        # Signature (64 bytes)
        signature = payload[offset : offset + 64].hex()
        offset += 64

        # App data starts here
        if len(payload) < offset + 1:
            raise ValueError("No app data present in advertisement")

        app_data = payload[offset:]

        # Parse app data
        flags = app_data[0]
        adv_type = flags & ADV_TYPE_MASK
        type_name = cls.TYPE_NAMES.get(adv_type, f"Unknown({adv_type})")

        app_offset = 1

        # Parse optional fields based on flags
        latitude = None
        longitude = None
        if flags & ADV_LATLON_MASK:
            if len(app_data) < app_offset + 8:
                raise ValueError("Not enough data for location field")
            lat_raw = struct.unpack("<i", app_data[app_offset : app_offset + 4])[0]
            lon_raw = struct.unpack("<i", app_data[app_offset + 4 : app_offset + 8])[0]
            latitude = lat_raw / 1e6
            longitude = lon_raw / 1e6
            app_offset += 8

        battery = None
        if flags & ADV_BATTERY_MASK:
            if len(app_data) < app_offset + 2:
                raise ValueError("Not enough data for battery field")
            battery = struct.unpack("<H", app_data[app_offset : app_offset + 2])[0]
            app_offset += 2

        temperature = None
        if flags & ADV_TEMPERATURE_MASK:
            if len(app_data) < app_offset + 2:
                raise ValueError("Not enough data for temperature field")
            temp_raw = struct.unpack("<h", app_data[app_offset : app_offset + 2])[0]
            temperature = temp_raw / 100.0
            app_offset += 2

        name = None
        if flags & ADV_NAME_MASK:
            if len(app_data) > app_offset:
                name_bytes = app_data[app_offset:]
                name = name_bytes.decode("utf-8", errors="ignore").rstrip("\x00").strip()
                if not name:
                    name = None

        return ParsedAdvert(
            advert_string=advert_string,
            raw_hex=raw_hex,
            raw_bytes=data,
            format_type="advertisement",
            public_key=public_key,
            timestamp=timestamp,
            signature=signature,
            adv_type=adv_type,
            type_name=type_name,
            flags=flags,
            name=name,
            latitude=latitude,
            longitude=longitude,
            battery=battery,
            temperature=temperature,
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
