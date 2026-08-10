# Loop 7 evaluator gate

Status: PASS

Final metrics are calculated inside `DynamicSelectiveLabelEnvironment.finalize`; the agent never supplies a metrics dictionary. Finalization is single-use and blocks further rounds. This is covered by `test_dynamic_rounds_and_oracle_once`.
