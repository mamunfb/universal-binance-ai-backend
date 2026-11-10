# Upstream Repository Integration Plan

This repository is the central project. Upstream code will be added only after review.

## Candidate sources

| Project | Upstream URL | Intended use | Integration rule |
|---|---|---|---|
| Binance Connector Python | https://github.com/binance/binance-connector-python | Official Binance API client | Evaluate as an optional provider dependency |
| CCXT | https://github.com/ccxt/ccxt | Unified exchange interfaces | Evaluate as an alternative adapter; avoid duplicate exchange clients |
| FastMCP | https://github.com/jlowin/fastmcp | MCP server framework | Evaluate for a later MCP adapter |
| TA-Lib Python | https://github.com/TA-Lib/ta-lib-python | Technical indicators | Evaluate installation requirements and license |
| Freqtrade | https://github.com/freqtrade/freqtrade | Research and backtesting reference | Do not copy wholesale; inspect GPL obligations first |

## Required review before importing
1. Confirm the upstream repository and current default branch.
2. Read the upstream LICENSE and relevant dependency licenses.
3. Check maintenance activity, releases, security issues, and compatibility.
4. Choose package dependency, Git submodule, or separately maintained fork.
5. Preserve copyright and license notices.
6. Record the exact upstream commit or tag and local modifications.
7. Run tests and security checks after integration.

## License caution
Some candidate projects may use copyleft licenses. Do not copy or combine code into a private or commercial distribution until applicable obligations have been reviewed. This checklist is not legal advice.

## Import status
No upstream source code has been copied into this repository yet.
