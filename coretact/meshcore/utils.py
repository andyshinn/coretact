"""Utilities for working with meshcore advertisements."""

from typing import Dict, Any

from coretact.meshcore.parser import AdvertParser, ParsedAdvert


def decode_advert_to_dict(advert_url: str) -> Dict[str, Any]:
    """
    Decode a meshcore advertisement URL to a dictionary.

    This is a shared utility used by both the API endpoint and CLI command
    to ensure consistent output format.

    Args:
        advert_url: The meshcore:// URL to decode

    Returns:
        Dictionary containing all decoded fields

    Raises:
        ValueError: If the URL cannot be parsed
    """
    parsed = AdvertParser.parse(advert_url)
    return parsed_advert_to_dict(parsed)


def parsed_advert_to_dict(parsed: ParsedAdvert) -> Dict[str, Any]:
    """
    Convert a ParsedAdvert object to a dictionary.

    This creates a consistent dictionary representation of the parsed
    advertisement data, including all available fields.

    Args:
        parsed: ParsedAdvert object

    Returns:
        Dictionary with all available fields
    """
    # Build response with always-present fields
    result: Dict[str, Any] = {
        "format_type": parsed.format_type,
        "public_key": parsed.public_key,
        "name": parsed.name,
        "adv_type": parsed.adv_type,
        "type_name": parsed.type_name,
    }

    # Add optional fields (only if present)
    if parsed.timestamp is not None:
        result["timestamp"] = parsed.timestamp

    if parsed.signature is not None:
        result["signature"] = parsed.signature
        # Verify signature for formats that support it
        result["signature_valid"] = parsed.verify_signature()

    if parsed.flags is not None:
        result["flags"] = parsed.flags

    if parsed.latitude is not None:
        result["latitude"] = parsed.latitude

    if parsed.longitude is not None:
        result["longitude"] = parsed.longitude

    if parsed.battery is not None:
        result["battery"] = parsed.battery

    if parsed.temperature is not None:
        result["temperature"] = parsed.temperature

    return result
