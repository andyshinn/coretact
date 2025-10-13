# Coretact - Meshcore Contact Management System

## Project Overview

Coretact is a contact management application for Meshcore devices that allows users to:
- Store and share their device advertisements via Discord
- Download contact lists as JSON files
- Search and filter contacts by various criteria
- Sync contacts directly to devices via Bluetooth or Serial (future web feature)

## Architecture

### Components

1. **Discord Bot** - Primary interface for users to manage their adverts
2. **Web API** - REST API for downloading and searching contacts
3. **Shared Core Logic** - Advertisement parsing, validation, and filtering
4. **Storage Layer** - File-based storage using datafiles library

### Technology Stack

- **Language**: Python 3.11+
- **Discord Bot**: discord.py
- **Web Server**: aiohttp
- **Data Serialization**: datafiles (https://datafiles.readthedocs.io/)
- **Data Models**: Native Python dataclasses
- **Storage**: File-based (JSON)

## Advertisement Format Analysis

Based on the example advertisement:
```
meshcore://110055365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d973cec687b840a38bc6efafd2ae4ecb248e1cdf15303447ba635df1afc1ae6aee261694dc657ce783a06d8e344012fa95eb744def387ecdb1aea00d500fcfc3aa917970f9100000000000000006567726d652e736820436f7265
```

Structure (hex-encoded after `meshcore://`):
- **Byte 0**: Type and flags (`0x11` = type 1 with flags)
- **Bytes 1-32**: Public key (32 bytes / 64 hex chars)
- **Remaining bytes**: Optional fields (location, features, name)

The public key in the example starts at position 4 in the hex string (byte offset 2).

## Data Models

### Advert Model (Stored on Disk)

```python
@dataclass
class Advert:
    public_key: str              # 64-char hex string (32 bytes)
    discord_server_id: str       # Discord guild ID
    discord_user_id: str         # Discord user ID
    advert_string: str           # Full meshcore:// URL
    type: int                    # Device type (1=companion, 2=repeater, 3=room)
    name: str                    # Device name extracted from advert
    latitude: Optional[float]    # Location if present
    longitude: Optional[float]   # Location if present
    flags: int                   # Parsed flags from advert
    out_path: Optional[str]      # Extracted from advert data
    created_at: datetime         # When advert was added
    updated_at: datetime         # Last update timestamp
```

### Contact Model (API Response)

```python
@dataclass
class Contact:
    type: int
    name: str
    custom_name: Optional[str]
    public_key: str
    flags: int
    latitude: str
    longitude: str
    last_advert: int             # Unix timestamp
    last_modified: int           # Unix timestamp
    out_path: Optional[str]
```

### Contacts List Response

```python
@dataclass
class ContactsList:
    contacts: List[Contact]
```

## Storage Structure

```
/storage/
  ├── <discord_server_id>/
  │   ├── <discord_user_id>/
  │   │   ├── <public_key>.json
  │   │   └── ...
  │   └── ...
  └── ...
```

Each advert is stored as a separate JSON file named by its public key. This allows:
- Easy lookups by public key
- Per-user organization
- Per-server isolation
- Efficient file-based queries

## Discord Bot Features

### Architecture

The bot follows a Cog-based architecture:
- **bot.py**: Bot initialization, intents setup, and extension loading
- **cogs/coretact.py**: Main Cog implementing the `/coretact` command group using `commands.GroupCog`
- Commands are organized as app_commands within the Cog
- The Cog has a `setup()` function to register it with the bot

### Slash Commands

All commands use the `/coretact` prefix to ensure global uniqueness across Discord.

1. **`/coretact add <meshcore_url>`**
   - Parse and validate the meshcore:// URL
   - Extract public key, type, name, location, etc.
   - Store advert to `/storage/<server_id>/<user_id>/<public_key>.json`
   - Respond with confirmation and parsed details

2. **`/coretact update <meshcore_url>`**
   - Same as add, but overwrites existing advert
   - Updates the `updated_at` timestamp

3. **`/coretact remove [public_key]`**
   - Remove user's own advert(s)
   - If no public_key specified, list user's adverts to choose from
   - Admins can remove any advert in their server

4. **`/coretact list [user]`**
   - List all adverts for the current user (or specified user)
   - Show: public_key, name, type, last_updated

5. **`/coretact search [type] [key_prefix] [name]`**
   - Search all adverts in the current server
   - Filter by:
     - `type`: companion (1), repeater (2), room (3)
     - `key_prefix`: First N characters of public key
     - `name`: Partial name match (case-insensitive)
   - Return paginated results

6. **`/coretact download [format] [filters...]`**
   - Generate and upload a contacts JSON file
   - `format`: json (default), csv (future)
   - Apply same filters as search command
   - Returns file attachment

7. **`/coretact info`**
   - Show statistics for current server (mesh)
   - Total adverts, breakdown by type, active users

### Permissions

- All users can add/update/remove their own adverts
- All users can search and download
- Server admins can remove any advert
- Bot owner can clear all data for a server (emergency)

## Web API Features

### Endpoints

#### `GET /health`
- Health check endpoint
- Returns: `{"status": "ok", "version": "1.0.0"}`

#### `GET /api/v1/mesh/<server_id>/contacts`
- Get all contacts for a mesh (Discord server)
- Query params:
  - `type`: Filter by type (1, 2, or 3)
  - `key_prefix`: Filter by public key prefix
  - `name`: Filter by name (partial match)
  - `user_id`: Filter by Discord user ID
- Returns: ContactsList JSON

#### `GET /api/v1/contact/<public_key>`
- Get a single contact by public key
- Searches across all meshes to find the advert
- Returns: Single Contact JSON with additional fields:
  ```json
  {
    "type": 1,
    "name": "egrme.sh Core",
    "custom_name": null,
    "public_key": "55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d",
    "flags": 0,
    "latitude": "0.0",
    "longitude": "0.0",
    "last_advert": 1760299414,
    "last_modified": 1760299413,
    "out_path": "",
    "advert_string": "meshcore://110055365953...",
    "discord_server_id": "123456789",
    "discord_user_id": "987654321"
  }
  ```
- Returns 404 if public key not found

#### `POST /api/v1/mesh/<server_id>/contacts/bulk`
- Get specific contacts by public keys
- Request body:
  ```json
  {
    "public_keys": ["55365953...", "83c3e551..."],
    "include_metadata": true
  }
  ```
- Returns: ContactsList JSON with only matching contacts

#### `GET /api/v1/mesh/<server_id>/user/<user_id>/contacts`
- Get all contacts for a specific Discord user
- Returns: ContactsList JSON

#### `GET /api/v1/mesh/<server_id>/stats`
- Get statistics for a mesh
- Returns:
  ```json
  {
    "server_id": "...",
    "total_adverts": 42,
    "by_type": {
      "companion": 25,
      "repeater": 10,
      "room": 7
    },
    "unique_users": 15,
    "last_updated": 1760299414
  }
  ```

### CORS Configuration

- Allow all origins for GET requests
- Restrict POST requests to known origins (future web UI)

## Shared Core Logic (`coretact/advert.py`)

### Advertisement Parser

```python
class AdvertParser:
    @staticmethod
    def parse(meshcore_url: str) -> ParsedAdvert:
        """
        Parse a meshcore:// URL into structured data.

        Raises:
        - ValueError: If URL is invalid or cannot be parsed
        """
        pass

    @staticmethod
    def validate(meshcore_url: str) -> bool:
        """Validate meshcore:// URL format."""
        pass

    @staticmethod
    def extract_public_key(meshcore_url: str) -> str:
        """Extract the 64-char hex public key."""
        pass
```

### Contact Filter

```python
class ContactFilter:
    @staticmethod
    def filter_adverts(
        adverts: List[Advert],
        type: Optional[int] = None,
        key_prefix: Optional[str] = None,
        name: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> List[Advert]:
        """Apply filters to a list of adverts."""
        pass
```

### Contact Converter

```python
class ContactConverter:
    @staticmethod
    def advert_to_contact(advert: Advert) -> Contact:
        """Convert Advert model to Contact model for API responses."""
        pass

    @staticmethod
    def adverts_to_contacts_list(adverts: List[Advert]) -> ContactsList:
        """Convert multiple adverts to ContactsList."""
        pass
```

## Implementation Phases

### Phase 1: Core Foundation
1. Set up project structure
2. Implement advertisement parser (`coretact/advert.py`)
3. Define data models
4. Set up datafiles storage layer
5. Write unit tests for parser

### Phase 2: Discord Bot (MVP)
1. Set up discord.py bot
2. Implement `/coretact add` command
3. Implement `/coretact list` command
4. Implement `/coretact remove` command
5. Test with real Discord server

### Phase 3: Discord Bot (Full Features)
1. Implement `/coretact search` command
2. Implement `/coretact download` command
3. Implement `/coretact info` command
4. Add pagination for list/search results
5. Add error handling and user feedback

### Phase 4: Web API (Core)
1. Set up aiohttp server
2. Implement health check endpoint
3. Implement mesh contacts endpoint (GET)
4. Implement bulk contacts endpoint (POST)
5. Add CORS middleware

### Phase 5: Web API (Extended)
1. Implement user contacts endpoint
2. Implement mesh stats endpoint
3. Add rate limiting
4. Add API documentation (OpenAPI/Swagger)

### Phase 6: Production Readiness
1. Add comprehensive logging
2. Set up monitoring/metrics
3. Add Docker configuration
4. Write deployment documentation
5. Set up CI/CD pipeline

### Future Enhancements
- Web UI for browsing contacts
- Bluetooth/Serial sync in browser (Web Bluetooth API)
- Contact QR code generation
- Contact expiration/cleanup
- User profiles and avatars
- Contact verification system
- Import/export from other formats

## Configuration

### Environment Variables

```bash
# Discord
DISCORD_BOT_TOKEN=your_token_here

# Web API
WEB_API_HOST=0.0.0.0
WEB_API_PORT=8080
WEB_API_CORS_ORIGINS=*

# Storage
STORAGE_PATH=/storage

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## File Structure

```
coretact/
├── docs/
│   └── plan.md                 # This file
├── coretact/
│   ├── __init__.py
│   ├── __main__.py            # Entry point
│   ├── config.py              # Configuration management
│   ├── models.py              # Data models
│   ├── advert.py              # Advertisement parsing & filtering
│   ├── storage.py             # Storage layer (datafiles)
│   ├── bot.py                 # Discord bot initialization
│   ├── cogs/
│   │   ├── __init__.py
│   │   └── coretact.py        # Coretact command group cog
│   └── api/
│       ├── __init__.py
│       ├── server.py          # aiohttp server
│       ├── routes.py          # API routes
│       └── middleware.py      # CORS, error handling
├── tests/
│   ├── __init__.py
│   ├── test_advert.py
│   ├── test_storage.py
│   ├── test_bot.py
│   └── test_api.py
├── storage/                   # Git-ignored data directory
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Testing Strategy

### Unit Tests
- Advertisement parser with various valid/invalid inputs
- Filter logic with edge cases
- Model validation
- Storage operations

### Integration Tests
- Discord command workflows
- API endpoint responses
- Storage persistence

### Manual Testing
- Real Discord server testing
- API calls with curl/Postman
- Performance testing with large datasets

## Security Considerations

1. **Input Validation**
   - Validate all meshcore:// URLs before parsing
   - Sanitize Discord user inputs
   - Limit file upload sizes

2. **Rate Limiting**
   - Per-user rate limits on Discord commands
   - Per-IP rate limits on API endpoints
   - Global rate limits to prevent abuse

3. **Access Control**
   - Discord users can only modify their own adverts
   - API is read-only (no write access)
   - Server admins have elevated permissions

4. **Data Privacy**
   - Store only public information (adverts are public by design)
   - No personal data beyond Discord IDs
   - Allow users to remove their data

## Open Questions - RESOLVED

### 1. Advertisement Parsing Details ✅ RESOLVED

**Decision:** Implemented custom parser in `coretact/meshcore/parser.py`

**Implementation:**
- Successfully parses Contact Export Format (meshcore:// URLs)
- Extracts: public_key (32 bytes), name, type, flags, location, timestamps, out_path
- Format: 2-byte header (0x11, 0x00) + 32-byte public key + contact data
- Based on RESP_CODE_CONTACT packet format from Companion Radio Protocol
- Tested with real adverts and working correctly

**Key Findings:**
- Export format != ContactInfo struct (different field ordering)
- Wire format optimized for transmission efficiency
- meshcore_py source code used as reference for byte offsets
- Parser handles both Contact Export and Broadcast Advertisement formats

**Files:**
- Implementation: `coretact/meshcore/parser.py`
- Tests: `tests/test_advert_parser.py`
- Reference: JavaScript parser at `/Users/andy/GitHub/andyshinn/tenfour/src/services/DeepLinkParser.js`

### 2. meshcore_py Library ✅ RESOLVED

**Decision:** Do NOT use meshcore_py for parsing

**Reasoning:**
- meshcore_py requires connected hardware (BLE/Serial/TCP connection)
- Designed for real-time device communication, not offline parsing
- We need standalone parsing without hardware dependencies

**Value Provided:**
- Used source code as reference for understanding binary format
- Confirmed public key size (32 bytes)
- Validated CONTACT packet structure and byte offsets

**Future Consideration:**
- Could be useful later for Bluetooth/Serial sync features in web UI
- May help with direct device communication features

### 3. Storage Scalability ✅ RESOLVED

**Decision:** Use datafiles with Manager API

**Reasoning:**
- Built-in filtering: `Advert.objects.filter(type=2)`, `Advert.objects.all()`
- Supports exact match queries out of the box
- Post-filter in Python for partial matches (name contains, key prefix)
- File-based storage is simple, debuggable, and sufficient for MVP

**Implementation:**
```python
@datafile("storage/{self.discord_server_id}/{self.discord_user_id}/{self.public_key}.json")
class Advert:
    # fields...
```

**Scalability:**
- Suitable for hundreds to thousands of adverts per mesh
- Each advert stored as individual JSON file
- Easy to inspect, backup, and migrate
- Can switch to SQLite later if needed without changing API

**Query Strategy:**
- Exact filters: Use datafiles Manager directly
- Partial matches: `[a for a in Advert.objects.all() if "prefix" in a.public_key]`
- Performance: Acceptable for expected dataset sizes

### 4. Discord Bot Hosting

**Status:** To be determined during deployment phase

**Considerations:**
- Self-hosted: Full control, custom domain, no platform restrictions
- Cloud (Railway/Fly.io/Heroku): Easy deployment, auto-scaling
- Bot verification: Required for 100+ servers (not immediate concern for MVP)
- Resources: Minimal (Python bot + file storage)

## Success Metrics

- Successfully parse and store adverts from Discord
- Provide reliable contact downloads via API
- Support multiple Discord servers (meshes)
- Sub-second response times for API requests
- Zero data loss during normal operations

## Timeline Estimate

- **Phase 1** (Core Foundation): 2-3 days
- **Phase 2** (Discord MVP): 2-3 days
- **Phase 3** (Discord Full): 2-3 days
- **Phase 4** (Web API Core): 2-3 days
- **Phase 5** (Web API Extended): 1-2 days
- **Phase 6** (Production): 2-3 days

**Total Estimate**: 11-17 days of development time

## Implementation Progress

### ✅ Completed

**Phase 1: Core Foundation - COMPLETED**
1. ✅ Project structure created
2. ✅ Advertisement parser implemented (`coretact/meshcore/parser.py`)
   - Parses meshcore:// URLs (Contact Export format)
   - Extracts public_key, name, type, flags, location, timestamps
3. ✅ Data models defined in parser (ParsedAdvert dataclass)
4. ✅ Unit tests written (`tests/test_advert_parser.py`)
   - 40+ test cases covering valid inputs, error handling, edge cases
   - pytest configuration (`pytest.ini`, `requirements-dev.txt`)
5. ✅ All open questions resolved and documented

**Phase 2: Discord Bot (MVP) - COMPLETED**
1. ✅ Set up datafiles storage layer with Advert model
   - File-based storage with configurable STORAGE_PATH
   - Automatic path resolution (relative/absolute)
   - Full CRUD operations
2. ✅ Discord bot initialization with loguru logging
   - Cog-based architecture following Bridger pattern
   - Auto-sync commands on startup (configurable)
   - Minimal intents (no message content needed)
3. ✅ Implemented `/coretact add` command
   - Add/update meshcore contact advertisements
   - Parse and validate meshcore:// URLs
   - Rich embed responses with full public keys
4. ✅ Implemented `/coretact list` command
   - List user's own adverts or another user's adverts
   - Full public key display
5. ✅ Implemented `/coretact remove` command
   - Remove adverts by public key prefix (8+ chars)
   - Handles multiple matches gracefully
6. ✅ Tested with real Discord server

**Phase 3: Discord Bot (Full Features) - COMPLETED**
1. ✅ Implemented `/coretact search` command
   - Filter by type (companion/repeater/room)
   - Filter by key_prefix
   - Filter by name (partial match)
   - Filter by user
   - Shows up to 25 results with full keys
2. ✅ Implemented `/coretact download` command
   - Export contacts as JSON file
   - Apply same filters as search
   - ContactsList format (device-compatible)
   - Ephemeral file attachment (private)
3. ✅ Implemented `/coretact info` command
   - Server statistics (total, unique users, last updated)
   - Breakdown by type
4. ✅ Shared data models for Discord & Web API
   - ContactConverter for consistent formatting
   - ContactFilter for unified filtering logic
5. ✅ Robust error handling throughout

**Phase 4: Web API (Core) - COMPLETED**
1. ✅ Set up aiohttp server with middleware
   - Error handling middleware with JSON error responses
   - CORS middleware with wildcard origin support
   - Request logging middleware
2. ✅ Implemented health check endpoint (GET /health)
   - Returns status and version information
3. ✅ Implemented mesh contacts endpoint (GET /api/v1/mesh/{server_id}/contacts)
   - Query parameter filtering (type, key_prefix, name, user_id)
   - Returns ContactsList format
4. ✅ Implemented single contact lookup endpoint (GET /api/v1/contact/{public_key})
   - Searches across all meshes
   - Returns Contact with additional metadata (advert_string, discord_server_id, discord_user_id)
5. ✅ Implemented bulk contacts endpoint (POST /api/v1/mesh/{server_id}/contacts/bulk)
   - Accepts list of public keys
   - Optional metadata inclusion
   - Returns ContactsList format
6. ✅ Added CORS middleware
   - Allows all origins (*)
   - Supports GET, POST, OPTIONS methods
   - Handles preflight requests

**Phase 5: Web API (Extended) - COMPLETED**
1. ✅ Implemented user contacts endpoint (GET /api/v1/mesh/{server_id}/user/{user_id}/contacts)
2. ✅ Implemented mesh stats endpoint (GET /api/v1/mesh/{server_id}/stats)
   - Total adverts, unique users, last_updated
   - Breakdown by type (companion, repeater, room)
3. ⬜ Add rate limiting - Future enhancement
4. ⬜ Add API documentation (OpenAPI/Swagger) - Future enhancement

**Files Created:**
- `coretact/__init__.py` - Package initialization with version
- `coretact/__main__.py` - CLI entry point (bot/api commands)
- `coretact/bot.py` - Bot initialization with auto-sync
- `coretact/log.py` - Loguru logging configuration
- `coretact/models.py` - Advert, Contact, ContactsList models
- `coretact/storage.py` - AdvertStorage, ContactConverter, ContactFilter
- `coretact/cogs/__init__.py`
- `coretact/cogs/coretact/__init__.py` - Main Cog with 6 commands
- `coretact/meshcore/__init__.py`
- `coretact/meshcore/parser.py` - Advertisement parser
- `coretact/api/__init__.py` - API package
- `coretact/api/server.py` - aiohttp server setup
- `coretact/api/routes.py` - API route handlers (6 endpoints)
- `coretact/api/middleware.py` - CORS, error handling, logging
- `tests/__init__.py`
- `tests/conftest.py` - Pytest configuration for datafiles
- `tests/test_advert_parser.py` - Parser tests (27 passed)
- `tests/test_storage.py` - Storage tests (7 passed, 1 skipped)
- `tests/test_api.py` - API tests (8 passed)
- `.env.default` - Environment variable template (updated with API vars)
- `.gitignore` - Python/storage/logs
- `README.md` - Complete documentation with API reference

**Test Results:**
- Total: 42 tests passed, 1 skipped
- Coverage: 54% overall
  - API routes: 90% coverage
  - API middleware: 76% coverage
  - Parser: 93% coverage
  - Storage: 82% coverage

### 🚧 In Progress

Nothing currently in progress.

### 📋 Next Steps

**Phase 6: Production Readiness** - Future
1. Docker configuration
2. Write deployment documentation
3. Set up CI/CD pipeline

**Future Enhancements:**
- Rate limiting for API endpoints
- OpenAPI/Swagger documentation
- Web Bluetooth/Serial sync features
- Contact QR code generation
- Contact expiration/cleanup

## Development Environment Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run specific test file
pytest tests/test_advert_parser.py

# Run with coverage
pytest --cov=coretact --cov-report=html
```
