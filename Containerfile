# Containerfile for Coretact
# Supports both Discord bot and Web API modes
FROM public.ecr.aws/docker/library/python:3.12.9

ARG release

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

COPY . /app

# Install dependencies
RUN --mount=type=cache,dst=/root/.cache/uv \
    uv sync --frozen --no-dev

# Default command runs the bot
# Override with "api" for the web API server
CMD ["uv", "run", "python", "-m", "coretact", "bot"]
