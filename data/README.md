# Data contents

| Path | Tracked | Purpose |
| --- | --- | --- |
| `demo/demo_transactions.csv` | Yes | Deterministic synthetic end-to-end demo with 240 customers |
| `sample/online_retail_sample.csv` | Yes | Small edge-case fixture used by tests |
| `raw/` | No | Official UCI workbook downloaded by `growthpilot download` |
| `interim/` | No | Temporary pipeline state |
| `processed/` | No | Canonical purchases, returns, rejected rows, features, and training snapshots |

Generated data is ignored so a normal GitHub push stays below platform limits and never accidentally publishes licensed source data. Empty `.gitkeep` files preserve the expected directory structure.

The synthetic demo CSV is reproducible:

```bash
python -m growthpilot demo-data --output data/demo/demo_transactions.csv --customers 240 --seed 42
```

The full public dataset is reproducible from its publisher:

```bash
python -m growthpilot download
python -m growthpilot phase1 --input data/raw/online_retail_II.xlsx
```
