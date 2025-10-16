# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Coretact is a Discord bot and Web API for managing meshcore contact advertisements. It allows users to share and discover meshcore device contacts within Discord servers, with each server acting as a separate "mesh" of contacts.

The system uses a file-based storage approach (via the `datafiles` library) where each contact advertisement is stored as a JSON file organized by Discord server ID, user ID, and public key.

## Development Setup

This project uses `uv` as the package manager. Install dependencies:

```bash
uv sync
```

Run the Discord bot:
```bash
uv run python -m coretact bot
```

Run the Web API server:
```bash
uv run python -m coretact api
# Or with custom host/port:
uv run python -m coretact api --host 127.0.0.1 --port 8080
```

## Testing

Run all tests:
```bash
uv run pytest
```

Run a single test file:
```bash
uv run pytest tests/test_storage.py
```

Run a specific test:
```bash
uv run pytest tests/test_storage.py::test_function_name -v
```

The test configuration is in [pyproject.toml](pyproject.toml) and includes coverage reporting. Tests automatically clean up storage files after each run (see [tests/conftest.py](tests/conftest.py)).

## Code Architecture

### Storage Layer (`coretact/storage.py`)

The storage layer is organized into several classes with distinct responsibilities:

- **`AdvertStorage`**: Core CRUD operations for advertisements (create, read, update, delete, list). Uses the `datafiles` library to persist `Advert` objects as JSON files.
- **`ContactConverter`**: Converts between internal `Advert` models (used for storage) and `Contact` models (used for API responses). This separation allows the internal storage format to differ from the API contract.
- **`ContactFilter`**: Applies filtering logic to lists of adverts (by type, key prefix, name, user ID). Used by both Discord commands and API endpoints.
- **`MeshStorage`**: Manages mesh/server metadata (Discord server name, icon, etc.) stored in `info.json` files.

### Data Models (`coretact/models.py`)

- **`Advert`**: Internal storage model decorated with `@datafile`. File path: `storage/<server_id>/adverts/<public_key>.json`. Contains the full meshcore URL, parsed fields, timestamps, and the owner's discord_user_id (stored inside the JSON, not in the path).
- **`Mesh`**: Server metadata model decorated with `@datafile`. File path: `storage/<server_id>/info.json`.
- **`Marks`**: User marks model decorated with `@datafile`. File path: `storage/<server_id>/marks/<discord_user_id>.json`. Contains a list of public keys that a user has marked for later download.
- **`Contact`**: API response model (not stored on disk). Contains the subset of fields exposed via the API.

The `STORAGE_PATH` environment variable controls where files are stored (defaults to `./storage`).

**Storage Design**: The discord_user_id is stored inside the JSON file, not in the file path. This allows lookups by server_id + public_key only, making permission checks simpler (load the advert first, then verify ownership).

### Meshcore Parser (`coretact/meshcore/parser.py`)

Parses `meshcore://` URLs into structured data. Supports two formats:
1. **Contact Export Format** (most common): ~123+ bytes with public key, name, location, timestamps
2. **Broadcast Format**: Shorter format without public key

The parser extracts: device type (companion/repeater/room), name, public key, flags, location coordinates, and path information.

### Discord Bot (`coretact/bot.py` + `coretact/cogs/coretact/__init__.py`)

- Built with `discord.py` using slash commands (app_commands)
- All commands are grouped under `/coretact`
- The bot automatically creates/updates mesh metadata when joining servers
- Commands: `add`, `list`, `remove`, `search`, `download`, `download-marked`, `info`
- The cog pattern is used for organization (`CoretactCog` in [coretact/cogs/coretact/__init__.py](coretact/cogs/coretact/__init__.py))

**Permission System:**
- Users can always add/remove their own advertisements
- Users with the "Coretact Admin" role can remove any advertisement in the server
- The `/coretact remove` command automatically searches all adverts for admins, or just the user's own adverts for regular users
- Permission checks use `app_commands.CheckFailure` exceptions which are caught by the error handler
- Permission helper functions:
  - `is_coretact_admin()`: Checks for "Coretact Admin" role
  - `check_advert_owner()`: Checks if user owns the advert
  - `is_coretact_admin_or_owner()`: Combined check (admin OR owner)

