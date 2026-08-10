# Loop 3 ingestion gate

Status: PASS (bounded experiment materialization)

CSV/Parquet metadata, profiling, sampling and batching are DuckDB-native. SHA-256 is streamed in 1 MiB chunks. LLM samples are capped at 50 records; dynamic experiments refuse materialization over 100,000 records.
