"""
Tests for MeshCore advertisement parser.

Tests parsing of meshcore:// URLs in both contact export and broadcast formats.
"""

import pytest
from coretact.meshcore.parser import AdvertParser, ParsedAdvert


class TestContactExportFormat:
    """Tests for contact export format (meshcore:// URLs shared by users)."""

    # Real contact export from egrme.sh
    VALID_CONTACT_EXPORT = (
        'meshcore://110055365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d6608'
        '7d5045ec6872ee07b881c8a3ab5e25e62430cdb8bbb4b7b415e0a208084424942f1b26dc'
        'dd315c9eccf86d81bbf960642c4c1e385ec5ab1a98471e4134006e0ef5b715120c910000'
        '0000000000006567726d652e736820436f7265'
    )

    EXPECTED_PUBLIC_KEY = '55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d'
    EXPECTED_NAME = 'egrme.sh Core'

    def test_parse_valid_contact_export(self):
        """Test parsing a valid contact export URL."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        assert parsed is not None
        assert isinstance(parsed, ParsedAdvert)
        assert parsed.format_type == "contact_export"

    def test_extract_public_key(self):
        """Test extracting public key from contact export."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        assert parsed.public_key == self.EXPECTED_PUBLIC_KEY
        assert len(parsed.public_key) == 64  # 32 bytes as hex string

    def test_extract_name(self):
        """Test extracting device name from contact export."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        assert parsed.name == self.EXPECTED_NAME
        assert len(parsed.name) > 0

    def test_extract_type_and_flags(self):
        """Test extracting type and flags."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        assert parsed.type is not None
        assert isinstance(parsed.type, int)
        assert parsed.flags is not None
        assert isinstance(parsed.flags, int)

    def test_extract_out_path(self):
        """Test extracting out_path information."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        assert parsed.out_path_len is not None
        # out_path may be None if path_len is 0 or -1

    def test_public_key_extraction_method(self):
        """Test the extract_public_key convenience method."""
        public_key = AdvertParser.extract_public_key(self.VALID_CONTACT_EXPORT)

        assert public_key == self.EXPECTED_PUBLIC_KEY

    def test_validate_method(self):
        """Test the validate convenience method."""
        assert AdvertParser.validate(self.VALID_CONTACT_EXPORT) is True

    def test_raw_data_preserved(self):
        """Test that raw data is preserved in parsed result."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        assert parsed.advert_string == self.VALID_CONTACT_EXPORT
        assert parsed.raw_hex == self.VALID_CONTACT_EXPORT.replace('meshcore://', '')
        assert len(parsed.raw_bytes) > 0


class TestBroadcastFormat:
    """Tests for broadcast advertisement format."""

    # Example broadcast format with location and name
    BROADCAST_WITH_LOCATION = (
        'meshcore://91'  # Type 1 (companion) with location and name flags
        '00000000'  # Latitude (0.0)
        '00000000'  # Longitude (0.0)
        '54657374'  # Name: "Test"
        '00'        # Null terminator
    )

    def test_parse_broadcast_format(self):
        """Test parsing broadcast format (shorter than contact export)."""
        parsed = AdvertParser.parse(self.BROADCAST_WITH_LOCATION)

        assert parsed.format_type == "broadcast"
        assert parsed.type == 1  # Companion
        assert parsed.latitude is not None
        assert parsed.name is not None

    def test_broadcast_no_public_key(self):
        """Test that broadcast format doesn't have public key."""
        parsed = AdvertParser.parse(self.BROADCAST_WITH_LOCATION)

        assert parsed.public_key is None


