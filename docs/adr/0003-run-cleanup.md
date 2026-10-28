# Explicit cleanup of verified closed runs

Status: accepted.

Local run folders are private working state. Cleanup is an explicit operator action, only for done/rejected/failed runs with a live-verified log-book page. Never prune active, awaiting-approval, or awaiting-PO runs. Retain status and append a pruning ledger entry.
