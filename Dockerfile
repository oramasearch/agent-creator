# syntax=docker/dockerfile:1
# SPDX-License-Identifier: MIT

# AgentCreator, published on Docker Hub as oramasearch/agent-creator. It is a definition that runs
# on agent-runtime: this image is the runtime plus the definition, served lake-wide with per-turn
# credentials (the person's key rides on each turn).
ARG RUNTIME_TAG
FROM docker.io/oramasearch/agent-runtime:${RUNTIME_TAG}
COPY definition /definition
ENV AGENT_DEFINITION_DIR=/definition \
    AGENT_MODE=service \
    AGENT_PER_TURN_CREDENTIALS=1 \
    TRACE_DIR=/tmp/agent-creator-traces
