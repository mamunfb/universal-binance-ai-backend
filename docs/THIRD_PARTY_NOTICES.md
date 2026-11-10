# Third-Party Notices and Integration Decisions

This file records the license information checked from upstream repository metadata during initial integration review. Re-check the exact release/tag and its license before distributing a build.

| Project | Upstream | Evidence checked | License indicated | Decision |
|---|---|---|---|---|
| Binance Python Connector | https://github.com/binance/binance-connector-python | Upstream README license badge | MIT | Not copied; initial backend uses Binance public REST endpoints through HTTPX |
| CCXT | https://github.com/ccxt/ccxt | Upstream pyproject.toml project metadata | MIT | Optional dependency only; not installed by default |
| FastMCP | https://github.com/PrefectHQ/fastmcp | Upstream LICENSE and pyproject.toml | Apache-2.0 | Optional dependency only; MCP adapter not implemented |
| TA-Lib Python | https://github.com/TA-Lib/ta-lib-python | Upstream LICENSE | BSD-2-Clause | Optional dependency only; current indicators are implemented in local Python code |
| Freqtrade | https://github.com/freqtrade/freqtrade | Upstream LICENSE and pyproject.toml | GPL-3.0-only | Not copied or imported; use only after a separate license compatibility review |

## Important
- A package dependency is not the same as copying or relicensing upstream source code.
- Preserve upstream license and copyright notices when redistributing third-party components.
- This inventory is a technical record, not legal advice.
- Re-check license files at the exact version/commit selected for a release.
