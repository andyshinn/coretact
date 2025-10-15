# Coretact Deployment Guide

This guide covers deploying Coretact using Podman with the Kubernetes YAML format (`podman play kube`).

## Prerequisites

- Podman installed ([podman.io](https://podman.io))
- Discord Bot Token from [Discord Developer Portal](https://discord.com/developers/applications)
- Your Discord User ID (optional, for owner commands)

## Quick Start

### 1. Build the Container Image

```bash
# Build the image with a specific version
podman build -t localhost/coretact:latest -f Containerfile . --build-arg release=0.1.0

# Or build without version tag (will use git version)
podman build -t localhost/coretact:latest -f Containerfile .
```

### 2. Configure Discord Credentials

Create a ConfigMap with your Discord bot credentials:

```bash
# Navigate to the deployment directory
cd deploy/kube

# Copy the ConfigMap template
cp configmap.yaml.example configmap.yaml

# Edit configmap.yaml and set your Discord bot token
vi configmap.yaml  # or use your preferred editor
```

Edit the `DISCORD_BOT_TOKEN` field in `configmap.yaml`:

```yaml
data:
  DISCORD_BOT_TOKEN: "your_actual_bot_token_here"  # REQUIRED
  DISCORD_BOT_OWNER_ID: "your_discord_user_id"     # Optional
```

**Security Note:** The `configmap.yaml` file is git-ignored to prevent accidentally committing credentials.

### 3. Deploy with Podman Play

```bash
# From the deploy/kube directory
podman play kube --configmap configmap.yaml coretact-play.yaml

# To update an existing deployment (recreates containers)
podman play kube --replace --configmap configmap.yaml coretact-play.yaml
```

### 4. Verify Deployment

```bash
# Check pod status
podman pod ps

# Check container logs
podman logs coretact-bot
podman logs coretact-api

# Check the API health endpoint
curl http://localhost:8080/health
```

### 5. Stop and Remove

```bash
# Stop and remove the pod
podman play kube --down coretact-play.yaml

# Or manually
podman pod stop coretact
podman pod rm coretact
```

## Architecture

The deployment consists of:

- **Bot Container**: Runs the Discord bot (`python -m coretact bot`)
- **API Container**: Runs the Web API server (`python -m coretact api`)
- **Shared Storage**: Both containers share the same storage volume for contact advertisements
- **Persistent Volumes**: Storage and logs are persisted across restarts

### Container Details

| Container | Port | Purpose | Health Check |
|-----------|------|---------|--------------|
| bot       | -    | Discord bot interface | None (Discord connection) |
| api       | 8080 | REST API for contacts | `/health` endpoint |

### Volume Mounts

| Volume | Mount Point | Size | Purpose |
|--------|-------------|------|---------|
| coretact-storage | `/var/lib/coretact/storage` | 1Gi | Contact advertisements (JSON files) |
| coretact-logs | `/var/lib/coretact/logs` | 500Mi | Application logs |

## Environment Variables

### Discord Bot Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ Yes | - | Discord bot token from Developer Portal |
| `DISCORD_BOT_OWNER_ID` | ❌ No | - | Your Discord user ID (enables owner commands) |
| `AUTO_SYNC_COMMANDS` | ❌ No | `true` | Auto-sync slash commands on startup |

### Web API Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEB_API_HOST` | ❌ No | `0.0.0.0` | Host to bind API server |
| `WEB_API_PORT` | ❌ No | `8080` | Port to bind API server |

### Storage Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STORAGE_PATH` | ❌ No | `/var/lib/coretact/storage` | Path to storage directory |
| `LOG_PATH` | ❌ No | `/var/lib/coretact/logs/{bot,api}.log` | Path to log file |

### Logging Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOGURU_LEVEL` | ❌ No | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `TZ` | ❌ No | `UTC` | Timezone for logs |

### Monitoring (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTRY_DSN` | ❌ No | - | Sentry.io DSN for error tracking |
| `SENTRY_RELEASE` | ❌ No | - | Release version for Sentry (auto-set during build) |

## Manual Container Run

If you prefer to run containers manually without Podman Play:

### Run the Discord Bot

```bash
podman run -d \
  --name coretact-bot \
  -e DISCORD_BOT_TOKEN="your_token" \
  -e DISCORD_BOT_OWNER_ID="your_user_id" \
  -e STORAGE_PATH=/data/storage \
  -v coretact-storage:/data/storage:Z \
  -v coretact-logs:/data/logs:Z \
  --restart always \
  localhost/coretact:latest \
  uv run python -m coretact bot
```

### Run the Web API

```bash
podman run -d \
  --name coretact-api \
  -e STORAGE_PATH=/data/storage \
  -e WEB_API_HOST=0.0.0.0 \
  -e WEB_API_PORT=8080 \
  -v coretact-storage:/data/storage:Z \
  -v coretact-logs:/data/logs:Z \
  -p 8080:8080 \
  --restart always \
  localhost/coretact:latest \
  uv run python -m coretact api
```

## Security Best Practices

### Using Podman Secrets

Instead of hardcoding tokens in `podman-play.yaml`, use Podman secrets:

```bash
# Create a secret for the Discord token
echo "your_discord_token" | podman secret create discord_token -

# Update podman-play.yaml to use the secret
# Replace the env var with:
#   envFrom:
#     - secretRef:
#         name: discord_token
#         key: DISCORD_BOT_TOKEN
```

### File Permissions

Ensure storage directories have appropriate permissions:

```bash
# Check volume location
podman volume inspect coretact-storage

# Set permissions if needed
sudo chown -R 1000:1000 /path/to/volume
```

### Network Security

- The API container exposes port 8080 by default
- For production, use a reverse proxy (nginx, traefik) with HTTPS
- Consider using Podman's network isolation features

## Monitoring and Logs

### View Container Logs

```bash
# Follow bot logs
podman logs -f coretact-bot

# Follow API logs
podman logs -f coretact-api

# View last 100 lines
podman logs --tail 100 coretact-bot
```

### Access Log Files

```bash
# Find volume location
podman volume inspect coretact-logs

# View logs directly
sudo tail -f /path/to/volume/bot.log
sudo tail -f /path/to/volume/api.log
```

### Health Checks

```bash
# Check API health
curl http://localhost:8080/health

# Check pod status
podman pod ps

# Check container status
podman ps -a --filter "label=app=coretact"
```

## Updating the Deployment

### Rebuild and Redeploy

```bash
# Build new image
podman build -t localhost/coretact:latest -f Containerfile . --build-arg release=0.2.0

# Stop current deployment
podman play kube --down podman-play.yaml

# Start updated deployment
podman play kube podman-play.yaml
```

### Zero-Downtime Updates

For the API (bot will have brief downtime):

```bash
# Build new image with version tag
podman build -t localhost/coretact:0.2.0 -f Containerfile . --build-arg release=0.2.0

# Update only the API container
podman stop coretact-api
podman rm coretact-api
podman run -d --pod coretact \
  --name coretact-api \
  localhost/coretact:0.2.0 \
  uv run python -m coretact api
```

## Backup and Restore

### Backup Storage

```bash
# Find volume location
VOLUME_PATH=$(podman volume inspect coretact-storage --format '{{.Mountpoint}}')

# Create backup
sudo tar -czf coretact-backup-$(date +%Y%m%d).tar.gz -C "$VOLUME_PATH" .

# Or use podman volume export (Podman 4.0+)
podman volume export coretact-storage -o coretact-storage-backup.tar
```

### Restore Storage

```bash
# Stop the pod
podman play kube --down podman-play.yaml

# Restore from backup
VOLUME_PATH=$(podman volume inspect coretact-storage --format '{{.Mountpoint}}')
sudo tar -xzf coretact-backup-20251014.tar.gz -C "$VOLUME_PATH"

# Or use podman volume import
podman volume import coretact-storage coretact-storage-backup.tar

# Restart the pod
podman play kube podman-play.yaml
```

## Troubleshooting

### Bot Not Connecting to Discord

```bash
# Check bot logs for errors
podman logs coretact-bot

# Common issues:
# - Invalid DISCORD_BOT_TOKEN
# - Bot not invited to server
# - Bot missing permissions (requires "applications.commands" scope)
```

### API Not Responding

```bash
# Check API logs
podman logs coretact-api

# Test health endpoint
curl http://localhost:8080/health

# Check if port is bound
podman port coretact-api
```

### Storage Permission Issues

```bash
# Check volume permissions
podman volume inspect coretact-storage

# Fix permissions (run as root)
sudo chown -R 1000:1000 $(podman volume inspect coretact-storage --format '{{.Mountpoint}}')
```

### Platform Warning (linux/amd64 vs linux/arm64)

If you see warnings about platform mismatch:

```bash
# Build for your platform explicitly
podman build --platform linux/arm64 -t localhost/coretact:latest -f Containerfile .

# Or build multi-arch image
podman build --platform linux/amd64,linux/arm64 -t localhost/coretact:latest -f Containerfile .
```

## Production Deployment

### Systemd Integration

Generate systemd units for automatic startup:

```bash
# Generate pod systemd unit
podman generate systemd --new --files --name coretact

# Move to systemd directory
sudo mv pod-coretact.service container-coretact-*.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable pod-coretact.service
sudo systemctl start pod-coretact.service
```

### Reverse Proxy (nginx)

Example nginx configuration for the API:

```nginx
server {
    listen 443 ssl http2;
    server_name coretact.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Resource Limits

The default configuration allocates:

- **CPU**: 0.1-0.5 cores per container
- **Memory**: 256-512 MiB per container
- **Storage**: 1 GiB for contacts, 500 MiB for logs

Adjust in [deploy/kube/coretact-play.yaml](deploy/kube/coretact-play.yaml) under `resources:` for each container.

## CI/CD with GitHub Actions

Coretact includes a GitHub Actions workflow for automated builds and deployments.

### Quick Setup

1. **Configure a self-hosted runner** on your deployment server:
   ```bash
   # From your GitHub repository:
   # Settings → Actions → Runners → New self-hosted runner
   # Follow the instructions to install and start the runner
   ```

2. **Add GitHub Secrets** in your repository:
   ```
   Settings → Secrets and variables → Actions → New repository secret

   Required:
   - DISCORD_BOT_TOKEN (your Discord bot token)

   Optional:
   - DISCORD_BOT_OWNER_ID (your Discord user ID)
   - SENTRY_DSN (Sentry error tracking)
   ```

3. **Create a release to deploy**:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0

   # Then on GitHub: Releases → Draft a new release → Publish
   ```

### What Happens on Release

When you publish a GitHub release:

1. **Tests run** on Ubuntu (pytest with coverage)
2. **Image builds** on your self-hosted runner with Buildah
3. **Image pushes** to GitHub Container Registry (GHCR)
4. **Deployment runs** `deploy/deploy.sh` script which:
   - Creates ConfigMap with Discord credentials
   - Pulls the new image from GHCR
   - Stops the old pod (if running)
   - Deploys with `podman play kube --configmap`
   - Verifies API health and shows logs

### Manual Deployment

If you need to deploy manually without a release:

```bash
cd /path/to/coretact
export IMAGE="ghcr.io/yourusername/coretact:v0.1.0"
export DISCORD_BOT_TOKEN="your_token_here"
export DISCORD_BOT_OWNER_ID="your_user_id"  # Optional
./deploy/deploy.sh
```

### Monitoring Deployments

- **GitHub Actions**: Check the `Actions` tab in your repository
- **Pod Status**: `podman pod ps`
- **Container Logs**: `podman logs -f coretact-bot`
- **API Health**: `curl http://localhost:8080/health`

For detailed CI/CD documentation, see [.github/README.md](.github/README.md).

## Additional Resources

- [Podman Documentation](https://docs.podman.io)
- [Podman Play Kube](https://docs.podman.io/en/latest/markdown/podman-play-kube.1.html)
- [Discord Developer Portal](https://discord.com/developers/applications)
- [GitHub Actions Self-Hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Coretact README](README.md)
