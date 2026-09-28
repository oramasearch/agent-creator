# Solution-bound agents

AgentCreator can bind an agent to one live catalogue solution. It does not carry an S-number or
B-number table. At the start of every turn it calls `list_solutions`, then calls `get_solution` for
each returned id. The detailed reads, not an earlier conversation turn or local product knowledge,
are the facts given to the model and the deterministic proposal review.

An engine that returns `unknown_capability` for `list_solutions` has no solutions for this turn.
AgentCreator describes the registry as “not deployed yet”; it does not use a compatibility
solution. Other read failures are reported and do not make a solution available.

## Proposal binding

When the person's business problem matches a runnable, non-sketch entry, the proposal contains one
binding:

```json
{
  "solution": {
    "id": "S-n",
    "capabilities": ["decide", "list_ledger", "get_monitor", "get_roi_readout"],
    "autonomy": [
      {"action_class": "an action from the registry", "autonomy": "A1"}
    ],
    "approval_gates": ["every A1 action class"]
  }
}
```

The four capabilities let the resulting agent make a policy-governed decision, inspect the audit
ledger, inspect the monitor and report measured value. `approve_decision` is deliberately absent:
an operating agent cannot release its own A1 decision. `record_action` and `record_outcome` are also
not granted by this binding; those writes remain with the solution's governed operation path.

The review in `definition/agent/main.py` checks the id against this turn's `get_solution` results,
requires `runnable: true`, rejects sketches, requires exactly the four capabilities above, copies
the complete `autonomy_defaults` list without changes, and requires every A1 action class in
`approval_gates`. Adding authority, changing an autonomy class, dropping an A1 gate or adding
`approve_decision` makes the proposal defective and triggers the one repair round.

## Refusals

A matching entry that is not runnable produces a structured decline with its live `issue`. A
sketch decline also repeats its live `promotion_condition`. If the registry is not deployed, the
decline names `list_solutions` and says it is not deployed yet.

If no catalogue entry matches the request, the existing methodology and approved-Pipeline path
still applies. Solution operation never promises return figures, prices or odds of success;
`get_roi_readout` is the only source for measured value.

## Evaluation

Unit tests cover turn-scoped list and detail reads, detailed-read precedence, runnable bindings,
non-runnable entries, sketches, older engines, exact autonomy, A1 gates and lake's
`workspace_query` envelope. The generated live eval matrix adds one runnable solution and one
unsupported solution when the registry provides them, or a registry-not-deployed case on an older
engine.
