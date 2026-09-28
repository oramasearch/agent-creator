Dated eval reports from `evals/run.py`, run against a real workspace.

- `2026-09-27-evals.*`: first live run against lake.oramadev.net, **15/16**, before prompt v2 added
  methodology-aware cases. The one failure is left as produced: `train-workspace-plain` asked for a
  retraining agent over "our approved churn Pipeline", and AgentCreator read the workspace, found no
  approved Pipeline, and asked which one instead of inventing it.
