#!/usr/bin/env bash
#
# Coretact Deployment Script
# Deploys Coretact using Podman Play with environment-based configuration
#
# Environment Variables:
#   IMAGE                  - Container image to deploy (default: ghcr.io/andyshinn/coretact:latest)
#   DISCORD_BOT_TOKEN      - Required: Discord bot token
#   DISCORD_BOT_OWNER_ID   - Optional: Discord bot owner ID
#   SENTRY_DSN             - Optional: Sentry DSN for error tracking
#   LOGURU_LEVEL           - Optional: Log level (default: INFO)
#   TZ                     - Optional: Timezone (default: UTC)

set -euo pipefail

# Configuration
KUBE_DIR="deploy/kube"
CONFIGMAP_FILE="$KUBE_DIR/configmap.yaml"
PLAY_FILE="$KUBE_DIR/coretact-play.yaml"
POD_NAME="coretact"

# Default values
export IMAGE="${IMAGE:-ghcr.io/andyshinn/coretact:latest}"
export LOGURU_LEVEL="${LOGURU_LEVEL:-INFO}"
export TZ="${TZ:-UTC}"
export SENTRY_DSN="${SENTRY_DSN:-}"

# Validate required environment variables
if [ -z "${DISCORD_BOT_TOKEN:-}" ]; then
    echo "Error: DISCORD_BOT_TOKEN environment variable is required" >&2
    exit 1
fi

echo "==> Deploying Coretact"
echo "    Image: $IMAGE"
echo "    Pod: $POD_NAME"
echo ""

# Create ConfigMap with Discord credentials
echo "==> Creating ConfigMap with credentials..."
cat > "$CONFIGMAP_FILE" <<EOF
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: coretact-discord-secrets
data:
  DISCORD_BOT_TOKEN: "${DISCORD_BOT_TOKEN}"
  DISCORD_BOT_OWNER_ID: "${DISCORD_BOT_OWNER_ID:-}"
EOF

# Create play file with substituted environment variables
echo "==> Generating play file with IMAGE=$IMAGE..."
PLAY_FILE_GENERATED="$KUBE_DIR/coretact-play.generated.yaml"
envsubst < "$PLAY_FILE" > "$PLAY_FILE_GENERATED"

# Pull the latest image
echo "==> Pulling image: $IMAGE"
podman pull "$IMAGE"

# Stop existing pod if running
if podman pod exists "$POD_NAME" 2>/dev/null; then
    echo "==> Stopping existing pod..."
    podman play kube --down "$PLAY_FILE_GENERATED" || true
fi

# Deploy with Podman Play (--replace ensures fresh containers)
echo "==> Deploying pod with Podman Play..."
podman play kube --replace --configmap "$CONFIGMAP_FILE" "$PLAY_FILE_GENERATED"

echo ""
echo "==> Deployment complete!"
echo "    View logs: podman logs -f coretact-bot"
echo "    API health: curl http://localhost:8080/health"
echo "    Pod status: podman pod ps"
echo "    Stop pod: podman play kube --down $PLAY_FILE_GENERATED"
