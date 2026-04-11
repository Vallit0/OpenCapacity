<div align="center">

<img src="docs/assets/logo.png" alt="OpenCapacity logo" width="180"/>

# OpenCapacity

**Hosting Capacity Analysis for Distributed Generation on Power Distribution Networks**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![OpenDSS](https://img.shields.io/badge/OpenDSS-EPRI-orange)](https://www.epri.com/pages/sa/opendss)
[![Dash](https://img.shields.io/badge/Dash-Plotly-00CC96?logo=plotly&logoColor=white)](https://dash.plotly.com/)
[![Power BI](https://img.shields.io/badge/Power%20BI-Ready-F2C811?logo=powerbi&logoColor=black)](https://powerbi.microsoft.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-active-brightgreen)]()

</div>

---

## Overview

**OpenCapacity** is an open-source platform that computes the **Hosting Capacity** of distribution networks — the maximum amount of Distributed Generation (DG) that can be safely connected at each bus and phase without violating voltage, current or loss limits.

The simulation engine is powered by **OpenDSS** (EPRI), the reference model is the **IEEE 13-Node Test Feeder**, and results are delivered through an interactive **Dash** dashboard and optional **Power BI** reports.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Algorithm](#algorithm)
- [Roadmap](#roadmap)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Features

- Per-bus and per-phase Hosting Capacity calculation via binary search.
- Full power-flow simulation powered by OpenDSS.
- Interactive dashboard built with Dash and Plotly: voltage profiles, line loadings, system losses.
- Manual DG injection for what-if analysis.
- Result export to Excel and JSON for Power BI consumption.
- Reference circuit: IEEE 13-Node Test Feeder (extensible to other feeders).

## Architecture

```
    ┌────────────┐      ┌───────────────┐      ┌────────────┐
    │  IEEE 13   │ ───▶ │    OpenDSS    │ ───▶ │  Analytics │
    │  Feeder    │      │   (engine)    │      │  (Python)  │
    └────────────┘      └───────────────┘      └─────┬──────┘
                                                     │
                          ┌──────────────────────────┼──────────────────────────┐
                          ▼                          ▼                          ▼
                   ┌────────────┐            ┌──────────────┐           ┌──────────────┐
                   │ Dash  App  │            │ Excel / JSON │           │  Power BI    │
                   └────────────┘            └──────────────┘           └──────────────┘
```

## Project Structure

```
OpenCapacity/
├── APP/
│   └── mi_app.py              # Dash dashboard (main application)
├── PROGRAMA DINAMICO/
│   ├── dss_powerbi.py.py      # Exporter for Power BI pipelines
│   └── DASHBOARD1.pbix        # Power BI report template
├── OpenDSS/                   # EPRI OpenDSS engine + IEEE test cases
├── docs/
│   └── assets/                # Logo and diagrams
├── INFORME_TECNICO.md         # Full technical report
├── ROAD_TO_BACKEND.md         # Migration plan to REST backend
└── endpoints_locations.md     # Planned REST API surface
```

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Windows (required by the bundled OpenDSS distribution)
- OpenDSS installed or available via `py-dss-interface` / `opendssdirect.py`

### Installation

```bash
git clone https://github.com/<your-user>/OpenCapacity.git
cd OpenCapacity
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Run the dashboard

```bash
python APP/mi_app.py
```

Then open http://127.0.0.1:8050 in your browser.

## Usage

1. Launch the Dash app.
2. The IEEE 13-Node circuit loads automatically and the base case is solved.
3. Explore the **Hosting Capacity** table (bus × phase).
4. Inject DG manually to run what-if scenarios and inspect voltage profiles and losses.
5. Export results for Power BI from the `PROGRAMA DINAMICO` pipeline.

## Algorithm

Hosting Capacity is computed per bus-phase using a **binary search** over a DG injection range (0 kW – 1,500,000 kW). At every step the circuit is re-solved with OpenDSS and checked against normative limits:

- Bus voltages within [Vmin, Vmax] in per-unit.
- Line currents below `NormAmps`.
- System losses within expected envelope.

The search converges on the maximum DG kW that keeps every constraint satisfied.

## Roadmap

- [x] Desktop dashboard (Dash)
- [x] Power BI export pipeline
- [ ] REST API backend (see `ROAD_TO_BACKEND.md`)
- [ ] Multi-feeder support (IEEE 34, IEEE 123)
- [ ] Time-series / QSTS hosting capacity
- [ ] Docker image and CI
- [ ] Web frontend decoupled from Dash

## Documentation

- [Technical report](INFORME_TECNICO.md) — full description of flow, functions, data models and algorithms.
- [Backend migration plan](ROAD_TO_BACKEND.md)
- [Planned REST endpoints](endpoints_locations.md)

## Contributing

Contributions are welcome. Please open an issue to discuss significant changes before submitting a pull request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Push and open a Pull Request

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

---

<div align="center">

Built with OpenDSS, Python and Dash — for a more open power grid.

</div>
