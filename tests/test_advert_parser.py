"""
Tests for MeshCore advertisement parser.

Tests parsing of meshcore:// URLs in both contact export and broadcast formats.
"""

import pytest
from coretact.meshcore.parser import AdvertParser, ParsedAdvert


class TestContactExportFormat:
    """Tests for contact export format (meshcore:// URLs shared by users)."""

    # Real contact export from egrme.sh with valid location (Austin, TX)
    VALID_CONTACT_EXPORT = (
        "meshcore://110055365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d6608"
        "7df2d9ee68a9d311a998dd4e3ebea8a03432539e0a5c35dfe94f7a0c8665181e70d17dde"
        "f51b7b5f2704a6fdd2fde47d3edf2057cfb3a874df8d394ac494ed646173fcdb0a91f7fc"
        "cc01e4462cfa6567726d652e736820436f7265"
    )

    EXPECTED_PUBLIC_KEY = "55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d"
    EXPECTED_NAME = "egrme.sh Core"
    EXPECTED_LATITUDE = 30.211319
    EXPECTED_LONGITUDE = -97.761564

    def test_parse_valid_contact_export(self):
        """Test parsing a valid contact export URL."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        assert parsed is not None
        assert isinstance(parsed, ParsedAdvert)
        assert parsed.format_type == "advertisement"

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

        assert parsed.adv_type is not None
        assert isinstance(parsed.adv_type, int)
        assert parsed.flags is not None
        assert isinstance(parsed.flags, int)

    def test_extract_timestamp_and_signature(self):
        """Test extracting timestamp and signature from modern advertisement format."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        # Modern advertisement format has timestamp and signature
        assert parsed.timestamp is not None
        assert isinstance(parsed.timestamp, int)
        assert parsed.signature is not None
        assert len(parsed.signature) == 128  # 64 bytes as hex string

    def test_extract_location(self):
        """Test extracting location data from advertisement."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        # Should have valid location data (Austin, TX)
        assert parsed.latitude is not None
        assert parsed.longitude is not None
        assert abs(parsed.latitude - self.EXPECTED_LATITUDE) < 0.000001
        assert abs(parsed.longitude - self.EXPECTED_LONGITUDE) < 0.000001

    def test_verify_signature(self):
        """Test Ed25519 signature verification."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        # Real advertisement should have valid signature
        assert parsed.verify_signature() is True

    def test_verify_signature_tampered(self):
        """Test that signature verification fails if data is tampered."""
        parsed = AdvertParser.parse(self.VALID_CONTACT_EXPORT)

        # Tamper with the name
        original_name = parsed.name
        parsed.name = "Tampered Name"

        # Signature should now be invalid
        assert parsed.verify_signature() is False

        # Restore original
        parsed.name = original_name
        assert parsed.verify_signature() is True

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
        assert parsed.raw_hex == self.VALID_CONTACT_EXPORT.replace("meshcore://", "")
        assert len(parsed.raw_bytes) > 0


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

    def test_minimal_valid_advertisement(self):
        """Test parsing minimal valid advertisement packet."""
        # Packet header (2 bytes) + public key (32) + timestamp (4) + signature (64) + app data (1)
        # Total = 103 bytes minimum
        minimal = (
            "meshcore://1100"  # Packet header (route=1, type=4, version=0, path_len=0)
            + "00" * 32  # Public key (32 bytes)
            + "00000000"  # Timestamp (4 bytes)
            + "00" * 64  # Signature (64 bytes)
            + "01"  # App data: flags (type=1, no optional fields)
        )

        parsed = AdvertParser.parse(minimal)
        assert parsed.format_type == "advertisement"
        assert parsed.public_key == "00" * 32

    def test_advertisement_with_no_name(self):
        """Test advertisement where name flag is not set."""
        # Advertisement with type but no name
        no_name = (
            "meshcore://1100"  # Packet header
            + "11" * 32  # Public key (32 bytes)
            + "00000000"  # Timestamp (4 bytes)
            + "00" * 64  # Signature (64 bytes)
            + "01"  # App data: flags (type=1, no name flag)
        )

        parsed = AdvertParser.parse(no_name)
        assert parsed.name is None

    def test_case_insensitive_hex(self):
        """Test that hex parsing is case-insensitive."""
        # Create valid advertisement packets with different case hex
        # Packet header (2) + public key (32) + timestamp (4) + signature (64) + app data (1) = 103
        lower = "meshcore://1100" + "aa" * 32 + "00000000" + "00" * 64 + "01"
        upper = "meshcore://1100" + "AA" * 32 + "00000000" + "00" * 64 + "01"
        mixed = "meshcore://1100" + "Aa" * 32 + "00000000" + "00" * 64 + "01"

        parsed_lower = AdvertParser.parse(lower)
        parsed_upper = AdvertParser.parse(upper)
        parsed_mixed = AdvertParser.parse(mixed)

        assert parsed_lower.public_key == parsed_upper.public_key
        assert parsed_lower.public_key == parsed_mixed.public_key
        assert parsed_lower.public_key == "aa" * 32  # Normalized to lowercase


