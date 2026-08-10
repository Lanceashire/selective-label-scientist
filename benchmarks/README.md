# Non-credit benchmark

`scripts/run_noncredit_benchmark.py` runs a 5-seed × 3-budget × 3-policy matrix on the public UCI Wisconsin Diagnostic Breast Cancer structured dataset bundled by scikit-learn. The features and target are real public data; the observed/hidden decision mapping is deliberately synthetic and all reports label it **REPLAY MODE / simulation**. It validates protocol behavior and policy trajectories, but cannot establish a real clinical or cross-domain causal selection claim.
