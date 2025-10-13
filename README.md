# Coretact - Meshcore Contact Management System

A Discord bot and API for managing meshcore contact advertisements.

## Features

- **Discord Bot**: Manage your meshcore contact advertisements via slash commands
- **Web API**: RESTful API for programmatic access to contact data
- **File-based Storage**: Simple JSON storage using the datafiles library
- **Contact Filtering**: Search and filter contacts by type, name, and public key
- **CORS Support**: Access the API from any origin

## Setup

### Prerequisites

- Python 3.12+
- A Discord bot token (get one from [Discord Developer Portal](https://discord.com/developers/applications))

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd coretact
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

3. Configure environment variables:
```bash
cp .env.default .env
# Edit .env and add your Discord bot token and owner ID
```

4. Run the bot or API server:
```bash
# Run the Discord bot
python -m coretact bot

# Run the Web API server
python -m coretact api

# Run the Web API server on a custom host/port
python -m coretact api --host 127.0.0.1 --port 8080
```

## Discord Commands

All commands use the `/coretact` prefix:

### `/coretact add <meshcore_url>`
Add or update your meshcore contact advertisement.

Example:
```
/coretact add meshcore://110055365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d...
```

### `/coretact list [user]`
List contact advertisements. Without arguments, lists your own adverts. Optionally specify a user to list their adverts.

### `/coretact remove <public_key>`
Remove one of your advertisements by providing the first 8+ characters of the public key.

Example:
```
/coretact remove 55365953
```

### `/coretact search [type] [key_prefix] [name] [user]`
Search for contact advertisements in the current server with optional filters:
- `type`: Filter by device type (companion, repeater, or room)
- `key_prefix`: Filter by public key prefix
- `name`: Filter by name (partial match)
- `user`: Filter by specific user

### `/coretact download [type] [key_prefix] [name] [user]`
Download contacts as a JSON file with optional filters (same as search command).

### `/coretact info`
Show statistics for the current server including total contacts, breakdown by type, and unique users.

## Web API

The Web API provides programmatic access to contact data. All endpoints return JSON responses.

### Base URL

```
http://localhost:8080
```

### Endpoints

#### Health Check

```http
GET /health
```

Returns the API health status and version.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

#### Get Mesh Contacts

```http
GET /api/v1/mesh/{server_id}/contacts
```

Get all contacts for a mesh (Discord server).

**Query Parameters:**
- `type` (optional): Filter by device type (1=companion, 2=repeater, 3=room)
- `key_prefix` (optional): Filter by public key prefix
- `name` (optional): Filter by name (partial match)
- `user_id` (optional): Filter by Discord user ID

**Example Request:**
```bash
curl "http://localhost:8080/api/v1/mesh/123456789/contacts?type=1&name=Core"
```

**Response:**
```json
{
  "contacts": [
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
      "out_path": ""
    }
  ]
}
```

#### Get Contact by Public Key

```http
GET /api/v1/contact/{public_key}
```

Get a single contact by public key (searches across all meshes).

**Example Request:**
```bash
curl "http://localhost:8080/api/v1/contact/55365953947d253d213d7ab36df0be29ffb7a758049f657a6b32e1d00d66087d"
```

**Response:**
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

#### Bulk Contacts

```http
POST /api/v1/mesh/{server_id}/contacts/bulk
```

Get specific contacts by public keys.

**Request Body:**
```json
{
  "public_keys": ["55365953...", "83c3e551..."],
  "include_metadata": true
}
```

**Response:** Same format as "Get Mesh Contacts" endpoint.

#### Get User Contacts

```http
GET /api/v1/mesh/{server_id}/user/{user_id}/contacts
```

Get all contacts for a specific Discord user.

**Example Request:**
```bash
curl "http://localhost:8080/api/v1/mesh/123456789/user/987654321/contacts"
```

**Response:** Same format as "Get Mesh Contacts" endpoint.

#### Get Mesh Stats

```http
GET /api/v1/mesh/{server_id}/stats
```

Get statistics for a mesh.

**Example Request:**
```bash
curl "http://localhost:8080/api/v1/mesh/123456789/stats"
```

**Response:**
```json
{
  "server_id": "123456789",
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

### CORS

The API supports CORS and allows requests from any origin. All endpoints include the following CORS headers:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type`

### Error Responses

All error responses follow this format:

```json
{
  "error": "Error message",
  "status": 400
}
```

Common status codes:
- `400`: Bad Request (invalid parameters)
- `404`: Not Found (resource doesn't exist)
- `500`: Internal Server Error

## Development

### Running Tests

```bash
pytest
```

### Project Structure

```
coretact/
├── coretact/
│   ├── __main__.py         # CLI entry point
│   ├── bot.py              # Discord bot initialization
│   ├── models.py           # Data models (Advert, Contact)
│   ├── storage.py          # Storage layer
│   ├── log.py              # Logging configuration
│   ├── meshcore/
│   │   └── parser.py       # Meshcore URL parser
│   ├── cogs/
│   │   └── coretact/       # Discord command handlers
│   │       └── __init__.py
│   └── api/
│       ├── __init__.py
│       ├── server.py       # API server setup
│       ├── routes.py       # API route handlers
│       └── middleware.py   # CORS and error handling
├── tests/
│   ├── conftest.py         # Pytest configuration
│   ├── test_storage.py     # Storage tests
│   ├── test_advert_parser.py  # Parser tests
│   └── test_api.py         # API tests
└── storage/                # Contact data (git-ignored)
```

## Environment Variables

### Discord Bot

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | Your Discord bot token |
| `DISCORD_BOT_OWNER_ID` | No | Your Discord user ID (for owner commands) |
| `AUTO_SYNC_COMMANDS` | No | Auto-sync commands on startup (default: `true`) |

### Web API

| Variable | Required | Description |
|----------|----------|-------------|
| `WEB_API_HOST` | No | API host to bind to (default: `0.0.0.0`) |
| `WEB_API_PORT` | No | API port to bind to (default: `8080`) |

### Storage

| Variable | Required | Description |
|----------|----------|-------------|
| `STORAGE_PATH` | No | Storage directory path (default: `./storage`) |

### Logging

| Variable | Required | Description |
|----------|----------|-------------|
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

## License

[Add license information]

## Contributing

[Add contributing guidelines]