class TestDataTypes:
    """Tests for data type handling."""

    def test_public_key_is_lowercase_hex(self):
        """Test that public key is returned as lowercase hex string."""
        # Valid advertisement packet with uppercase hex in public key
        # Packet header (2) + Public key (32) + timestamp (4) + signature (64) + app data (1)
        url = (
            "meshcore://1100"
            + "ABCD" * 16  # Public key (uppercase, 32 bytes)
            + "00000000"  # Timestamp
            + "00" * 64  # Signature
            + "01"  # App data
        )
        parsed = AdvertParser.parse(url)

        assert parsed.public_key is not None
        assert parsed.public_key.islower()
        assert all(c in "0123456789abcdef" for c in parsed.public_key)

    def test_location_data_types(self):
        """Test that location fields are floats when present."""
        # Advertisement with location data
        with_location = (
            "meshcore://1100"
            + "00" * 32  # Public key (32 bytes)
            + "00000000"  # Timestamp (4 bytes)
            + "00" * 64  # Signature (64 bytes)
            + "11"  # Flags: type=1, location=yes (0x10 | 0x01 = 0x11)
            + "E8030000"  # Latitude (1000 = 0.001 degrees when /1e6)
            + "E8030000"  # Longitude (1000 = 0.001 degrees when /1e6)
        )

        parsed = AdvertParser.parse(with_location)

        assert parsed.latitude is not None
        assert parsed.longitude is not None
        assert isinstance(parsed.latitude, float)
        assert isinstance(parsed.longitude, float)
        assert abs(parsed.latitude - 0.001) < 0.000001
        assert abs(parsed.longitude - 0.001) < 0.000001

    def test_timestamp_data_types(self):
        """Test that timestamp field is integer when present."""
        with_timestamp = (
            "meshcore://1100"
            + "00" * 32  # Public key (32 bytes)
            + "01020304"  # Timestamp: 0x04030201 = 67305985 (little-endian uint32)
            + "00" * 64  # Signature (64 bytes)
            + "01"  # Flags: type=1
        )

        parsed = AdvertParser.parse(with_timestamp)

        assert parsed.timestamp is not None
        assert isinstance(parsed.timestamp, int)
        assert parsed.timestamp == 67305985  # 0x04030201 in little-endian


