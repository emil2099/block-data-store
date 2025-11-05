# Performance Smoke Test Guide

The `scripts/perf_smoke.py` helper ingests the same Markdown document over and
over, keeps every copy in the store, and records per-document timings at key
checkpoints so you can observe how fetch, render, and document-scoped filter
performance change as the corpus grows.

## Running the test with on-disk SQLite

```bash
python3 scripts/perf_smoke.py \
  --steps 1,10,100,1000,10000 \
  --sample-size 10 \
  --sqlite-path ./perf_smoke.db \
  --log-interval 200 \
  --output telemetry.json
```

Notes:

- `--steps` controls which iteration checkpoints are sampled (default
  `1,10,100,1000`). As the corpus grows, each checkpoint repeats the measurements.
- `--sample-size` sets how many documents are averaged at each checkpoint
  (default 10). Increase it if your content varies widely.
- Use `--sqlite-path` or `--database-url` to target SQLite or Postgres;
  `--reset-schema` wipes existing tables.
- Adjust `--log-interval` or `--quiet` to manage log verbosity during long runs.
- If you re-run on the same SQLite file, remove it first to start with an empty
  store.

## Telemetry output anatomy

`telemetry.json` collects an entry per checkpoint under `checkpoints`:

| Field | Meaning |
| --- | --- |
| `documents` | Total documents ingested so far. |
| `sample_size` | Number of documents sampled to compute averages (default 10). |
| `avg_fetch_ms` | Average time to hydrate a sampled document via `get_root_tree`. |
| `avg_render_ms` | Average time to render the sampled documents via `MarkdownRenderer`. |
| `avg_render_length` | Average character length of the rendered Markdown for the sample. |
| `avg_filter_paragraph_ms` | Average time to fetch all paragraphs within each sampled document. |
| `avg_filter_parent_ms` | Average time to run the parent-filter query within each sampled document. |
| `avg_paragraph_count` | Average paragraph count per sampled document. |
| `avg_parent_count` | Average matches for the parent-filter query per sampled document. |
| `total_blocks` | Total blocks persisted in the store at the checkpoint. |

You can plot these fields (e.g. documents vs. `avg_fetch_ms`) to visualise how
per-document operations behave as the corpus grows. The helper also writes
`docs/perf_smoke_summary.csv` for easy import into spreadsheet/plotting tools.
