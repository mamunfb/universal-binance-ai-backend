from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Body

from app.config import settings
from app.indicators import calculate_indicators
from app.providers.binance_spot import BinanceSpotProvider
from app.providers.binance_futures import BinanceFuturesProvider
from app.services.market_scanner import scan_spot_markets
from app.services.futures_scanner import scan_futures_markets
from app.services.derivatives_intelligence import get_derivatives_intelligence
from app.services.multi_timeframe import analyze_multiple_timeframes, analyze_btc_market_condition
from app.services.liquidation_collector import LiquidationCollector, LiquidationStore
from app.services.price_levels import analyze_support_resistance, calculate_fibonacci_levels
from app.services.volume_structure import calculate_vwap, calculate_volume_profile, analyze_market_structure
from app.providers.news_rss import RSSNewsProvider, parse_feed_sources
from app.services.news_intelligence import collect_news_intelligence
from app.services.news_verification import parse_domain_list
from app.services.catalyst_analysis import analyze_catalysts
from app.providers.evm_rpc import EVMRPCProvider
from app.services.onchain_intelligence import analyze_erc20_activity, get_evm_wallet_snapshot, get_erc20_token_snapshot
from app.services.evm_transfer_store import EVMTransferStore, index_erc20_transfer_history
from app.services.wallet_attribution import load_wallet_registry, annotate_wallet_addresses
from app.services.cross_chain_wallets import parse_chain_rpc_configs, cross_chain_native_wallet_snapshot
from app.services.cross_chain_tokens import parse_chain_token_configs, cross_chain_erc20_snapshot
from app.services.cross_chain_smart_money import cross_chain_verified_wallet_flows

liquidation_store = LiquidationStore(settings.liquidation_database_path)
liquidation_collector = LiquidationCollector(liquidation_store)
news_provider = RSSNewsProvider(settings.http_timeout_seconds)
evm_transfer_store = EVMTransferStore(settings.evm_transfer_database_path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.liquidation_collector_enabled:
        liquidation_collector.start()
    try:
        yield
    finally:
        if settings.liquidation_collector_enabled:
            await liquidation_collector.stop()


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Research-only crypto market data API with Binance Spot/Futures market data, "
        "technical analysis, derivatives snapshots, and optional liquidation collection."
    ),
)


def get_spot_provider() -> BinanceSpotProvider:
    return BinanceSpotProvider(
        base_url=settings.binance_spot_base_url,
        timeout_seconds=settings.http_timeout_seconds,
    )