class TestQRCodeContactFormat:
    """Tests for QR code contact format (meshcore://contact/add?...)."""

    # Example QR code format URL
    VALID_QR_CONTACT = (
        "meshcore://contact/add?name=egrme.sh+Core&"
        "public_key=55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d&"
        "type=1"
    )

    EXPECTED_PUBLIC_KEY = "55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d"
    EXPECTED_NAME = "egrme.sh Core"
    EXPECTED_TYPE = 1

    def test_parse_valid_qr_contact(self):
        """Test parsing a valid QR code contact URL."""
        parsed = AdvertParser.parse(self.VALID_QR_CONTACT)

        assert parsed is not None
        assert isinstance(parsed, ParsedAdvert)
        assert parsed.format_type == "qr_contact"

    def test_extract_public_key_from_qr(self):
        """Test extracting public key from QR code format."""
        parsed = AdvertParser.parse(self.VALID_QR_CONTACT)

        assert parsed.public_key == self.EXPECTED_PUBLIC_KEY
        assert len(parsed.public_key) == 64

    def test_extract_name_from_qr(self):
        """Test extracting name from QR code format (handles + as space)."""
        parsed = AdvertParser.parse(self.VALID_QR_CONTACT)

        assert parsed.name == self.EXPECTED_NAME

    def test_extract_type_from_qr(self):
        """Test extracting type from QR code format."""
        parsed = AdvertParser.parse(self.VALID_QR_CONTACT)

        assert parsed.adv_type == self.EXPECTED_TYPE
        assert parsed.type_name == "Chat"

    def test_qr_format_has_no_signature(self):
        """Test that QR format doesn't have signature/timestamp fields."""
        parsed = AdvertParser.parse(self.VALID_QR_CONTACT)

        assert parsed.timestamp is None
        assert parsed.signature is None
        assert parsed.flags is None
        assert parsed.latitude is None
        assert parsed.longitude is None
        assert parsed.battery is None
        assert parsed.temperature is None

    def test_qr_format_missing_name(self):
        """Test QR format with missing name parameter."""
        url = (
            "meshcore://contact/add?public_key=55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d&type=1"
        )
        with pytest.raises(ValueError, match="Missing required parameter: name"):
            AdvertParser.parse(url)

    def test_qr_format_missing_public_key(self):
        """Test QR format with missing public_key parameter."""
        url = "meshcore://contact/add?name=Test&type=1"
        with pytest.raises(ValueError, match="Missing required parameter: public_key"):
            AdvertParser.parse(url)

    def test_qr_format_missing_type(self):
        """Test QR format with missing type parameter."""
        url = "meshcore://contact/add?name=Test&public_key=55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d"
        with pytest.raises(ValueError, match="Missing required parameter: type"):
            AdvertParser.parse(url)

    def test_qr_format_invalid_public_key_length(self):
        """Test QR format with invalid public key length."""
        url = "meshcore://contact/add?name=Test&public_key=1234&type=1"
        with pytest.raises(ValueError, match="Invalid public key length"):
            AdvertParser.parse(url)

    def test_qr_format_invalid_public_key_chars(self):
        """Test QR format with invalid characters in public key."""
        url = "meshcore://contact/add?name=Test&public_key=" + "ZZ" * 32 + "&type=1"
        with pytest.raises(ValueError, match="invalid hex characters"):
            AdvertParser.parse(url)

    def test_qr_format_invalid_type(self):
        """Test QR format with invalid type value."""
        url = "meshcore://contact/add?name=Test&public_key=55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d&type=abc"
        with pytest.raises(ValueError, match="Invalid type value"):
            AdvertParser.parse(url)

    def test_qr_format_type_out_of_range(self):
        """Test QR format with type out of valid range."""
        url = "meshcore://contact/add?name=Test&public_key=55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d&type=10"
        with pytest.raises(ValueError, match="Type out of range"):
            AdvertParser.parse(url)

    def test_qr_format_name_url_decoding(self):
        """Test that QR format properly decodes URL-encoded names."""
        # Test with + for spaces
        url1 = "meshcore://contact/add?name=Test+Device+Name&public_key=55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d&type=1"
        parsed1 = AdvertParser.parse(url1)
        assert parsed1.name == "Test Device Name"

        # Test with %20 for spaces
        url2 = "meshcore://contact/add?name=Test%20Device%20Name&public_key=55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d&type=1"
        parsed2 = AdvertParser.parse(url2)
        assert parsed2.name == "Test Device Name"

    def test_qr_format_uppercase_public_key(self):
        """Test that QR format normalizes uppercase public keys to lowercase."""
        url = "meshcore://contact/add?name=Test&public_key=ABCD" + "EF01" * 15 + "&type=1"
        parsed = AdvertParser.parse(url)
        assert parsed.public_key == ("abcd" + "ef01" * 15)
        assert parsed.public_key.islower()

    def test_public_key_extraction_from_qr(self):
        """Test the extract_public_key convenience method with QR format."""
        public_key = AdvertParser.extract_public_key(self.VALID_QR_CONTACT)
        assert public_key == self.EXPECTED_PUBLIC_KEY

    def test_validate_method_with_qr(self):
        """Test the validate convenience method with QR format."""
        assert AdvertParser.validate(self.VALID_QR_CONTACT) is True


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
        assert parsed1.adv_type == parsed2.adv_type
        assert parsed1.flags == parsed2.flags


class TestFormatDetection:
    """Tests for automatic format detection."""

    def test_detect_binary_format(self):
        """Test that binary format is properly detected."""
        # Minimal binary advertisement
        binary_url = "meshcore://1100" + "00" * 32 + "00000000" + "00" * 64 + "01"
        parsed = AdvertParser.parse(binary_url)
        assert parsed.format_type == "advertisement"

    def test_detect_qr_format(self):
        """Test that QR code format is properly detected."""
        qr_url = "meshcore://contact/add?name=Test&public_key=" + "11" * 32 + "&type=1"
        parsed = AdvertParser.parse(qr_url)
        assert parsed.format_type == "qr_contact"

    def test_unsupported_format(self):
        """Test that unsupported format raises appropriate error."""
        unsupported_url = "meshcore://unknown/format"
        # Non-QR formats are assumed to be binary hex, so invalid characters
        # will trigger the hex validation error
        with pytest.raises(ValueError, match="invalid hex characters"):
            AdvertParser.parse(unsupported_url)