class TestErrorHandling:
    """Tests for error handling and validation."""

    def test_empty_url(self):
        """Test parsing empty URL raises ValueError."""
        with pytest.raises(ValueError, match="URL must be a non-empty string"):
            AdvertParser.parse("")

    def test_none_url(self):
        """Test parsing None raises ValueError."""
        with pytest.raises(ValueError, match="URL must be a non-empty string"):
            AdvertParser.parse(None)

    def test_invalid_protocol(self):
        """Test parsing URL with wrong protocol raises ValueError."""
        with pytest.raises(ValueError, match="URL must start with meshcore://"):
            AdvertParser.parse("https://example.com")

    def test_no_data_after_protocol(self):
        """Test parsing URL with no data after protocol."""
        with pytest.raises(ValueError, match="URL contains no data after protocol"):
            AdvertParser.parse("meshcore://")

    def test_invalid_hex_characters(self):
        """Test parsing URL with invalid hex characters."""
        with pytest.raises(ValueError, match="invalid hex characters"):
            AdvertParser.parse("meshcore://ZZZZ")

    def test_odd_length_hex(self):
        """Test parsing URL with odd-length hex string."""
        with pytest.raises(ValueError, match="Failed to decode hex data"):
            AdvertParser.parse("meshcore://123")  # Odd length

    def test_too_short_data(self):
        """Test parsing URL with insufficient data."""
        with pytest.raises(ValueError):
            AdvertParser.parse("meshcore://11")  # Only 1 byte

    def test_validate_returns_false_for_invalid(self):
        """Test that validate returns False for invalid URLs."""
        assert AdvertParser.validate("invalid") is False
        assert AdvertParser.validate("meshcore://ZZZ") is False
        assert AdvertParser.validate("") is False

    def test_extract_public_key_returns_none_for_invalid(self):
        """Test that extract_public_key returns None for invalid URLs."""
        assert AdvertParser.extract_public_key("invalid") is None
        assert AdvertParser.extract_public_key("meshcore://11") is None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_minimal_valid_contact_export(self):
        """Test parsing minimal valid contact export (header + public key + minimal data)."""
        # Header (2 bytes) + public key (32 bytes) + minimal contact data (89 bytes)
        # Total must be >= 123 bytes to be detected as contact_export
        minimal = (
            'meshcore://1100'  # Header (2 bytes)
            + '00' * 32         # Public key (32 bytes)
            + '00' * 89         # Minimal contact data (89 bytes) = 123 total
        )

        parsed = AdvertParser.parse(minimal)
        assert parsed.format_type == "contact_export"
        assert parsed.public_key == '00' * 32

    def test_contact_export_with_no_name(self):
        """Test contact export where name field is all null bytes."""
        # This should handle gracefully
        no_name = (
            'meshcore://1100'
            + '11' * 32  # Public key
            + '01'       # Type
            + '00'       # Flags
            + 'FF'       # path_len = -1
            + '00' * 64  # Out path
            + '00' * 32  # Name (all nulls)
        )

        parsed = AdvertParser.parse(no_name)
        assert parsed.name is None or parsed.name == ''

    def test_case_insensitive_hex(self):
        """Test that hex parsing is case-insensitive."""
        lower = 'meshcore://1100' + 'aa' * 32 + '00' * 77
        upper = 'meshcore://1100' + 'AA' * 32 + '00' * 77
        mixed = 'meshcore://1100' + 'Aa' * 32 + '00' * 77

        parsed_lower = AdvertParser.parse(lower)
        parsed_upper = AdvertParser.parse(upper)
        parsed_mixed = AdvertParser.parse(mixed)

        assert parsed_lower.public_key == parsed_upper.public_key
        assert parsed_lower.public_key == parsed_mixed.public_key


class TestDataTypes:
    """Tests for data type handling."""

    def test_public_key_is_lowercase_hex(self):
        """Test that public key is returned as lowercase hex string."""
        # Must be >= 123 bytes to be contact_export format
        # Header (2) + Public key (32) + padding (89) = 123 bytes
        url = 'meshcore://1100' + 'ABCD' * 16 + '00' * 89  # 16 * 2 = 32 bytes for pubkey
        parsed = AdvertParser.parse(url)

        assert parsed.public_key is not None
        assert parsed.public_key.islower()
        assert all(c in '0123456789abcdef' for c in parsed.public_key)

    def test_location_data_types(self):
        """Test that location fields are floats when present."""
        # Contact export with location data
        with_location = (
            'meshcore://1100'
            + '00' * 32  # Public key
            + '01'       # Type
            + '00'       # Flags
            + 'FF'       # path_len
            + '00' * 64  # Out path
            + '00' * 32  # Name
            + '00' * 4    # last_advert
            + 'E8030000'  # Latitude (1000 * 1E6 = 0.001)
            + 'E8030000'  # Longitude
        )

        parsed = AdvertParser.parse(with_location)

        if parsed.latitude is not None:
            assert isinstance(parsed.latitude, float)
            assert isinstance(parsed.longitude, float)

    def test_timestamp_data_types(self):
        """Test that timestamp fields are integers when present."""
        with_timestamps = (
            'meshcore://1100'
            + '00' * 32  # Public key
            + '01'       # Type
            + '00'       # Flags
            + 'FF'        # path_len
            + '00' * 64   # Out path
            + '00' * 32   # Name
            + '01020304'  # last_advert (little-endian uint32)
            + '00' * 8    # Location
            + '05060708'  # lastmod
        )

        parsed = AdvertParser.parse(with_timestamps)

        if parsed.last_advert is not None:
            assert isinstance(parsed.last_advert, int)
        if parsed.last_modified is not None:
            assert isinstance(parsed.last_modified, int)


class TestRealWorldExamples:
    """Tests using real-world advertisement examples."""

    def test_multiple_real_adverts(self):
        """Test that parser handles multiple real-world examples."""
        # This would be expanded with more real examples as we collect them
        real_adverts = [
            TestContactExportFormat.VALID_CONTACT_EXPORT,
        ]

        for advert in real_adverts:
            parsed = AdvertParser.parse(advert)
            assert parsed is not None
            assert parsed.public_key is not None
            assert len(parsed.public_key) == 64

    def test_parser_is_deterministic(self):
        """Test that parser produces same result when called multiple times."""
        url = TestContactExportFormat.VALID_CONTACT_EXPORT

        parsed1 = AdvertParser.parse(url)
        parsed2 = AdvertParser.parse(url)

        assert parsed1.public_key == parsed2.public_key
        assert parsed1.name == parsed2.name
        assert parsed1.type == parsed2.type
        assert parsed1.flags == parsed2.flags
