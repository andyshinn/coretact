# Kubernetes/Podman Deployment Files

This directory contains Kubernetes-compatible YAML files for deploying Coretact with Podman Play.

## Files

- **`coretact-play.yaml`** - Main pod specification with bot and API containers
- **`configmap.yaml.example`** - Template for Discord credentials (copy to `configmap.yaml`)
- **`configmap.yaml`** - Your actual credentials (git-ignored, you create this)

## Quick Start

```bash
# 1. Copy the ConfigMap template
cp configmap.yaml.example configmap.yaml

# 2. Edit and add your Discord bot token
vi configmap.yaml

# 3. Deploy (using envsubst to set image)
export IMAGE=localhost/coretact:latest
envsubst < coretact-play.yaml | podman play kube --configmap configmap.yaml -

# 3a. Update deployment (with --replace to recreate containers)
export IMAGE=localhost/coretact:latest
envsubst < coretact-play.yaml | podman play kube --replace --configmap configmap.yaml -

# 4. Check status
podman pod ps
podman logs coretact-bot
curl http://localhost:8080/health

# 5. Stop when done
# Note: Use the generated file or re-run envsubst
envsubst < coretact-play.yaml | podman play kube --down -
```

## Configuration

### Required

- `DISCORD_BOT_TOKEN` - Your Discord bot token (get from [Discord Developer Portal](https://discord.com/developers/applications))

### Optional

- `DISCORD_BOT_OWNER_ID` - Your Discord user ID (enables owner-only commands)

### Other Settings

All other configuration options (storage paths, logging, etc.) are defined inline in `coretact-play.yaml` and can be edited there if needed.

## Security

- `configmap.yaml` is automatically git-ignored to prevent credential leaks
- For production, consider using Podman secrets instead of ConfigMaps
- Never commit `configmap.yaml` to version control

## Volumes

The deployment creates two persistent volumes:

- `coretact-storage` (1 GiB) - Contact advertisements
- `coretact-logs` (500 MiB) - Application logs

To inspect volumes:

```bash
podman volume ls
podman volume inspect coretact-storage
```

## Troubleshooting

### Bot not connecting

```bash
# Check if token is set
podman exec coretact-bot env | grep DISCORD_BOT_TOKEN

# View bot logs
podman logs coretact-bot
```

### API not responding

```bash
# Check API logs
podman logs coretact-api

# Test health endpoint
curl http://localhost:8080/health
```

## More Information

See [DEPLOYMENT.md](../../DEPLOYMENT.md) in the project root for comprehensive deployment documentation.
