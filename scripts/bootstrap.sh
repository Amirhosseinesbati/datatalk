#!/bin/sh
set -eu

python /app/scripts/seed_data.py --profile fast --output /app/data/generated/fast
python -m datatalk.cli init-db
python -m datatalk.cli load-data --dir /app/data/generated/fast
