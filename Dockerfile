# syntax=docker/dockerfile:1
# AgentCreator (zetta#1017): private on Docker Hub as oramasearch/agent-creator. It is a definition
# that runs on agent-runtime: this image is the runtime plus the definition, served lake-wide with
# per-turn credentials (the person's key rides on each turn).
# The runtime is named by tag and digest (lake#1003): RUNTIME_DIGEST is the sha256:... of the pushed
# agent-runtime image, so a moved tag cannot change what is built. Without it the reference is
# invalid and the build stops.
ARG RUNTIME_TAG
ARG RUNTIME_DIGEST
FROM docker.io/oramasearch/agent-runtime:${RUNTIME_TAG}@${RUNTIME_DIGEST}
COPY definition /definition
ENV AGENT_DEFINITION_DIR=/definition \
    AGENT_MODE=service \
    AGENT_PER_TURN_CREDENTIALS=1 \
    TRACE_DIR=/tmp/agent-creator-traces
