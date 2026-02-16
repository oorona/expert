FROM pgvector/pgvector:pg18

# Install build dependencies for pg_textsearch
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        postgresql-server-dev-18 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Download and install pg_textsearch from source
ARG PG_TEXTSEARCH_VERSION=0.5.1
RUN curl -fsSL "https://github.com/timescale/pg_textsearch/releases/download/v${PG_TEXTSEARCH_VERSION}/pg_textsearch-${PG_TEXTSEARCH_VERSION}.tar.gz" \
        -o /tmp/pg_textsearch.tar.gz \
    && mkdir -p /tmp/pg_textsearch \
    && tar xzf /tmp/pg_textsearch.tar.gz -C /tmp/pg_textsearch --strip-components=1 \
    && cd /tmp/pg_textsearch \
    && make \
    && make install \
    && rm -rf /tmp/pg_textsearch /tmp/pg_textsearch.tar.gz

# Clean up build dependencies to keep image small
RUN apt-get purge -y --auto-remove \
        build-essential \
        postgresql-server-dev-18 \
        curl \
    && rm -rf /var/lib/apt/lists/*