**User Context Menus:**
- **Show Contacts**: Right-click a user to see all their contact advertisements
- **Mark Contact**: Right-click a user to toggle marking all their contacts for later download

**Contact Marking System:**
- Users can mark contacts from other users to create a personal collection
- Marks are stored per-server in `storage/<server_id>/marks/<discord_user_id>.json`
- Use `/coretact download-marked` to download all marked contacts as a JSON file
- The marking system uses the `Marks` datafile model with a simple list of public keys

### Web API (`coretact/api/`)

- Built with `aiohttp`
- Entry points: [coretact/api/server.py](coretact/api/server.py) sets up the app, [coretact/api/routes.py](coretact/api/routes.py) defines endpoints
- All API routes are under `/api/v1/`
- CORS middleware allows requests from any origin ([coretact/api/middleware.py](coretact/api/middleware.py))
- The `AdvertStorage` instance is stored in `app["storage"]` and accessed by route handlers

### Environment Configuration

Required for Discord bot:
- `DISCORD_BOT_TOKEN`: Bot token from Discord Developer Portal
- `DISCORD_BOT_OWNER_ID`: Optional, enables owner commands

Optional:
- `STORAGE_PATH`: Custom storage directory (default: `./storage`)
- `WEB_API_HOST`: API bind address (default: `0.0.0.0`)
- `WEB_API_PORT`: API bind port (default: `8080`)
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `AUTO_SYNC_COMMANDS`: Auto-sync Discord commands on startup (default: `true`)

Sentry (optional):
- `SENTRY_DSN`: Sentry project DSN for error tracking
- `SENTRY_TRACES_SAMPLE_RATE`: Transaction sampling rate (default: `0.1` = 10%)
- `SENTRY_PROFILES_SAMPLE_RATE`: Profiling sampling rate (default: `0.1` = 10%)
- `SENTRY_AUTH_TOKEN`: Auth token for CI/CD release tracking (GitHub Actions only)

See [.env.default](.env.default) for a template.

### Error Tracking with Sentry

Sentry is integrated for error tracking and performance monitoring:

**Initialization:** Sentry is initialized in [coretact/__init__.py](coretact/__init__.py) at module import time, ensuring all errors are captured.

**Privacy Settings:**
- `send_default_pii=False`: Prevents personally identifiable information from being sent
- `EventScrubber`: Redacts sensitive environment variables from error reports
- Custom denylist includes: `DISCORD_BOT_TOKEN`, `DISCORD_BOT_OWNER_ID`

**Release Tracking:**
- Release information comes from `coretact.__version__` (set via setuptools-scm from git tags)
- Release format: `coretact@<version>` (e.g., `coretact@1.0.0`)
- Errors are automatically tagged with the release version when sent to Sentry
- This allows filtering and tracking issues by version in the Sentry dashboard

**GitHub Actions Integration:**
- The `deploy` job in [.github/workflows/build.yml](.github/workflows/build.yml) creates Sentry releases using `getsentry/action-release@v1`
- Requires `SENTRY_AUTH_TOKEN` secret configured in GitHub repository settings
- Automatically creates release, links commits, and registers production deployment
- Only runs on release publish events
- Release version matches the package version from `.version` file

## Key Design Patterns

### File-Based Storage with datafiles

The `datafiles` library provides ORM-like functionality with automatic JSON serialization:
- Models are decorated with `@datafile` and specify their file path pattern
- Access the underlying file via `model.datafile.path`, `model.datafile.save()`, `model.datafile.load()`
- Query API available via `Model.objects.all()`, `Model.objects.filter()`, `Model.objects.get_or_none()`
- Test configuration in [tests/conftest.py](tests/conftest.py) disables hooks for performance

### Separation of Storage and API Models

Internal `Advert` model != External `Contact` model. This allows:
- Internal refactoring without breaking API contracts
- Different field names/types between storage and API
- The `ContactConverter` class bridges the two

### Error Handling

- Discord bot: Uses `cog_app_command_error` to catch and format errors for users
- API: Uses aiohttp's `web.HTTPException` subclasses (`HTTPNotFound`, `HTTPBadRequest`)
- Parser: Raises `ValueError` for invalid meshcore URLs
