# blackroad-conversion-tracker

Multi-touch attribution, funnel analysis, and conversion rate tracking for BlackRoad OS.

## Features

- **4 Attribution Models**: Last-click, First-click, Linear, Time-decay
- **Funnel Analysis**: Step-by-step drop-off visualization with ASCII charts
- **Conversion Rate Tracking**: Unique visitors vs. goal completions
- **Cohort Analysis**: Weekly cohorts with 1w/2w/4w conversion windows
- **Goal Performance**: Aggregate stats across all goals
- **Export**: JSON and CSV report export

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# Define a goal with funnel steps
python src/conversion_tracker.py goal "Signup" signup_complete \
  --value-per-conversion 25.0 \
  --funnel-steps "page_view,form_start,signup_complete"

# Track an event
python src/conversion_tracker.py track visitor_001 session_001 page_view \
  --source google --medium cpc --campaign summer

# View funnel report
python src/conversion_tracker.py funnel 1

# Attribution report
python src/conversion_tracker.py attribute 1 --model time_decay

# Goal performance
python src/conversion_tracker.py report

# Cohort analysis
python src/conversion_tracker.py cohort 1 --weeks 8

# Export report
python src/conversion_tracker.py export 1 --format json --output report.json

# List all goals
python src/conversion_tracker.py goals
```

## Attribution Models

| Model | Description |
|-------|-------------|
| `last_click` | 100% credit to final touchpoint |
| `first_click` | 100% credit to first touchpoint |
| `linear` | Equal credit across all touchpoints |
| `time_decay` | Exponential weighting, recency favored (half-life 7 days) |

## Running Tests

```bash
pytest tests/ -v --cov=src
```

## License

Proprietary — BlackRoad OS, Inc. All rights reserved.
