Dated eval reports from `evals/run.py`, run against a real workspace.

- `2026-09-27-evals.*`: first live run against lake.oramadev.net, **15/16**, before prompt v2 added
  methodology-aware cases. The one failure is left as produced: `train-workspace-plain` asked for a
  retraining agent over "our approved churn Pipeline", and AgentCreator read the workspace, found no
  approved Pipeline, and asked which one instead of inventing it.
- Prompt v3 adds live solution bindings and solution-aware eval cases. No prompt-v3 live report is
  recorded here; the existing report and score remain unchanged.
- Prompt v5 adds Lake's own areas as skills (agent-runtime#7). No prompt-v5 live report is recorded
  here yet: it needs a Lake with the twelve skills deployed (lake#650 and the workspace engine's
  skill list).
