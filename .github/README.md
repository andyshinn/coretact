# GitHub Actions CI/CD

This directory contains GitHub Actions workflows for continuous integration and deployment of Coretact.

## Workflows

### `build.yml`

Handles building, testing, and deploying Coretact.

#### Triggers

- **Pull Requests** to `main`: Runs tests and builds image
- **Push to `main`**: Runs tests and builds image with `latest` tag
- **Releases**: Runs tests, builds tagged image, and deploys to production

#### Jobs

##### 1. `test`
- Runs on: `ubuntu-24.04`
- Steps:
  - Checkout code
  - Install `uv` and Python 3.12
  - Install dependencies
  - Run pytest with coverage

##### 2. `build`
- Runs on: `self-hosted` (your deployment server)
- Steps:
  - Checkout code
  - Extract branch/tag name
  - Build container image with Buildah
  - Push to GitHub Container Registry (GHCR)
- Outputs: Tagged images
  - `ghcr.io/<owner>/coretact:<commit-sha>`
  - `ghcr.io/<owner>/coretact:<branch-name>`
  - `ghcr.io/<owner>/coretact:latest` (main branch only)

##### 3. `deploy`
- Runs on: `self-hosted` (your deployment server)
- Triggers: Only on release publication
- Requires: `build` and `test` jobs to complete successfully
- Steps:
  - Checkout code
  - Run `deploy/deploy.sh` script
  - Deploys using Podman Play

## Required Secrets

Configure these secrets in your GitHub repository settings:
`Settings → Secrets and variables → Actions → New repository secret`

### Required

- **`DISCORD_BOT_TOKEN`** (required)
  - Your Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications)
  - Used by the bot to connect to Discord
  - Format: Long string like `MTQyNzA5Njg2NjYyMDgzNzk1OA.G5bBV4...`

### Optional

- **`DISCORD_BOT_OWNER_ID`** (optional)
  - Your Discord user ID for owner-only commands
  - Right-click your username in Discord (Developer Mode) and select "Copy ID"
  - Format: Numeric string like `206914075391688704`

- **`SENTRY_DSN`** (optional)
  - Sentry.io DSN for error tracking
  - Get from your Sentry project settings
  - Format: `https://[key]@[org].ingest.sentry.io/[project]`

## Self-Hosted Runner Setup

The `build` and `deploy` jobs run on a self-hosted GitHub Actions runner, which is your deployment server.

### Installing the Runner

1. Go to your repository: `Settings → Actions → Runners → New self-hosted runner`
2. Follow the instructions to download and configure the runner on your server
3. Install as a service (systemd):

```bash
cd actions-runner
sudo ./svc.sh install
sudo ./svc.sh start
```

### Runner Requirements

The self-hosted runner needs:

- **Podman** installed and configured
- **Buildah** for building container images
- **jq** for JSON parsing (used in deploy script)
- Access to write to `$HOME/.config/containers/` for Podman config

#### Installation on Ubuntu/Debian

```bash
# Install Podman and Buildah
sudo apt-get update
sudo apt-get install -y podman buildah jq

# Enable Podman socket (optional, for API access)
systemctl --user enable --now podman.socket

# Configure Podman for rootless mode
echo "export XDG_RUNTIME_DIR=/run/user/$(id -u)" >> ~/.bashrc
```

## Deployment Process

### Automatic Deployment (Releases)

1. Create a new release on GitHub:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
2. Go to GitHub: `Releases → Draft a new release`
3. Select the tag, add release notes
4. Click "Publish release"
5. GitHub Actions will:
   - Run tests
   - Build tagged image (`ghcr.io/<owner>/coretact:v0.2.0`)
   - Push to GHCR
   - Deploy to production using `deploy/deploy.sh`

### Manual Deployment

SSH into your self-hosted runner and run:

```bash
cd /path/to/coretact
export IMAGE="ghcr.io/<owner>/coretact:v0.2.0"
export DISCORD_BOT_TOKEN="your_token_here"
export DISCORD_BOT_OWNER_ID="your_user_id"
./deploy/deploy.sh
```

## Troubleshooting

### Build fails with "permission denied"

Ensure the self-hosted runner has Podman configured correctly:

```bash
# Check Podman works
podman run --rm hello-world

# Check Buildah works
buildah version
```

### Deploy fails with "DISCORD_BOT_TOKEN required"

Verify the secret is set in GitHub:
`Settings → Secrets and variables → Actions → Repository secrets`

### Pod already exists error

The old pod wasn't removed. SSH to the server and run:

```bash
podman play kube --down deploy/kube/coretact-play.yaml
# Or force remove
podman pod rm -f coretact
```

### Image not found

GHCR authentication might have failed. Check the runner has access:

```bash
# Login to GHCR
echo $GITHUB_TOKEN | podman login ghcr.io -u $GITHUB_ACTOR --password-stdin

# Or manually with a PAT
podman login ghcr.io -u yourusername
```

## Monitoring Deployments

### View Runner Status

- GitHub: `Settings → Actions → Runners`
- Server: `sudo ./svc.sh status`

### View Deployment Logs

- GitHub Actions: `Actions` tab → Select workflow run
- Server logs:
  ```bash
  podman logs -f coretact-bot
  podman logs -f coretact-api
  ```

### Check Deployed Version

```bash
# API health endpoint shows version
curl http://localhost:8080/health

# Check running image
podman ps --filter "pod=coretact" --format "{{.Image}}"
```

## Security Best Practices

1. **Use Self-Hosted Runners Securely**
   - Don't use self-hosted runners for public repositories
   - Keep runner software updated: `cd actions-runner && ./config.sh --upgrade`
   - Run runner as dedicated user (not root)

2. **Protect Secrets**
   - Never log secrets in GitHub Actions
   - Use environment variables only
   - Rotate tokens periodically

3. **Image Security**
   - Images are built from source on your own runner
   - Pushed to GHCR (private by default)
   - Pull images only from trusted registries

## Advanced Configuration

### Custom Environment Variables

Add to `.github/workflows/build.yml` under the `deploy` job:

```yaml
- name: Deploy with Podman Play
  run: deploy/deploy.sh
  env:
    IMAGE: ghcr.io/${{ github.repository }}:${{ github.event.release.tag_name }}
    DISCORD_BOT_TOKEN: ${{ secrets.DISCORD_BOT_TOKEN }}
    DISCORD_BOT_OWNER_ID: ${{ secrets.DISCORD_BOT_OWNER_ID }}
    LOGURU_LEVEL: INFO
    TZ: America/Chicago
    SENTRY_DSN: ${{ secrets.SENTRY_DSN }}
```

### Deploy on Push to Main (Continuous Deployment)

Change the `deploy` job condition:

```yaml
if: github.ref == 'refs/heads/main' && github.event_name == 'push'
```

This will deploy every commit to `main` (use with caution!).

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Self-hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Podman Documentation](https://docs.podman.io)
- [Buildah Documentation](https://buildah.io/docs)
