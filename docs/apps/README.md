# Apps and build agents

AgentCreator can propose Python agents that observe Ship Apps and image builds. Every turn reads
the Apps and builds visible through the person's delegated lake credential; no App or build is
remembered across turns.

## Live facts

The turn uses the lake capability inputs exactly:

| Capability | Input beyond `customer_id` | Fact retained |
|---|---|---|
| `list_apps` | none | the visible Apps |
| `get_app` | `app_id` | desired and observed state for every listed App |
| `receive_app_events` | `app_id`, `from_sequence: 1`, `wait_ms: 0` | retained `app-events.<app-id>` events and `next_sequence` |
| `list_builds` | none | the visible builds |
| `get_build` | `build_id` | desired and observed state for every listed build |
| `receive_build_events` | `build_id`, `from_sequence: 1`, `wait_ms: 0` | retained `build-events.<build-id>` events and `next_sequence` |

`app-events.<app-id>` always names one live App. `build-events.*` is the proposal's shorthand for
listing builds and following each returned id through `receive_build_events`; the created agent
does not receive a global event-bus credential. Subsequent polls use the returned one-based cursor.

A failed list marks the App/build source unavailable. A failed detail or event read stays in
`app_error`, and the prompt requires AgentCreator to name the failed capability instead of
inventing facts or access.

## Proposal contract

An App proposal carries an `app_capabilities` object:

```json
{
  "reads": [
    "list_apps",
    "get_app",
    "receive_app_events",
    "list_builds",
    "get_build",
    "receive_build_events"
  ],
  "subscriptions": ["app-events.<live-app-id>", "build-events.*"],
  "proposals": ["build_app", "restart_app"],
  "application_agent": {
    "agent": "agent-application",
    "kind": "app"
  }
}
```

The deterministic review requires a Python agent, capabilities present in this turn's filtered
lake OpenAPI, valid live topic ids and the exact ApplicationAgent delegation. A build wildcard also
requires `list_builds` and `receive_build_events`.

Every App proposal also carries one `agent.toml` whose `tools` list is exactly `reads` plus
`proposals`. agent-runtime uses this allow-list to narrow the capabilities from lake's filtered
OpenAPI. It calls read tools through lake's audited customer-scoped route. A proposal tool only
records its capability and input in the turn result; it never calls the mutation route.

## Writes and confirmation

The custom agent never executes an App or build mutation. It may propose these registered actions:

`create_app`, `deploy_app`, `rollback_app`, `delete_app`, `set_app_env`, `unset_app_env`,
`set_app_auth`, `restart_app`, `stop_app`, `start_app`, `scale_app`,
`set_app_zetta_binding`, `bind_service_to_app`, `unbind_service_from_app`,
`create_service_and_bind_to_app`, `build_image`, `build_app`, and `cancel_build`.

After the person confirms, lake asks `agent-application` for an `app` turn. ApplicationAgent first
returns a reviewable proposal. Lake gives its later turn `create_app` and `deploy_app` only when
`context.confirmed_proposal` is the exact object the person reviewed. This keeps reads in the
custom agent's grant and every write behind human confirmation.

`build_app` is the one action above whose App input is named `app`; App reads and the other App
mutations use `app_id`, while build reads and cancellation use `build_id`.
