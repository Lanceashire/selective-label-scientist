# Non-credit benchmarks

`scripts/run_noncredit_benchmark.py` runs a 5-seed × 3-budget × 3-policy matrix on the public UCI Wisconsin Diagnostic Breast Cancer structured dataset bundled by scikit-learn. The features and target are real public data, but the observed/hidden decision mapping is deliberately synthetic. All reports label it **REPLAY MODE / simulation**. It validates protocol behavior and policy trajectories but cannot establish a historical clinical or cross-domain causal selection claim.

`scripts/run_sandiego_historical_audit.py` is the complementary real historical non-credit audit. It consumes the City of San Diego's public October 2017–June 2018 vehicle-stops CSV. Download that public file into `benchmarks/data/san_diego_vehicle_stops_2017_2018.csv`; this data directory is deliberately ignored by Git. The audit records the source hash, documented search decision, real label-availability pattern, observation semantics, and the absence of a separate outcome timestamp.

This second artifact is intentionally **not** labelled a dynamic-policy or final-metric benchmark: no contraband label exists for unsearched stops, so ECOMIC blocks oracle evaluation rather than imputing a result. It supplies real cross-domain selective-label evidence while keeping historical missingness analysis distinct from an oracle-backed replay simulation.
