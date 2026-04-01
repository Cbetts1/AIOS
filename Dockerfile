FROM python:3.12-slim

LABEL maintainer="AURA OS contributors"
LABEL description="AURA OS — Adaptive User-space Runtime Architecture"

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/aura

# Copy project files
COPY . .

# Install as a Python package (stdlib-only, no extras)
RUN pip install --no-cache-dir .

# Set up AURA_HOME
ENV AURA_HOME=/root/.aura

# Create runtime directories
RUN mkdir -p "$AURA_HOME"/{configs,logs,models,tasks,repos,data,pkg/installed,ipc}

ENTRYPOINT ["aura"]
CMD ["--help"]
