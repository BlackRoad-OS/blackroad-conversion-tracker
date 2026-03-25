<!-- BlackRoad SEO Enhanced -->

# ulackroad conversion tracker

> Part of **[BlackRoad OS](https://blackroad.io)** — Sovereign Computing for Everyone

[![BlackRoad OS](https://img.shields.io/badge/BlackRoad-OS-ff1d6c?style=for-the-badge)](https://blackroad.io)
[![BlackRoad OS](https://img.shields.io/badge/Org-BlackRoad-OS-2979ff?style=for-the-badge)](https://github.com/BlackRoad-OS)
[![License](https://img.shields.io/badge/License-Proprietary-f5a623?style=for-the-badge)](LICENSE)

**ulackroad conversion tracker** is part of the **BlackRoad OS** ecosystem — a sovereign, distributed operating system built on edge computing, local AI, and mesh networking by **BlackRoad OS, Inc.**

## About BlackRoad OS

BlackRoad OS is a sovereign computing platform that runs AI locally on your own hardware. No cloud dependencies. No API keys. No surveillance. Built by [BlackRoad OS, Inc.](https://github.com/BlackRoad-OS-Inc), a Delaware C-Corp founded in 2025.

### Key Features
- **Local AI** — Run LLMs on Raspberry Pi, Hailo-8, and commodity hardware
- **Mesh Networking** — WireGuard VPN, NATS pub/sub, peer-to-peer communication
- **Edge Computing** — 52 TOPS of AI acceleration across a Pi fleet
- **Self-Hosted Everything** — Git, DNS, storage, CI/CD, chat — all sovereign
- **Zero Cloud Dependencies** — Your data stays on your hardware

### The BlackRoad Ecosystem
| Organization | Focus |
|---|---|
| [BlackRoad OS](https://github.com/BlackRoad-OS) | Core platform and applications |
| [BlackRoad OS, Inc.](https://github.com/BlackRoad-OS-Inc) | Corporate and enterprise |
| [BlackRoad AI](https://github.com/BlackRoad-AI) | Artificial intelligence and ML |
| [BlackRoad Hardware](https://github.com/BlackRoad-Hardware) | Edge hardware and IoT |
| [BlackRoad Security](https://github.com/BlackRoad-Security) | Cybersecurity and auditing |
| [BlackRoad Quantum](https://github.com/BlackRoad-Quantum) | Quantum computing research |
| [BlackRoad Agents](https://github.com/BlackRoad-Agents) | Autonomous AI agents |
| [BlackRoad Network](https://github.com/BlackRoad-Network) | Mesh and distributed networking |
| [BlackRoad Education](https://github.com/BlackRoad-Education) | Learning and tutoring platforms |
| [BlackRoad Labs](https://github.com/BlackRoad-Labs) | Research and experiments |
| [BlackRoad Cloud](https://github.com/BlackRoad-Cloud) | Self-hosted cloud infrastructure |
| [BlackRoad Forge](https://github.com/BlackRoad-Forge) | Developer tools and utilities |

### Links
- **Website**: [blackroad.io](https://blackroad.io)
- **Documentation**: [docs.blackroad.io](https://docs.blackroad.io)
- **Chat**: [chat.blackroad.io](https://chat.blackroad.io)
- **Search**: [search.blackroad.io](https://search.blackroad.io)

---


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
