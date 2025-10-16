# Containerfile for Coretact
# Supports both Discord bot and Web API modes
FROM public.ecr.aws/docker/library/python:3.12.9

ARG release

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set fallback version if git is not available
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${release:-0.0.0-dev}
ENV UV_LINK_MODE=copy

# Copy application code first (needed for setuptools-scm)
COPY . /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Set environment variables
ENV SENTRY_RELEASE=coretact@$release \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Default command runs the bot
# Override with "api" for the web API server
CMD ["uv", "run", "python", "-m", "coretact", "bot"]
