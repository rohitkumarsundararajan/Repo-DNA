# Node 20 comes from the official image (newer than Debian's apt package)
FROM node:20-slim AS node

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy node + npm from the node stage
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

# madge, pinned version
RUN npm install -g madge@8.0.0 && npm cache clean --force

# Harden git: never run hooks from the cloned repo, only allow https
RUN git config --system core.hooksPath /dev/null \
 && git config --system protocol.allow never \
 && git config --system protocol.https.allow always

# Non-root user, no secrets anywhere in the image.
# /work is created and owned by that user before switching to it: WORKDIR alone would
# create it owned by root and the clone would fail with "permission denied".
RUN useradd --create-home --uid 10001 sandbox \
 && mkdir -p /work \
 && chown sandbox:sandbox /work
USER sandbox
ENV HOME=/home/sandbox \
    GIT_TERMINAL_PROMPT=0
WORKDIR /work

# The runner supplies the real command (git clone ..., madge --json ...)
CMD ["sleep", "infinity"]
