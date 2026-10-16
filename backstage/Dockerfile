# =============================================================================
# Multi-stage build for the Vidi Backstage app (builds entirely in Docker — the
# host needs no Node toolchain). Based on the official Backstage "Multi-stage
# Build": https://backstage.io/docs/deployment/docker
#
# IMPORTANT: build-time and runtime Node versions must match, or the
# better-sqlite3 native module fails at runtime. Keep this image and
# scaffold-backstage.sh on the same node:24 tag.
#
# NOT the create-app Dockerfile in packages/backend/ (that one is the host-build
# variant that expects `yarn build` to have run on the host first).
# =============================================================================

# ---- Stage 1: skeleton (cache the yarn install layer) -----------------------
FROM node:24-trixie-slim AS packages

WORKDIR /app
COPY .yarn ./.yarn
COPY .yarnrc.yml package.json yarn.lock ./
COPY packages packages
COPY plugins plugins

# Keep only package.json files so the install layer is cached independently of
# source changes.
RUN find packages plugins -mindepth 2 -maxdepth 2 \! -name "package.json" -exec rm -rf {} \+ || true

# ---- Stage 2: install deps + build -----------------------------------------
FROM node:24-trixie-slim AS build

ENV PYTHON=/usr/bin/python3
# Toolchain for native modules (better-sqlite3) + scaffolder's isolated-vm.
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 g++ build-essential libsqlite3-dev && \
    rm -rf /var/lib/apt/lists/*

USER node
WORKDIR /app

# Install against the skeleton first (better layer caching).
COPY --from=packages --chown=node:node /app .
COPY --chown=node:node .yarn ./.yarn
COPY --chown=node:node .yarnrc.yml ./
RUN yarn install --immutable

# Now bring in the full source and build.
COPY --chown=node:node . .
RUN yarn tsc
RUN yarn --cwd packages/backend build

# ---- Stage 3: runtime -------------------------------------------------------
FROM node:24-trixie-slim

ENV PYTHON=/usr/bin/python3
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 g++ build-essential libsqlite3-dev && \
    rm -rf /var/lib/apt/lists/*

# Persistent SQLite lives here (mounted as the backstage-data volume). Must be
# owned by `node` so the unprivileged runtime user can write; an empty named
# volume inherits this ownership on first mount.
RUN mkdir -p /data && chown -R node:node /data

USER node
WORKDIR /app

# Install production deps against the backend skeleton.
COPY --from=build --chown=node:node /app/.yarn ./.yarn
COPY --from=build --chown=node:node /app/.yarnrc.yml ./
COPY --from=build --chown=node:node /app/yarn.lock /app/package.json ./
COPY --from=build --chown=node:node /app/packages/backend/dist/skeleton.tar.gz ./
RUN tar xzf skeleton.tar.gz && rm skeleton.tar.gz
RUN yarn workspaces focus --all --production

# Unpack the built backend bundle + ship the configs and example catalog data.
COPY --from=build --chown=node:node /app/packages/backend/dist/bundle.tar.gz /app/app-config*.yaml ./
RUN tar xzf bundle.tar.gz && rm bundle.tar.gz
COPY --from=build --chown=node:node /app/examples ./examples

ENV NODE_ENV=production
ENV NODE_OPTIONS="--no-node-snapshot"

CMD ["node", "packages/backend", "--config", "app-config.yaml", "--config", "app-config.production.yaml"]
