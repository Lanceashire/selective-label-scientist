# Loop 1 protocol gate

Status: PASS

`PartitionedUniverse` enforces mutually-exclusive visible/candidate/forbidden/oracle sets, only permits choices from the current batch, and removes all departed candidates so historical backlog cannot re-enter later rounds. `tests_agent/test_beta_protocol.py` executes 100 seeded invariant trials.