@app.get("/api/v1/news/intelligence", tags=["news"])
async def news_intelligence(
    symbols: str = "BTC,ETH",
    hours: int = Query(default=72, ge=1, le=720),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    requested_symbols = [value.strip().upper() for value in symbols.split(",") if value.strip()]
    sources = parse_feed_sources(settings.news_rss_feeds)
    return await collect_news_intelligence(
        news_provider, sources, requested_symbols, hours=hours, limit=limit,
        primary_domains=parse_domain_list(settings.news_primary_source_domains),
        independent_domains=parse_domain_list(settings.news_independent_source_domains),
        stale_after_hours=settings.news_stale_after_hours,
    )

@app.get("/api/v1/news/catalysts", tags=["news"])
async def news_catalysts(
    symbols: str = "BTC,ETH",
    hours: int = Query(default=72, ge=1, le=720),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    news = await news_intelligence(symbols=symbols, hours=hours, limit=limit)
    items = analyze_catalysts(news["items"])
    counts = {
        label: sum(1 for item in items if item["catalyst"]["direction"] == label)
        for label in ("BULLISH", "BEARISH", "MIXED", "UNKNOWN")
    }
    return {
        "status": news["status"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_news_status": news["status"],
        "item_count": len(items),
        "direction_counts": counts,
        "items": items,
        "warning": (
            "Keyword-based catalyst triage only. Not a price forecast or trade signal. "
            "Confirm with technical, liquidity, derivatives, and risk checks."
        ),
    }



def get_evm_provider() -> EVMRPCProvider:
    if not settings.evm_rpc_url:
        raise HTTPException(status_code=503, detail={"status": "BLOCKED", "message": "EVM_RPC_URL is not configured."})
    try:
        return EVMRPCProvider(settings.evm_rpc_url, settings.http_timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={"status": "BLOCKED", "error": str(exc)}) from exc


def parse_exchange_addresses(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in raw.split(","):
        if "=" not in entry:
            continue
        label, address = entry.split("=", 1)
        if label.strip() and address.strip():
            result[label.strip()] = address.strip()
    return result


@app.get("/api/v1/onchain/evm/wallets", tags=["on-chain"])
async def evm_wallet_snapshots(addresses: str = Query(..., min_length=42, max_length=5000)) -> dict:
    requested = [value.strip() for value in addresses.split(",") if value.strip()]
    if not 1 <= len(requested) <= 50:
        raise HTTPException(status_code=422, detail="Provide between 1 and 50 wallet addresses.")
    try:
        return await get_evm_wallet_snapshot(get_evm_provider(), requested)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc


@app.get("/api/v1/onchain/evm/token/{contract}/snapshot", tags=["on-chain"])
async def evm_token_snapshot(contract: str, addresses: str = "") -> dict:
    requested = [value.strip() for value in addresses.split(",") if value.strip()]
    watchlist = {f"Tracked wallet {index + 1}": address for index, address in enumerate(requested)}
    watchlist.update(parse_exchange_addresses(settings.evm_exchange_addresses))
    if len(watchlist) > 50:
        raise HTTPException(status_code=422, detail="At most 50 tracked addresses are supported.")
    try:
        return await get_erc20_token_snapshot(get_evm_provider(), contract, watchlist)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc

@app.post("/api/v1/onchain/evm/token/{contract}/index", tags=["on-chain"])
async def index_evm_token_history(
    contract: str,
    payload: dict = Body(..., example={"from_block": 1000000, "to_block": 1001000, "chunk_size": 500}),
) -> dict:
    try:
        from_block = int(payload["from_block"])
        to_block = int(payload["to_block"])
        chunk_size = int(payload.get("chunk_size", 500))
        if chunk_size > settings.evm_max_log_block_span:
            raise ValueError(
                f"chunk_size cannot exceed EVM_MAX_LOG_BLOCK_SPAN ({settings.evm_max_log_block_span})"
            )
        return await index_erc20_transfer_history(
            get_evm_provider(), evm_transfer_store, contract, from_block, to_block,
            chunk_size, settings.evm_index_max_total_blocks,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc


@app.get("/api/v1/onchain/evm/token/{contract}/history", tags=["on-chain"])
async def get_evm_token_history(
    contract: str,
    from_block: int = Query(..., ge=0),
    to_block: int = Query(..., ge=0),
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict:
    if to_block < from_block:
        raise HTTPException(status_code=422, detail="to_block must be >= from_block")
    try:
        provider = get_evm_provider()
        chain_id = await provider.chain_id()
        rows = evm_transfer_store.history(chain_id, contract, from_block, to_block, limit)
        return {
            "status": "COMPLETED", "chain_id": chain_id, "contract_address": contract.lower(),
            "requested_range": {"from": from_block, "to": to_block},
            "returned_count": len(rows), "transfers": rows,
            "indexed_coverage": evm_transfer_store.coverage(chain_id, contract),
            "warning": "Only stored indexed logs are returned. An empty result does not prove there were no transfers unless this range is fully covered.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc


@app.get("/api/v1/onchain/evm/cross-chain/wallets", tags=["on-chain"])
async def cross_chain_wallets(addresses: str = Query(..., description="Comma-separated EVM wallet addresses")) -> dict:
    try:
        requested = [value.strip() for value in addresses.split(",") if value.strip()]
        if not requested:
            raise ValueError("At least one wallet address is required")
        configs = parse_chain_rpc_configs(settings.evm_chain_rpc_urls)
        if not configs:
            raise HTTPException(status_code=503, detail={
                "status": "BLOCKED",
                "message": "Configure EVM_CHAIN_RPC_URLS with one or more HTTPS RPC endpoints."
            })
        result = await cross_chain_native_wallet_snapshot(
            configs, requested, settings.http_timeout_seconds
        )
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)[:300]}) from exc


@app.get("/api/v1/onchain/evm/cross-chain/token/{asset_id}", tags=["on-chain"])
async def cross_chain_token_snapshot(asset_id: str, addresses: str = Query(..., description="Comma-separated EVM wallet addresses")) -> dict:
    try:
        requested = [value.strip() for value in addresses.split(",") if value.strip()]
        configs = parse_chain_token_configs(settings.evm_chain_token_contracts)
        if not configs:
            raise HTTPException(status_code=503, detail={"status": "BLOCKED", "message": "Configure EVM_CHAIN_TOKEN_CONTRACTS with chain-specific asset contracts and HTTPS RPC URLs."})
        return await cross_chain_erc20_snapshot(configs, asset_id, requested, settings.http_timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)[:300]}) from exc


@app.get("/api/v1/onchain/evm/cross-chain/token/{asset_id}/flows", tags=["on-chain"])
async def cross_chain_token_flows(
    asset_id: str,
    from_block: int = Query(..., ge=0),
    to_block: int = Query(..., ge=0),
    decimals: int = Query(..., ge=0, le=36, description="Token decimals; must match the configured asset contracts on every selected chain"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    if to_block < from_block:
        raise HTTPException(status_code=422, detail="to_block must be >= from_block")
    try:
        configs = parse_chain_token_configs(settings.evm_chain_token_contracts)
        selected = [item for item in configs if item["asset_id"] == asset_id.lower()]
        if not selected:
            raise HTTPException(status_code=404, detail="No configured contracts for this asset_id")
        results = []
        for item in selected:
            try:
                provider = EVMRPCProvider(item["rpc_url"], settings.http_timeout_seconds)
                actual_chain_id = await provider.chain_id()
                if actual_chain_id != item["chain_id"]:
                    results.append({
                        "status": "FAILED", "chain_id": actual_chain_id,
                        "expected_chain_id": item["chain_id"], "chain_name": item["chain_name"],
                        "contract_address": item["contract_address"],
                        "error": "RPC chain_id does not match configured chain_id",
                    })
                    continue
                coverage = evm_transfer_store.range_coverage(
                    actual_chain_id, item["contract_address"], from_block, to_block
                )
                flows = evm_transfer_store.address_flow_summary(
                    actual_chain_id, item["contract_address"], from_block, to_block,
                    decimals, limit,
                )
                results.append({
                    "status": "COMPLETED" if coverage["complete"] else "INCOMPLETE",
                    "chain_id": actual_chain_id, "chain_name": item["chain_name"],
                    "asset_id": item["asset_id"], "contract_address": item["contract_address"],
                    "requested_range": {"from": from_block, "to": to_block},
                    "coverage": coverage, "flow_summary": flows,
                })
            except Exception as exc:
                results.append({
                    "status": "FAILED", "chain_id": item["chain_id"],
                    "chain_name": item["chain_name"], "contract_address": item["contract_address"],
                    "error": f"{type(exc).__name__}: {str(exc)[:250]}",
                })
        return {
            "status": "COMPLETED" if results and all(x["status"] == "COMPLETED" for x in results) else "INCOMPLETE",
            "asset_id": asset_id.lower(), "decimals_used": decimals,
            "requested_range": {"from": from_block, "to": to_block},
            "chain_count": len(results), "chains": results,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "warning": "Flows are computed only from locally indexed ERC-20 logs. Inspect per-chain coverage before interpreting results. decimals must be correct for each configured contract; a shared asset_id does not prove economic equivalence. Net transfer flow is not wallet balance, trading intent, or price prediction.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/onchain/evm/cross-chain/token/{asset_id}/smart-money", tags=["on-chain"])
async def cross_chain_smart_money(
    asset_id: str,
    from_block: int = Query(..., ge=0),
    to_block: int = Query(..., ge=0),
    decimals: int = Query(..., ge=0, le=36),
    limit: int = Query(default=50, ge=1, le=200),
    window_blocks: int = Query(default=1000, ge=1, le=1000000),
) -> dict:
    try:
        configs = parse_chain_token_configs(settings.evm_chain_token_contracts)
        return await cross_chain_verified_wallet_flows(
            configs, asset_id, from_block, to_block, decimals,
            settings.evm_wallet_registry, evm_transfer_store,
            settings.http_timeout_seconds, limit, window_blocks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/onchain/evm/cross-chain/token/{asset_id}/intelligence", tags=["on-chain"])
async def cross_chain_token_intelligence(
    asset_id: str,
    from_block: int = Query(..., ge=0),
    to_block: int = Query(..., ge=0),
    decimals: int = Query(..., ge=0, le=36),
    limit: int = Query(default=50, ge=1, le=200),
    window_blocks: int = Query(default=1000, ge=1, le=1000000),
) -> dict:
    """Combine indexed address flows and verified smart-money cohort flows by chain."""
    if to_block < from_block:
        raise HTTPException(status_code=422, detail="to_block must be >= from_block")
    configs = parse_chain_token_configs(settings.evm_chain_token_contracts)
    if not any(item["asset_id"] == asset_id.lower() for item in configs):
        raise HTTPException(status_code=404, detail="No configured contracts for this asset_id")
    flows = await cross_chain_token_flows(
        asset_id, from_block, to_block, decimals, limit,
    )
    cohorts = await cross_chain_verified_wallet_flows(
        configs, asset_id, from_block, to_block, decimals,
        settings.evm_wallet_registry, evm_transfer_store,
        settings.http_timeout_seconds, limit, window_blocks,
    )
    cohort_by_chain = {
        (item["chain_id"], item.get("contract_address", "").lower()): item
        for item in cohorts["chains"]
        if item.get("contract_address")
    }
    chains = []
    for flow in flows["chains"]:
        key = (flow["chain_id"], flow.get("contract_address", "").lower())
        cohort = cohort_by_chain.get(key)
        config = next((item for item in configs
                       if item["chain_id"] == flow["chain_id"]
                       and item["contract_address"].lower() == key[1]), None)
        try:
            registry = load_wallet_registry(settings.evm_wallet_registry, flow["chain_id"])
            entity_flows = evm_transfer_store.verified_label_flows(
                flow["chain_id"], flow["contract_address"], from_block, to_block,
                decimals, registry,
            ) if config else {"verified_label_flows": {}, "warning": "No matching chain configuration."}
            entity_flow_status = "COMPLETED" if config else "UNAVAILABLE"
            verified_wallets = [
                item for item in registry.get("wallets", [])
                if item.get("verification_status") == "verified"
                and item.get("label") in {"exchange", "fund", "market_maker",
                                          "protocol_treasury", "smart_money", "whale"}
            ]
            if not config:
                concentration = {"status": "UNAVAILABLE", "reason": "No matching chain configuration."}
            elif not verified_wallets:
                concentration = {"status": "EMPTY", "verified_wallet_count": 0,
                                  "wallets": [], "by_label": {},
                                  "warning": "No verified registry wallets are configured for this chain."}
            elif len(verified_wallets) > 50:
                concentration = {"status": "INCOMPLETE",
                                  "verified_wallet_count": len(verified_wallets),
                                  "queried_wallet_count": 0,
                                  "reason": "Snapshot limit is 50 verified wallets; reduce the chain registry before querying to avoid a biased partial sample."}
            else:
                snapshot = await cross_chain_erc20_snapshot(
                    [config], asset_id, [item["address"] for item in verified_wallets],
                    settings.http_timeout_seconds,
                )
                chain_snapshot = snapshot["chains"][0]
                label_by_address = {item["address"]: item["label"] for item in verified_wallets}
                groups = {}
                for wallet in chain_snapshot.get("wallets", []):
                    if wallet.get("status") != "COMPLETED":
                        continue
                    label = label_by_address[wallet["address"]]
                    group = groups.setdefault(label, {"wallet_count": 0, "balance_raw": 0})
                    group["wallet_count"] += 1
                    group["balance_raw"] += int(wallet["balance_raw"])
                supply_raw = int(chain_snapshot.get("token", {}).get("total_supply_raw", "0"))
                scale = 10 ** chain_snapshot.get("token", {}).get("decimals", decimals)
                by_label = {
                    label: {
                        "wallet_count": group["wallet_count"],
                        "balance_raw": str(group["balance_raw"]),
                        "balance_tokens": group["balance_raw"] / scale,
                        "share_of_total_supply_pct": (
                            group["balance_raw"] / supply_raw * 100 if supply_raw else None
                        ),
                    } for label, group in groups.items()
                }
                concentration = {
                    "status": chain_snapshot["status"],
                    "snapshot_block": chain_snapshot.get("snapshot_block"),
                    "token": chain_snapshot.get("token"),
                    "verified_wallet_count": len(verified_wallets),
                    "queried_wallet_count": len(chain_snapshot.get("wallets", [])),
                    "successful_wallet_count": sum(
                        1 for item in chain_snapshot.get("wallets", [])
                        if item.get("status") == "COMPLETED"
                    ),
                    "by_label": by_label,
                    "wallets": chain_snapshot.get("wallets", []),
                    "warning": "Snapshot balances are queried at one pinned block per chain. Only verified operator-registry wallets are included; this is not a full holder ranking or complete supply concentration analysis.",
                }
            concentration_status = concentration["status"]
        except Exception as exc:
            entity_flows = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            entity_flow_status = "FAILED"
            concentration = {"status": "FAILED", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            concentration_status = "FAILED"
        flow_coverage = flow.get("coverage", {})
        cohort_coverage = (cohort or {}).get("coverage", {})
        concentration_wallets = concentration.get("wallets", [])
        chains.append({
            "data_quality": {
                "indexed_flow_coverage_complete": flow_coverage.get("complete", False),
                "indexed_flow_gap_count": len(flow_coverage.get("gaps", [])),
                "smart_money_coverage_complete": cohort_coverage.get("complete", False),
                "smart_money_gap_count": len(cohort_coverage.get("gaps", [])),
                "balance_snapshot_block": concentration.get("snapshot_block"),
                "balance_snapshot_status": concentration_status,
                "balance_wallets_queried": concentration.get("queried_wallet_count", 0),
                "balance_wallets_succeeded": concentration.get("successful_wallet_count", 0),
                "balance_wallets_failed": sum(
                    1 for item in concentration_wallets if item.get("status") == "FAILED"
                ),
                "verified_registry_wallet_count": concentration.get("verified_wallet_count", 0),
                "chain_result_status": (
                    "COMPLETED"
                    if flow["status"] == "COMPLETED"
                    and cohort is not None and cohort["status"] == "COMPLETED"
                    and entity_flow_status == "COMPLETED"
                    and concentration_status in {"COMPLETED", "EMPTY"}
                    else "INCOMPLETE"
                ),
                "freshness_note": "Snapshot block height is reported; wall-clock age cannot be determined because block timestamps are not fetched by this endpoint.",
            },
            "chain_id": flow["chain_id"],
            "chain_name": flow.get("chain_name"),
            "contract_address": flow.get("contract_address"),
            "status": (
                "COMPLETED"
                if flow["status"] == "COMPLETED"
                and cohort is not None and cohort["status"] == "COMPLETED"
                and entity_flow_status == "COMPLETED"
                and concentration_status in {"COMPLETED", "EMPTY"}
                else "INCOMPLETE"
            ),
            "address_flows": flow,
            "verified_smart_money": cohort or {
                "status": "UNAVAILABLE",
                "warning": "No matching cohort result for this chain and contract.",
            },
            "verified_entity_flows": {
                "status": entity_flow_status,
                **entity_flows,
            },
            "verified_wallet_concentration": concentration,
        })
    quality_counts = {
        "completed_chains": sum(1 for item in chains if item["status"] == "COMPLETED"),
        "incomplete_chains": sum(1 for item in chains if item["status"] != "COMPLETED"),
        "chains_with_complete_indexed_flow_coverage": sum(
            1 for item in chains if item["data_quality"]["indexed_flow_coverage_complete"]
        ),
        "chains_with_complete_smart_money_coverage": sum(
            1 for item in chains if item["data_quality"]["smart_money_coverage_complete"]
        ),
        "chains_with_successful_balance_snapshot": sum(
            1 for item in chains if item["data_quality"]["balance_snapshot_status"] == "COMPLETED"
        ),
    }
    return {
        "data_quality_summary": quality_counts,
        "status": "COMPLETED" if chains and all(
            item["status"] == "COMPLETED" for item in chains
        ) else "INCOMPLETE",
        "asset_id": asset_id.lower(),
        "requested_range": {"from": from_block, "to": to_block},
        "decimals_used": decimals,
        "chain_count": len(chains),
        "chains": chains,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "warning": (
            "Research-only composite of locally indexed ERC-20 transfers and "
            "operator-verified registry flows and tracked-wallet balance snapshots. Coverage gaps or RPC "
            "failures make results incomplete. Token transfers do not prove trades, "
            "wallet ownership, or investment intent. Concentration covers only configured "
            "verified wallets, not every token holder. Balance snapshot block heights "
            "and token decimals must be interpreted per chain."
        ),
    }


@app.get("/api/v1/onchain/evm/token/{contract}/concentration", tags=["on-chain"])
async def evm_token_concentration(contract: str) -> dict:
    try:
        provider = get_evm_provider()
        chain_id = await provider.chain_id()
        block_number = await provider.block_number()
        registry = load_wallet_registry(settings.evm_wallet_registry, chain_id)
        tracked = {
            f"{item.get('label', 'unknown')}:{item.get('entity_name') or item['address']}": item["address"]
            for item in registry.get("wallets", [])
            if item.get("verification_status") == "verified"
            and item.get("label") in {"smart_money", "exchange", "fund", "market_maker", "protocol_treasury", "whale"}
        }
        snapshot = await get_erc20_token_snapshot(provider, contract, tracked)
        grouped = {}
        for row in snapshot["tracked_balances"]:
            label = row["label"].split(":", 1)[0]
            group = grouped.setdefault(label, {"wallet_count": 0, "balance_raw": 0})
            group["wallet_count"] += 1
            group["balance_raw"] += int(row["balance_raw"])
        scale = 10 ** snapshot["token"]["decimals"]
        concentration = {
            label: {
                "wallet_count": values["wallet_count"],
                "balance_raw": str(values["balance_raw"]),
                "balance_tokens": values["balance_raw"] / scale,
                "share_of_total_supply_pct": (
                    values["balance_raw"] / int(snapshot["token"]["total_supply_raw"]) * 100
                    if int(snapshot["token"]["total_supply_raw"]) else None
                ),
            }
            for label, values in grouped.items()
        }
        return {
            "status": snapshot["status"],
            "chain_id": chain_id,
            "snapshot_block_number": block_number,
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
            "token": snapshot["token"],
            "tracked_wallet_concentration": concentration,
            "tracked_balances": snapshot["tracked_balances"],
            "failed_balances": snapshot["failed_balances"],
            "tracked_addresses_combined_balance_tokens": snapshot["tracked_addresses_combined_balance_tokens"],
            "tracked_addresses_combined_share_of_total_supply_pct": snapshot["tracked_addresses_combined_share_of_total_supply_pct"],
            "registry_status": registry["status"],
            "warning": "Only verified operator-registry addresses are included. This is not a complete holder ranking or full token concentration analysis. Balance calls may be served at different latest blocks by the RPC; snapshot_block_number is the block observed before calls began.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)[:300]}) from exc


@app.get("/api/v1/onchain/evm/wallet-registry", tags=["on-chain"])
async def evm_wallet_registry(addresses: str = "") -> dict:
    try:
        chain_id = await get_evm_provider().chain_id()
        registry = load_wallet_registry(settings.evm_wallet_registry, chain_id)
        if addresses.strip():
            requested = [value.strip() for value in addresses.split(",") if value.strip()]
            if len(requested) > 100:
                raise ValueError("At most 100 addresses can be looked up per request")
            return {
                "status": registry["status"], "chain_id": chain_id,
                "wallets": annotate_wallet_addresses(requested, registry),
                "registry_warning": registry["warning"],
            }
        return registry
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc


@app.get("/api/v1/onchain/evm/token/{contract}/history/flows", tags=["on-chain"])
async def get_evm_token_history_flows(
    contract: str,
    from_block: int = Query(..., ge=0),
    to_block: int = Query(..., ge=0),
    decimals: int = Query(..., ge=0, le=36),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    if to_block < from_block:
        raise HTTPException(status_code=422, detail="to_block must be >= from_block")
    try:
        provider = get_evm_provider()
        chain_id = await provider.chain_id()
        summary = evm_transfer_store.address_flow_summary(
            chain_id, contract, from_block, to_block, decimals, limit
        )
        registry = load_wallet_registry(settings.evm_wallet_registry, chain_id)
        for key in ("top_net_receivers", "top_net_senders"):
            rows = summary[key]
            labels = {
                item["address"]: item
                for item in annotate_wallet_addresses([row["address"] for row in rows], registry)
            }
            for row in rows:
                row["attribution"] = labels[row["address"]]
        return {
            "status": "COMPLETED", "chain_id": chain_id,
            "contract_address": contract.lower(),
            "requested_range": {"from": from_block, "to": to_block},
            "address_flows": summary,
            "indexed_coverage": evm_transfer_store.coverage(chain_id, contract),
            "attribution_warning": registry["warning"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc


@app.get("/api/v1/onchain/evm/token/{contract}/smart-money", tags=["on-chain"])
async def evm_token_smart_money_activity(
    contract: str,
    from_block: int = Query(..., ge=0),
    to_block: int = Query(..., ge=0),
    decimals: int = Query(..., ge=0, le=36),
    limit: int = Query(default=100, ge=1, le=200),
    window_blocks: int = Query(default=1000, ge=1, le=1000000),
) -> dict:
    if to_block < from_block:
        raise HTTPException(status_code=422, detail="to_block must be >= from_block")
    try:
        chain_id = await get_evm_provider().chain_id()
        registry = load_wallet_registry(settings.evm_wallet_registry, chain_id)
        coverage = evm_transfer_store.range_coverage(chain_id, contract, from_block, to_block)
        activity = evm_transfer_store.smart_money_activity(
            chain_id, contract, from_block, to_block, decimals, registry, limit
        )
        trend = evm_transfer_store.smart_money_accumulation_trend(
            chain_id, contract, from_block, to_block, decimals, registry, window_blocks
        )
        return {
            "status": "COMPLETED" if coverage["complete"] else "INCOMPLETE",
            "chain_id": chain_id, "contract_address": contract.lower(),
            "requested_range": {"from": from_block, "to": to_block},
            "coverage": coverage,
            "smart_money_activity": activity,
            "accumulation_trend": trend,
            "registry_status": registry["status"],
            "warning": "Only verified registry labels are treated as smart_money. Incomplete indexed coverage means missing transfers may change these results.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc


@app.get("/api/v1/onchain/evm/token/{contract}/activity", tags=["on-chain"])
async def evm_token_activity(
    contract: str,
    from_block: int = Query(..., ge=0),
    to_block: int = Query(..., ge=0),
    decimals: int = Query(..., ge=0, le=36),
    whale_threshold_tokens: float = Query(default=100000, ge=0),
) -> dict:
    try:
        if to_block < from_block:
            raise ValueError("to_block must be greater than or equal to from_block")
        return await analyze_erc20_activity(
            get_evm_provider(), contract, from_block, to_block, decimals,
            exchange_addresses=parse_exchange_addresses(settings.evm_exchange_addresses),
            whale_threshold_tokens=whale_threshold_tokens,
            max_block_span=settings.evm_max_log_block_span,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


@app.get("/api/v1/markets/spot/scan", tags=["markets"])
async def spot_market_scan(
    quote_asset: str = Query(default="USDT", min_length=2, max_length=12),
    min_quote_volume: float = Query(default=0.0, ge=0.0),
) -> dict:
    result = await scan_spot_markets(
        get_spot_provider(),
        quote_asset=quote_asset,
        min_quote_volume=min_quote_volume,
    )
    if result["status"] == "FAILED":
        raise HTTPException(status_code=502, detail=result)
    return result


def get_futures_provider(market: str) -> BinanceFuturesProvider:
    return BinanceFuturesProvider(market, timeout_seconds=settings.http_timeout_seconds)


@app.get("/api/v1/markets/futures/usdm/scan", tags=["markets"])
async def usdm_market_scan(
    quote_asset: str = Query(default="USDT", min_length=2, max_length=12),
    min_quote_volume: float = Query(default=0.0, ge=0.0),
    perpetual_only: bool = True,
) -> dict:
    result = await scan_futures_markets(
        get_futures_provider("USD_M"), quote_asset, min_quote_volume, perpetual_only
    )
    if result["status"] == "FAILED":
        raise HTTPException(status_code=502, detail=result)
    return result


@app.get("/api/v1/markets/futures/coinm/scan", tags=["markets"])
async def coinm_market_scan(
    quote_asset: str = Query(default="USD", min_length=2, max_length=12),
    min_quote_volume: float = Query(default=0.0, ge=0.0),
    perpetual_only: bool = True,
) -> dict:
    result = await scan_futures_markets(
        get_futures_provider("COIN_M"), quote_asset, min_quote_volume, perpetual_only
    )
    if result["status"] == "FAILED":
        raise HTTPException(status_code=502, detail=result)
    return result


@app.get("/api/v1/markets/futures/usdm/klines/{symbol}", tags=["markets"])
async def usdm_klines(
    symbol: str,
    interval: Literal[
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M"
    ] = "1h",
    limit: int = Query(default=500, ge=1, le=1500),
) -> dict:
    try:
        rows = await get_futures_provider("USD_M").klines(symbol, interval, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc
    return {"status": "COMPLETED", "source": "Binance USD-M Futures public REST API",
            "symbol": symbol.upper(), "interval": interval, "count": len(rows), "klines": rows}


@app.get("/api/v1/markets/futures/coinm/klines/{symbol}", tags=["markets"])
async def coinm_klines(
    symbol: str,
    interval: Literal[
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M"
    ] = "1h",
    limit: int = Query(default=500, ge=1, le=1500),
) -> dict:
    try:
        rows = await get_futures_provider("COIN_M").klines(symbol, interval, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc
    return {"status": "COMPLETED", "source": "Binance COIN-M Futures public REST API",
            "symbol": symbol.upper(), "interval": interval, "count": len(rows), "klines": rows}


@app.get("/api/v1/analysis/futures/usdm/derivatives/{symbol}", tags=["analysis"])
async def usdm_derivatives_intelligence(
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"] = "1h",
    history_limit: int = Query(default=30, ge=1, le=100),
    order_book_limit: Literal[5, 10, 20, 50, 100, 500, 1000] = 100,
) -> dict:
    try:
        return await get_derivatives_intelligence(
            get_futures_provider("USD_M"),
            symbol=symbol,
            period=period,
            history_limit=history_limit,
            order_book_limit=order_book_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc


@app.get("/api/v1/analysis/spot/technical/{symbol}", tags=["analysis"])
async def spot_technical_analysis(
    symbol: str,
    interval: Literal[
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M"
    ] = "1h",
    limit: int = Query(default=500, ge=2, le=1000),
) -> dict:
    try:
        rows = await get_spot_provider().klines(symbol, interval, limit)
        closes = [float(row[4]) for row in rows]
        indicators = calculate_indicators(closes)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc
    return {
        "status": "COMPLETED",
        "source": "Binance Spot public REST API",
        "symbol": symbol.upper(),
        "interval": interval,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "indicators": indicators,
        "warning": "Indicators describe historical data and are not guaranteed trading signals.",
    }


@app.get("/api/v1/analysis/spot/multi-timeframe/{symbol}", tags=["analysis"])
async def spot_multi_timeframe_analysis(symbol: str) -> dict:
    return await analyze_multiple_timeframes(get_spot_provider(), symbol)


@app.get("/api/v1/analysis/market/btc-condition", tags=["analysis"])
async def btc_market_condition() -> dict:
    return await analyze_btc_market_condition(get_spot_provider())


@app.get("/api/v1/analysis/spot/price-levels/{symbol}", tags=["analysis"])
async def spot_price_levels(
    symbol: str,
    interval: Literal["15m", "1h", "4h", "1d"] = "1h",
    limit: int = Query(default=300, ge=20, le=1000),
    pivot_left: int = Query(default=3, ge=1, le=20),
    pivot_right: int = Query(default=3, ge=1, le=20),
    tolerance_pct: float = Query(default=0.003, gt=0, le=0.05),
) -> dict:
    try:
        rows = await get_spot_provider().klines(symbol, interval, limit)
        support_resistance = analyze_support_resistance(
            rows, pivot_left=pivot_left, pivot_right=pivot_right,
            tolerance_pct=tolerance_pct,
        )
        fibonacci = calculate_fibonacci_levels(
            rows, pivot_left=pivot_left, pivot_right=pivot_right
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc
    return {
        "status": "COMPLETED" if support_resistance["status"] == "COMPLETED" and fibonacci["status"] == "COMPLETED" else "INCOMPLETE",
        "source": "Binance Spot public REST klines",
        "symbol": symbol.upper(),
        "interval": interval,
        "candle_count": len(rows),
        "support_resistance": support_resistance,
        "fibonacci": fibonacci,
        "warning": "Technical reference calculations only; not trading signals or guaranteed support/resistance.",
    }


@app.get("/api/v1/analysis/spot/volume-structure/{symbol}", tags=["analysis"])
async def spot_volume_structure(
    symbol: str,
    interval: Literal["15m", "1h", "4h", "1d"] = "1h",
    limit: int = Query(default=300, ge=20, le=1000),
    anchor_index: int = Query(default=0, ge=0),
    profile_bins: int = Query(default=48, ge=5, le=200),
    value_area_pct: float = Query(default=0.70, ge=0.5, le=0.95),
    pivot_left: int = Query(default=3, ge=1, le=20),
    pivot_right: int = Query(default=3, ge=1, le=20),
) -> dict:
    try:
        rows = await get_spot_provider().klines(symbol, interval, limit)
        if anchor_index >= len(rows):
            raise ValueError("anchor_index must be smaller than returned candle count")
        vwap = calculate_vwap(rows, anchor_index=anchor_index)
        volume_profile = calculate_volume_profile(
            rows, bins=profile_bins, value_area_pct=value_area_pct
        )
        market_structure = analyze_market_structure(
            rows, pivot_left=pivot_left, pivot_right=pivot_right
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc
    sections = [vwap["status"], volume_profile["status"], market_structure["status"]]
    return {
        "status": "COMPLETED" if all(s == "COMPLETED" for s in sections) else "INCOMPLETE",
        "source": "Binance Spot public REST klines",
        "symbol": symbol.upper(),
        "interval": interval,
        "candle_count": len(rows),
        "vwap": vwap,
        "volume_profile": volume_profile,
        "market_structure": market_structure,
        "warning": "OHLCV-based approximations only. No trade-level volume-at-price, order-book liquidity map, or guaranteed trading signal is provided.",
    }


@app.get("/api/v1/analysis/futures/liquidations/status", tags=["analysis"])
async def liquidation_collector_status() -> dict:
    if not settings.liquidation_collector_enabled:
        return {
            "status": "DISABLED",
            "collector_enabled": False,
            "message": "Set LIQUIDATION_COLLECTOR_ENABLED=true and run a persistent service to collect live events.",
            "stored_event_count": liquidation_store.count(),
        }
    return liquidation_collector.status()


@app.get("/api/v1/analysis/futures/liquidations/recent", tags=["analysis"])
async def recent_liquidations(
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    rows = await __import__("asyncio").to_thread(
        liquidation_store.recent, symbol, limit
    )
    return {
        "status": "COMPLETED",
        "source": "Binance USDⓈ-M all-market forceOrder WebSocket snapshot stream",
        "symbol": symbol.upper() if symbol else None,
        "returned_count": len(rows),
        "events": rows,
        "coverage_warning": "Binance sends at most the latest liquidation snapshot per symbol per 1000ms. This is not a complete liquidation tape or historical exchange archive.",
    }


@app.get("/api/v1/markets/spot/klines/{symbol}", tags=["markets"])
async def spot_klines(
    symbol: str,
    interval: Literal[
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
        "6h", "8h", "12h", "1d", "3d", "1w", "1M"
    ] = "1h",
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict:
    try:
        rows = await get_spot_provider().klines(symbol, interval, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": str(exc)}) from exc
    return {
        "status": "COMPLETED",
        "source": "Binance Spot public REST API",
        "symbol": symbol.upper(),
        "interval": interval,
        "count": len(rows),
        "klines": rows,
    }
