import asyncio
from contextlib import asynccontextmanager
import hmac
from datetime import datetime, timezone
import json
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Body, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.indicators import calculate_indicators
from app.providers.binance_spot import BinanceSpotProvider
from app.providers.binance_futures import BinanceFuturesProvider
from app.services.market_scanner import scan_spot_markets
from app.services.futures_scanner import scan_futures_markets
from app.services.derivatives_intelligence import get_derivatives_intelligence
from app.services.spot_futures_basis import analyze_spot_futures_basis
from app.services.market_evidence import build_market_evidence_snapshot
from app.services.multi_timeframe import analyze_multiple_timeframes, analyze_btc_market_condition
from app.services.liquidation_collector import LiquidationCollector, LiquidationStore
from app.services.price_levels import analyze_support_resistance, calculate_fibonacci_levels
from app.services.volume_structure import calculate_vwap, calculate_volume_profile, analyze_market_structure
from app.providers.news_rss import RSSNewsProvider, parse_feed_sources
from app.services.news_intelligence import collect_news_intelligence
from app.services.news_verification import parse_domain_list
from app.services.catalyst_analysis import analyze_catalysts
from app.services.trade_risk import build_trade_risk_plan
from app.services.signal_lifecycle import build_signal_lifecycle
from app.providers.evm_rpc import EVMRPCProvider
from app.services.onchain_intelligence import analyze_erc20_activity, get_evm_wallet_snapshot, get_erc20_token_snapshot
from app.services.evm_transfer_store import EVMTransferStore, index_erc20_transfer_history
from app.services.historical_klines import HistoricalKlineStore
from app.services.funding_rates import FundingRateStore
from app.services.open_interest import OpenInterestStore
from app.services.derivatives_ratio_store import DerivativesRatioStore
from app.services.combined_derivatives_intelligence import CombinedDerivativesIntelligence
from app.services.market_regime import MarketRegimeAnalysis
from app.services.liquidation_clusters import LiquidationClusterAnalysis
from app.services.historical_signal_performance import HistoricalSignalPerformance
from app.services.smart_money_structure import SmartMoneyMarketStructure
from app.services.order_book_intelligence import analyze_order_book
from app.services.order_book_stream import OrderBookHistoryStore, OrderBookStreamCollector
from app.services.aggregate_trade_stream import AggregateTradeStore, AggregateTradeCollector
from app.services.liquidity_behavior import analyze_liquidity_behavior
from app.services.order_flow_intelligence import analyze_order_flow
from app.services.multi_timeframe_order_flow import analyze_multi_timeframe_order_flow
from app.services.liquidity_sweep_confirmation import analyze_liquidity_sweep_confirmation
from app.services.market_structure_confluence import analyze_market_structure_confluence
from app.services.market_confluence_store import MarketConfluenceStore
from app.services.market_confluence_performance import MarketConfluencePerformance
from app.services.derivatives_collector import DerivativesHistoryCollector
from app.services.funding_open_interest_analysis import FundingOpenInterestAnalysis
from app.services.advanced_derivatives_analysis import AdvancedDerivativesAnalysis, DerivativesSignalStore
from app.services.multi_timeframe_derivatives import MultiTimeframeDerivativesAnalysis
from app.services.historical_coverage import HistoricalCoverageEngine
from app.services.market_data_quality import MarketDataQualityEngine
from app.services.historical_collector import HistoricalKlineCollector
from app.services.wallet_attribution import load_wallet_registry, annotate_wallet_addresses
from app.services.cross_chain_wallets import parse_chain_rpc_configs, cross_chain_native_wallet_snapshot
from app.services.cross_chain_tokens import parse_chain_token_configs, cross_chain_erc20_snapshot
from app.services.cross_chain_smart_money import cross_chain_verified_wallet_flows

liquidation_store = LiquidationStore(settings.liquidation_database_path)
liquidation_collector = LiquidationCollector(liquidation_store)
order_book_history_store = OrderBookHistoryStore(settings.order_book_database_path)
order_book_collector: OrderBookStreamCollector | None = None
aggregate_trade_store = AggregateTradeStore(settings.aggregate_trade_database_path)
aggregate_trade_collector: AggregateTradeCollector | None = None
news_provider = RSSNewsProvider(settings.http_timeout_seconds)
evm_transfer_store = EVMTransferStore(settings.evm_transfer_database_path)
historical_kline_store = HistoricalKlineStore(settings.historical_kline_database_path)
funding_rate_store = FundingRateStore(settings.funding_rate_database_path)
open_interest_store = OpenInterestStore(settings.open_interest_database_path)
derivatives_signal_store = DerivativesSignalStore(settings.derivatives_signal_database_path)
derivatives_ratio_store = DerivativesRatioStore(settings.derivatives_ratio_database_path)
market_confluence_store = MarketConfluenceStore(settings.market_confluence_database_path)
market_confluence_performance = MarketConfluencePerformance(market_confluence_store, historical_kline_store)
historical_collector: HistoricalKlineCollector | None = None
derivatives_collector: DerivativesHistoryCollector | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global historical_collector, derivatives_collector, order_book_collector, aggregate_trade_collector
    if settings.liquidation_collector_enabled:
        liquidation_collector.start()
    if settings.order_book_collector_enabled:
        order_book_collector = OrderBookStreamCollector(
            store=order_book_history_store,
            spot_provider_factory=get_spot_provider,
            futures_provider_factory=get_futures_provider,
            jobs_json=settings.order_book_collector_jobs,
            sample_interval_seconds=settings.order_book_sample_interval_seconds,
            snapshot_limit=settings.order_book_snapshot_limit,
            stored_levels=settings.order_book_stored_levels,
        )
        order_book_collector.start()
    if settings.aggregate_trade_collector_enabled:
        aggregate_trade_collector = AggregateTradeCollector(
            store=aggregate_trade_store,
            jobs_json=settings.aggregate_trade_collector_jobs,
        )
        aggregate_trade_collector.start()
    if settings.derivatives_collector_enabled:
        derivatives_collector = DerivativesHistoryCollector(
            funding_store=funding_rate_store,
            open_interest_store=open_interest_store,
            provider_factory=get_futures_provider,
            jobs_json=settings.derivatives_collector_jobs,
            poll_seconds=settings.derivatives_collector_poll_seconds,
            funding_limit=settings.derivatives_collector_funding_limit,
            open_interest_limit=settings.derivatives_collector_open_interest_limit,
        )
        derivatives_collector.start()
    if settings.historical_collector_enabled:
        historical_collector = HistoricalKlineCollector(
            store=historical_kline_store,
            spot_provider_factory=get_spot_provider,
            futures_provider_factory=get_futures_provider,
            jobs_json=settings.historical_collector_jobs,
            poll_seconds=settings.historical_collector_poll_seconds,
            initial_limit=settings.historical_collector_initial_limit,
        )
        historical_collector.start()
    try:
        yield
    finally:
        if order_book_collector is not None:
            await order_book_collector.stop()
            order_book_collector = None
        if aggregate_trade_collector is not None:
            await aggregate_trade_collector.stop()
            aggregate_trade_collector = None
        if derivatives_collector is not None:
            await derivatives_collector.stop()
            derivatives_collector = None
        if settings.historical_collector_enabled and historical_collector is not None:
            await historical_collector.stop()
            historical_collector = None
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

def _error_payload(
    code: str, message: str, details: dict | list | None = None,
    request_id: str | None = None,
) -> dict:
    """Return a stable, machine-readable API error envelope."""
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    payload = {"status": "FAILED", "error": error}
    if request_id:
        payload["request_id"] = request_id
    return payload


@app.middleware("http")
async def request_tracking_middleware(request: Request, call_next):
    request_id = uuid4().hex
    request.state.request_id = request_id

    if request.url.path.startswith("/api/"):
        configured_key = settings.personal_api_key
        try:
            client_keys = json.loads(settings.ai_client_api_keys or "{}")
            if not isinstance(client_keys, dict) or any(
                not isinstance(name, str) or not isinstance(key, str)
                for name, key in client_keys.items()
            ):
                raise ValueError("AI_CLIENT_API_KEYS must be a JSON object of client names to keys")
        except (TypeError, ValueError, json.JSONDecodeError):
            client_keys = None

        production = settings.app_env.lower() in {"production", "prod"}
        has_valid_client_keys = (
            isinstance(client_keys, dict)
            and all(
                isinstance(client_keys.get(name), str) and len(client_keys[name]) >= 32
                for name in ("chatgpt", "gemini", "manus", "claude", "perplexity")
            )
        )
        if production and (
            client_keys is None
            or not has_valid_client_keys
            and len(configured_key) < 32
        ):
            response = JSONResponse(
                status_code=503,
                content=_error_payload(
                    "AUTH_NOT_CONFIGURED",
                    "Configure strong private API keys for all AI clients or a strong owner key.",
                    request_id=request_id,
                ),
            )
            response.headers["X-Request-ID"] = request_id
            return response

        if configured_key or client_keys:
            authorization = request.headers.get("authorization", "")
            scheme, _, supplied_key = authorization.partition(" ")
            matched_client = None
            if scheme.lower() == "bearer" and supplied_key:
                if isinstance(client_keys, dict):
                    for client_name, client_key in client_keys.items():
                        if hmac.compare_digest(
                            supplied_key.encode("utf-8"), client_key.encode("utf-8")
                        ):
                            matched_client = client_name
                            break
                if configured_key and hmac.compare_digest(
                    supplied_key.encode("utf-8"), configured_key.encode("utf-8")
                ):
                    matched_client = "owner"
            if matched_client is None:
                response = JSONResponse(
                    status_code=401,
                    content=_error_payload(
                        "UNAUTHORIZED",
                        "A valid private Bearer API key is required.",
                        request_id=request_id,
                    ),
                    headers={"WWW-Authenticate": "Bearer"},
                )
                response.headers["X-Request-ID"] = request_id
                return response
            request.state.ai_client = matched_client

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "location": list(item.get("loc", ())),
            "message": item.get("msg", "Invalid value"),
            "type": item.get("type", "validation_error"),
        }
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            "VALIDATION_ERROR", "Request parameters or body failed validation.", details,
            getattr(request.state, "request_id", None)
        ),
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    status_codes = {
        400: ("BAD_REQUEST", "The request could not be processed."),
        401: ("UNAUTHORIZED", "Authentication is required."),
        403: ("FORBIDDEN", "The request is not permitted."),
        404: ("NOT_FOUND", "The requested resource was not found."),
        409: ("CONFLICT", "The request conflicts with the current resource state."),
        422: ("VALIDATION_ERROR", "The request could not be validated."),
        429: ("RATE_LIMITED", "The request rate limit was exceeded."),
        502: ("UPSTREAM_ERROR", "An upstream service returned an error."),
        503: ("SERVICE_UNAVAILABLE", "The requested service is unavailable."),
        504: ("UPSTREAM_TIMEOUT", "An upstream service did not respond in time."),
    }
    code, message = status_codes.get(
        exc.status_code, ("HTTP_ERROR", "The request failed.")
    )
    detail = exc.detail
    details = detail if isinstance(detail, (dict, list)) else (
        {"reason": detail} if isinstance(detail, str) else None
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(code, message, details, getattr(request.state, "request_id", None)),
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            "INTERNAL_SERVER_ERROR",
            "An unexpected server error occurred. No internal exception details are exposed.",
            request_id=getattr(request.state, "request_id", None),
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
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


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
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc

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
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


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
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


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
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


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
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


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
                    "error": "CHAIN_FLOW_UNAVAILABLE", "error_type": type(exc).__name__,
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
                    "snapshot_block_number": chain_snapshot.get("snapshot_block_number", chain_snapshot.get("snapshot_block")),
                    "snapshot_block_timestamp": chain_snapshot.get("snapshot_block_timestamp"),
                    "snapshot_timestamp_status": chain_snapshot.get("snapshot_timestamp_status", "UNAVAILABLE"),
                    "snapshot_block_time": (
                        datetime.fromtimestamp(
                            chain_snapshot["snapshot_block_timestamp"], timezone.utc
                        ).isoformat()
                        if chain_snapshot.get("snapshot_block_timestamp") is not None else None
                    ),
                    "snapshot_age_seconds": (
                        max(0, int(datetime.now(timezone.utc).timestamp()) - chain_snapshot["snapshot_block_timestamp"])
                        if chain_snapshot.get("snapshot_block_timestamp") is not None else None
                    ),
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
                "balance_snapshot_block_number": concentration.get(
                    "snapshot_block_number", concentration.get("snapshot_block")
                ),
                "balance_snapshot_block_timestamp": concentration.get("snapshot_block_timestamp"),
                "balance_snapshot_timestamp_status": concentration.get(
                    "snapshot_timestamp_status", "UNAVAILABLE"
                ),
                "balance_snapshot_block_time": concentration.get("snapshot_block_time"),
                "balance_snapshot_age_seconds": concentration.get("snapshot_age_seconds"),
                "balance_snapshot_status": concentration_status,
                "balance_wallets_queried": concentration.get("queried_wallet_count", 0),
                "balance_wallets_succeeded": concentration.get("successful_wallet_count", 0),
                "balance_wallets_failed": sum(
                    1 for item in concentration_wallets if item.get("status") == "FAILED"
                ),
                "verified_registry_wallet_count": concentration.get("verified_wallet_count", 0),
                "component_status": {
                    "indexed_address_flows": flow.get("status", "UNAVAILABLE"),
                    "verified_smart_money": (
                        cohort.get("status", "UNAVAILABLE") if cohort is not None else "UNAVAILABLE"
                    ),
                    "verified_entity_flows": entity_flow_status,
                    "verified_wallet_concentration": concentration_status,
                },
                "incomplete_reasons": [
                    reason for condition, reason in [
                        (flow.get("status") != "COMPLETED", "Indexed address flows are not complete."),
                        (cohort is None or cohort.get("status") != "COMPLETED", "Verified smart-money flow data is unavailable or incomplete."),
                        (entity_flow_status != "COMPLETED", "Verified entity flow data is unavailable or incomplete."),
                        (concentration_status not in {"COMPLETED", "EMPTY"}, "Verified wallet balance snapshot is incomplete or unavailable."),
                        (not flow_coverage.get("complete", False), "Indexed address-flow coverage has gaps or is not confirmed complete."),
                        (not cohort_coverage.get("complete", False), "Smart-money indexed coverage has gaps or is not confirmed complete."),
                    ] if condition
                ],
                "chain_result_status": (
                    "COMPLETED"
                    if flow["status"] == "COMPLETED"
                    and cohort is not None and cohort["status"] == "COMPLETED"
                    and entity_flow_status == "COMPLETED"
                    and concentration_status in {"COMPLETED", "EMPTY"}
                    and flow_coverage.get("complete", False)
                    and cohort_coverage.get("complete", False)
                    else "INCOMPLETE"
                ),
                "freshness_note": (
                    "Snapshot age is calculated from the chain block timestamp and measured at API response time."
                    if concentration.get("snapshot_timestamp_status") == "AVAILABLE"
                    else "Block timestamp is unavailable from the RPC; snapshot age cannot be calculated."
                ),
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
                    and flow_coverage.get("complete", False)
                    and cohort_coverage.get("complete", False)
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
    overall_status = "COMPLETED" if chains and all(
        item["status"] == "COMPLETED" for item in chains
    ) else "INCOMPLETE"
    data_quality = {
        "status": overall_status,
        "coverage": {
            **quality_counts,
            "total_chains": len(chains),
            "requested_block_range": {"from": from_block, "to": to_block},
        },
        "freshness": {
            "balance_snapshots_with_timestamp": sum(
                1 for item in chains
                if item["data_quality"]["balance_snapshot_block"] is not None
                and item["data_quality"]["balance_snapshot_timestamp_status"] == "AVAILABLE"
            ),
            "balance_snapshots_without_timestamp": sum(
                1 for item in chains
                if item["data_quality"]["balance_snapshot_block"] is not None
                and item["data_quality"]["balance_snapshot_timestamp_status"] != "AVAILABLE"
            ),
            "chain_snapshots": [
                {
                    "chain_id": item["chain_id"],
                    "snapshot_block": item["data_quality"]["balance_snapshot_block"],
                    "snapshot_block_number": item["data_quality"]["balance_snapshot_block_number"],
                    "snapshot_block_timestamp": item["data_quality"]["balance_snapshot_block_timestamp"],
                    "timestamp_status": item["data_quality"]["balance_snapshot_timestamp_status"],
                    "snapshot_block_time": item["data_quality"]["balance_snapshot_block_time"],
                    "snapshot_age_seconds": item["data_quality"]["balance_snapshot_age_seconds"],
                }
                for item in chains
            ],
            "note": "Freshness is available only when the RPC returns a block timestamp; age is measured at API response time.",
        },
        "limitations": [
            "Indexed transfer flows reflect only locally indexed ranges; inspect per-chain coverage gaps.",
            "Token transfers do not prove trades, ownership, deposits, withdrawals, or investment intent.",
            "Wallet labels are operator-maintained; evidence fields are not independently authenticated by this service.",
            "Balance concentration includes only configured verified registry wallets, not all token holders.",
            "Block heights and token decimals are chain-specific and must not be compared across chains as if they shared one timeline.",
            "The asset_id is an operator-defined grouping key and does not prove economic equivalence between contracts.",
        ],
        "interpretation_notes": [
            "Treat INCOMPLETE results as partial evidence, not a complete market picture.",
            "Treat EMPTY concentration as no configured verified wallets, not zero ownership by the wider cohort.",
            "A missing block timestamp means freshness is unknown, not that the snapshot is stale.",
        ],
    }
    return {
        "data_quality": data_quality,
        "data_quality_summary": quality_counts,
        "status": overall_status,
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
            "snapshot_block": snapshot["snapshot_block"],
            "snapshot_block_number": snapshot["snapshot_block_number"],
            "snapshot_block_timestamp": snapshot["snapshot_block_timestamp"],
            "snapshot_timestamp_status": snapshot["snapshot_timestamp_status"],
            "snapshot_block_time": snapshot["snapshot_block_time"],
            "snapshot_age_seconds": snapshot["snapshot_age_seconds"],
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
            "token": snapshot["token"],
            "tracked_wallet_concentration": concentration,
            "tracked_balances": snapshot["tracked_balances"],
            "failed_balances": snapshot["failed_balances"],
            "tracked_addresses_combined_balance_tokens": snapshot["tracked_addresses_combined_balance_tokens"],
            "tracked_addresses_combined_share_of_total_supply_pct": snapshot["tracked_addresses_combined_share_of_total_supply_pct"],
            "registry_status": registry["status"],
            "warning": "Only verified operator-registry addresses are included. This is not a complete holder ranking or full token concentration analysis. All token metadata, supply, and tracked balances are read at the same pinned block; timestamp-derived freshness is unavailable if the RPC does not return block metadata.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


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
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


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
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


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
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


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
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "ONCHAIN_PROVIDER_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


@app.get("/api/v1/markets/spot/scan", tags=["markets"])
async def spot_market_scan(
    quote_asset: str | None = Query(default=None, min_length=2, max_length=12),
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


async def _preflight_probe(name: str, operation) -> dict:
    try:
        payload = await operation()
        symbols = payload.get("symbols", []) if isinstance(payload, dict) else []
        return {"name": name, "status": "AVAILABLE", "symbol_count": len(symbols)}
    except Exception as exc:
        return {"name": name, "status": "UNAVAILABLE", "error_type": type(exc).__name__}


@app.get("/api/v1/research/preflight", tags=["research"])
async def research_preflight() -> dict:
    """Probe live Binance public market endpoints and disclose configured research capabilities."""
    spot, usdm, coinm = await asyncio.gather(
        _preflight_probe("BINANCE_SPOT", get_spot_provider().exchange_info),
        _preflight_probe("BINANCE_USDM", get_futures_provider("USD_M").exchange_info),
        _preflight_probe("BINANCE_COINM", get_futures_provider("COIN_M").exchange_info),
    )
    feed_sources = parse_feed_sources(settings.news_rss_feeds)
    onchain_status = "PARTIAL" if settings.evm_rpc_url or settings.evm_chain_rpc_urls.strip() not in {"", "[]"} else "UNAVAILABLE"
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "market_data": {"spot": spot, "usdm": usdm, "coinm": coinm},
        "capabilities": {
            "binance_live_market_data": "AVAILABLE" if all(x["status"] == "AVAILABLE" for x in (spot, usdm, coinm)) else "PARTIAL" if any(x["status"] == "AVAILABLE" for x in (spot, usdm, coinm)) else "UNAVAILABLE",
            "news_sources": "CONFIGURED" if feed_sources else "UNAVAILABLE",
            "news_source_count": len(feed_sources),
            "live_web_search": "NOT_ASSESSABLE_BY_BACKEND",
            "code_execution": "AVAILABLE",
            "onchain_provider": onchain_status,
            "current_time": "PARTIAL_SERVER_CLOCK_NOT_NTP_VERIFIED",
        },
        "limitations": [
            "This endpoint probes exchangeInfo connectivity only; it does not prove full market scan coverage or order-book availability.",
            "Configured RSS feeds are not equivalent to complete global news search or independent claim verification.",
            "The backend cannot inspect the AI runtime's separate live web-search entitlement.",
            "On-chain provider configuration is not a successful chain RPC health check.",
            "Server time is reported in UTC; synchronization accuracy is not independently verified.",
        ],
        "trading_enabled": False,
        "api_credentials_required": False,
    }


@app.get("/api/v1/markets/futures/usdm/scan", tags=["markets"])
async def usdm_market_scan(
    quote_asset: str | None = Query(default=None, min_length=2, max_length=12),
    min_quote_volume: float = Query(default=0.0, ge=0.0),
    perpetual_only: bool = False,
) -> dict:
    result = await scan_futures_markets(
        get_futures_provider("USD_M"), quote_asset, min_quote_volume, perpetual_only
    )
    if result["status"] == "FAILED":
        raise HTTPException(status_code=502, detail=result)
    return result


@app.get("/api/v1/markets/futures/coinm/scan", tags=["markets"])
async def coinm_market_scan(
    quote_asset: str | None = Query(default=None, min_length=2, max_length=12),
    min_quote_volume: float = Query(default=0.0, ge=0.0),
    perpetual_only: bool = False,
) -> dict:
    result = await scan_futures_markets(
        get_futures_provider("COIN_M"), quote_asset, min_quote_volume, perpetual_only
    )
    if result["status"] == "FAILED":
        raise HTTPException(status_code=502, detail=result)
    return result


@app.get("/api/v1/markets/futures/scan-all", tags=["markets"])
async def all_futures_market_scan(
    min_quote_volume: float = Query(default=0.0, ge=0.0),
    perpetual_only: bool = False,
) -> dict:
    """Scan USDⓈ-M and COIN-M contract universes and report combined coverage."""
    usdm, coinm = await asyncio.gather(
        scan_futures_markets(
            get_futures_provider("USD_M"), quote_asset=None,
            min_quote_volume=min_quote_volume, perpetual_only=perpetual_only,
        ),
        scan_futures_markets(
            get_futures_provider("COIN_M"), quote_asset=None,
            min_quote_volume=min_quote_volume, perpetual_only=perpetual_only,
        ),
    )
    by_asset: dict[str, list[dict]] = {}
    for market_result in (usdm, coinm):
        for contract in market_result.get("results", []):
            base = str(contract.get("base_asset") or contract.get("symbol") or "UNKNOWN")
            by_asset.setdefault(base, []).append({
                "market": contract.get("market"),
                "symbol": contract.get("symbol"),
                "contract_type": contract.get("contract_type"),
                "margin_asset": contract.get("margin_asset"),
                "quote_asset": contract.get("quote_asset"),
                "quote_volume_24h": contract.get("quote_volume_24h"),
            })
    unique_coins = [
        {"base_asset": base, "contracts": contracts}
        for base, contracts in sorted(by_asset.items())
    ]
    statuses = (usdm.get("status"), coinm.get("status"))
    return {
        "status": "COMPLETED" if all(value == "COMPLETED" for value in statuses) else "INCOMPLETE",
        "phase_status": "INCOMPLETE",
        "phase_status_reason": "Full Stage 1 requires depth, recent-average volume surge, relative strength, market-cap and per-contract derivatives enrichment.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Binance USDⓈ-M and COIN-M public Futures REST APIs",
        "perpetual_only": perpetual_only,
        "total_available_contracts": (
            usdm.get("total_available_contracts", 0) + coinm.get("total_available_contracts", 0)
        ),
        "eligible_contracts": usdm.get("eligible_symbols", 0) + coinm.get("eligible_symbols", 0),
        "successfully_scanned_contracts": usdm.get("scanned_symbols", 0) + coinm.get("scanned_symbols", 0),
        "failed_contracts": usdm.get("failed_symbols", 0) + coinm.get("failed_symbols", 0),
        "unique_underlying_count": len(unique_coins),
        "unique_underlyings": unique_coins,
        "markets": {"USD_M": usdm, "COIN_M": coinm},
        "coverage_warning": (
            "Coverage is combined across both contract families. Contracts remain separately identified; "
            "this endpoint does not choose a primary contract because comparable order-book spread, depth, "
            "funding and execution suitability must be checked before selecting one."
        ),
    }


@app.get("/api/v1/markets/scan-all", tags=["markets"])
async def all_market_families_scan() -> dict:
    """Scan complete eligible Spot, USDⓈ-M and COIN-M symbol universes separately."""
    spot, futures = await asyncio.gather(
        scan_spot_markets(get_spot_provider(), quote_asset=None),
        all_futures_market_scan(min_quote_volume=0.0, perpetual_only=False),
    )
    grouped: dict[str, dict[str, Any]] = {}
    for row in spot.get("results", []):
        base = str(row.get("base_asset") or row.get("symbol") or "UNKNOWN")
        grouped.setdefault(base, {"base_asset": base, "spot_pairs": [], "futures_contracts": []})
        grouped[base]["spot_pairs"].append(row.get("symbol"))
    for row in futures.get("unique_underlyings", []):
        base = str(row.get("base_asset") or "UNKNOWN")
        grouped.setdefault(base, {"base_asset": base, "spot_pairs": [], "futures_contracts": []})
        grouped[base]["futures_contracts"].extend(row.get("contracts", []))
    raw_scan_complete = spot.get("status") == "COMPLETED" and futures.get("status") == "COMPLETED"
    return {
        "status": "COMPLETED" if raw_scan_complete else "INCOMPLETE",
        "phase_status": "INCOMPLETE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "markets": {"SPOT": spot, "FUTURES": futures},
        "coverage": {
            "spot_total_available_pairs": spot.get("total_available_pairs", 0),
            "spot_eligible_pairs": spot.get("eligible_symbols", 0),
            "spot_successfully_scanned_pairs": spot.get("scanned_symbols", 0),
            "spot_failed_pairs": spot.get("failed_symbols", 0),
            "futures_total_available_contracts": futures.get("total_available_contracts", 0),
            "futures_eligible_contracts": futures.get("eligible_contracts", 0),
            "futures_successfully_scanned_contracts": futures.get("successfully_scanned_contracts", 0),
            "futures_failed_contracts": futures.get("failed_contracts", 0),
            "unique_underlying_count": len(grouped),
        },
        "unique_underlyings": [grouped[key] for key in sorted(grouped)],
        "phase_status_reason": (
            "Raw symbol/ticker coverage is distinct from full Phase 01. Order-book depth, "
            "recent-average volume surge, market-cap enrichment and complete risk-tag coverage remain incomplete."
        ),
        "trading_enabled": False,
    }


@app.get("/api/v1/markets/futures/{market}/premium-index/{symbol}", tags=["markets"])
async def futures_premium_index(
    market: Literal["USD_M", "COIN_M"], symbol: str,
) -> dict:
    try:
        data = await get_futures_provider(market).premium_index(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "status": "FAILED", "error": "FUTURES_PREMIUM_INDEX_UNAVAILABLE",
            "market": market, "symbol": symbol.upper(),
        }) from exc
    return {
        "status": "COMPLETED", "market": market, "symbol": symbol.upper(),
        "source": f"Binance {market} public REST premiumIndex",
        "generated_at": datetime.now(timezone.utc).isoformat(), "data": data,
    }


@app.get("/api/v1/markets/futures/{market}/open-interest/{symbol}", tags=["markets"])
async def futures_open_interest(
    market: Literal["USD_M", "COIN_M"], symbol: str,
) -> dict:
    try:
        data = await get_futures_provider(market).open_interest(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "status": "FAILED", "error": "FUTURES_OPEN_INTEREST_UNAVAILABLE",
            "market": market, "symbol": symbol.upper(),
        }) from exc
    return {
        "status": "COMPLETED", "market": market, "symbol": symbol.upper(),
        "source": f"Binance {market} public REST openInterest",
        "generated_at": datetime.now(timezone.utc).isoformat(), "data": data,
    }


@app.get("/api/v1/markets/futures/{market}/open-interest-history/{symbol}", tags=["markets"])
async def futures_open_interest_history(
    market: Literal["USD_M", "COIN_M"], symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] = "1h",
    limit: int = Query(default=30, ge=1, le=500),
    pair: str | None = Query(default=None, min_length=2, max_length=30),
    contract_type: Literal["PERPETUAL", "CURRENT_QUARTER", "NEXT_QUARTER"] | None = None,
) -> dict:
    try:
        data = await get_futures_provider(market).open_interest_history(
            symbol, period=period, limit=limit, pair=pair, contract_type=contract_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "status": "FAILED", "error": "FUTURES_OPEN_INTEREST_HISTORY_UNAVAILABLE",
            "market": market, "symbol": symbol.upper(),
        }) from exc
    return {
        "status": "COMPLETED", "market": market, "symbol": symbol.upper(),
        "period": period, "returned_count": len(data),
        "source": f"Binance {market} public REST openInterestHist",
        "generated_at": datetime.now(timezone.utc).isoformat(), "data": data,
    }


@app.get("/api/v1/markets/futures/{market}/funding-info", tags=["markets"])
async def futures_funding_info(market: Literal["USD_M", "COIN_M"]) -> dict:
    try:
        data = await get_futures_provider(market).funding_info()
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "status": "FAILED", "error": "FUTURES_FUNDING_INFO_UNAVAILABLE",
            "market": market,
        }) from exc
    return {
        "status": "COMPLETED", "market": market,
        "source": f"Binance {market} public REST fundingInfo",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "returned_count": len(data), "symbols_with_funding_adjustments": data,
        "note": "This endpoint reports symbols with funding parameter adjustments; absence from the response does not by itself prove a non-standard interval.",
    }


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


@app.get("/api/v1/history/order-book/status", tags=["history"])
async def order_book_stream_status() -> dict:
    if not settings.order_book_collector_enabled:
        return {
            "status": "DISABLED", "enabled": False,
            "stored_sample_count": order_book_history_store.count(),
            "message": "Set ORDER_BOOK_COLLECTOR_ENABLED=true and configure ORDER_BOOK_COLLECTOR_JOBS on a persistent single-process deployment.",
        }
    if order_book_collector is None:
        return {"status": "STARTING", "enabled": True}
    return {"status": "RUNNING", **order_book_collector.status()}


@app.get("/api/v1/history/order-book/{market}/{symbol}", tags=["history"])
async def stored_order_book_history(
    market: Literal["SPOT", "USD_M", "COIN_M"], symbol: str,
    limit: int = Query(default=100, ge=1, le=1000),
    start_time_ms: int | None = Query(default=None, ge=0),
    end_time_ms: int | None = Query(default=None, ge=0),
) -> dict:
    if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
        raise HTTPException(status_code=422, detail="end_time_ms must be >= start_time_ms")
    rows = await asyncio.to_thread(
        order_book_history_store.recent, market, symbol, limit, start_time_ms, end_time_ms
    )
    return {
        "status": "COMPLETED", "market": market, "symbol": symbol.upper(),
        "returned_count": len(rows), "samples": rows,
        "coverage_warning": "Only locally captured, sequence-synchronized samples are returned. No historical backfill is available.",
    }


@app.get("/api/v1/history/aggregate-trades/status", tags=["history"])
async def aggregate_trade_collector_status() -> dict:
    if not settings.aggregate_trade_collector_enabled:
        return {
            "status": "DISABLED", "enabled": False,
            "stored_trade_count": aggregate_trade_store.count(),
            "message": "Set AGGREGATE_TRADE_COLLECTOR_ENABLED=true and configure AGG_TRADE_COLLECTOR_JOBS.",
        }
    if aggregate_trade_collector is None:
        return {"status": "STARTING", "enabled": True}
    return {"status": "RUNNING", **aggregate_trade_collector.status()}


@app.get("/api/v1/history/aggregate-trades/{market}/{symbol}", tags=["history"])
async def stored_aggregate_trades(
    market: Literal["SPOT", "USD_M", "COIN_M"], symbol: str,
    limit: int = Query(default=1000, ge=1, le=10000),
    start_time_ms: int | None = Query(default=None, ge=0),
    end_time_ms: int | None = Query(default=None, ge=0),
) -> dict:
    if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
        raise HTTPException(status_code=422, detail="end_time_ms must be >= start_time_ms")
    rows = await asyncio.to_thread(
        aggregate_trade_store.recent, market, symbol, limit, start_time_ms, end_time_ms
    )
    return {
        "status": "COMPLETED", "market": market, "symbol": symbol.upper(),
        "returned_count": len(rows), "trades": rows,
        "coverage_warning": "Only locally captured aggregate trades are returned; no historical backfill is performed.",
    }


@app.get("/api/v1/analysis/liquidity-behavior/{market}/{symbol}", tags=["analysis"])
async def liquidity_behavior_analysis(
    market: Literal["SPOT", "USD_M", "COIN_M"], symbol: str,
    min_removed_notional: float = Query(default=10000, ge=0, le=1e15),
    min_aggressive_notional: float = Query(default=10000, ge=0, le=1e15),
    max_absorption_move_bps: float = Query(default=2.0, ge=0, le=1000),
    trade_price_band_bps: float = Query(default=2.0, ge=0, le=1000),
) -> dict:
    snapshots = await asyncio.to_thread(order_book_history_store.recent, market, symbol, 2)
    if len(snapshots) < 2:
        return {
            "status": "INSUFFICIENT_DATA", "market": market, "symbol": symbol.upper(),
            "reason": "At least two stored order-book samples are required.",
            "order_book_collector_enabled": settings.order_book_collector_enabled,
        }
    snapshots = list(reversed(snapshots))
    start_ms = int(snapshots[0].get("event_time_ms") or 0)
    end_ms = int(snapshots[-1].get("event_time_ms") or 0)
    trades = await asyncio.to_thread(
        aggregate_trade_store.recent, market, symbol, 10000, start_ms, end_ms
    )
    result = await asyncio.to_thread(
        analyze_liquidity_behavior, snapshots, trades, market, symbol,
        min_removed_notional, min_aggressive_notional,
        max_absorption_move_bps, trade_price_band_bps,
    )
    result["collector_coverage"] = {
        "order_book_collector_enabled": settings.order_book_collector_enabled,
        "aggregate_trade_collector_enabled": settings.aggregate_trade_collector_enabled,
        "aggregate_trade_samples_available": len(trades),
    }
    return result


@app.get("/api/v1/analysis/market-structure-confluence/{market}/{symbol}", tags=["analysis"])
async def market_structure_confluence(
    market: Literal["SPOT", "USD_M", "COIN_M"], symbol: str,
    interval: str = "1h",
    limit: int = Query(default=300, ge=40, le=1000),
    periods: str = "15m,1h,4h,1d",
    bin_size_bps: float = Query(default=5.0, ge=0.1, le=500),
    value_area_pct: float = Query(default=70.0, ge=50, le=99),
) -> dict:
    allowed_intervals = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}
    if interval not in allowed_intervals:
        raise HTTPException(status_code=422, detail="Unsupported candle interval")
    selected_periods = [item.strip() for item in periods.split(",") if item.strip()]
    allowed_periods = {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}
    if not selected_periods or len(selected_periods) > 9 or len(set(selected_periods)) != len(selected_periods):
        raise HTTPException(status_code=422, detail="Select 1 to 9 unique timeframes")
    if any(item not in allowed_periods for item in selected_periods):
        raise HTTPException(status_code=422, detail="Unsupported order-flow timeframe")
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    longest_minutes = max(
        {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120,
         "4h": 240, "6h": 360, "12h": 720, "1d": 1440}[item]
        for item in selected_periods
    )
    try:
        history, trades = await asyncio.gather(
            asyncio.to_thread(historical_kline_store.history, market, symbol, interval, None, None, limit),
            asyncio.to_thread(
                aggregate_trade_store.recent, market, symbol, 50000,
                end_ms - max(longest_minutes, 1440) * 60_000, end_ms,
            ),
        )
        candles = history["candles"]
        if len(candles) < 40:
            return {
                "status": "INSUFFICIENT_DATA", "market": market, "symbol": symbol.upper(),
                "interval": interval, "available_candles": len(candles),
                "required_candles": 40, "confluence": {
                    "bias": "UNKNOWN", "alignment": "INSUFFICIENT_DIRECTIONAL_EVIDENCE",
                },
                "historical_coverage": history.get("coverage"),
            }
        structure, regime = await asyncio.gather(
            asyncio.to_thread(SmartMoneyMarketStructure(historical_kline_store).analyze,
                              market, symbol, interval, limit, 3, 3),
            asyncio.to_thread(MarketRegimeAnalysis(historical_kline_store).analyze,
                              market, symbol, interval, max(40, min(limit, 200))),
        )
        flow_end = end_ms
        flow_start = flow_end - 60 * 60_000
        order_flow = await asyncio.to_thread(
            analyze_order_flow, trades, market, symbol, flow_start, flow_end,
            bin_size_bps, value_area_pct,
        )
        multi_flow = await asyncio.to_thread(
            analyze_multi_timeframe_order_flow, trades, market, symbol,
            end_ms, selected_periods, bin_size_bps, value_area_pct,
        )
        book_samples = await asyncio.to_thread(
            order_book_history_store.recent, market, symbol, 2000,
            int(candles[0]["open_time_ms"]), int(candles[-1]["close_time_ms"]),
        )
        sweep = await asyncio.to_thread(
            analyze_liquidity_sweep_confirmation,
            candles, trades, book_samples, market, symbol, [], [],
        )
        result = await asyncio.to_thread(
            analyze_market_structure_confluence,
            market, symbol, interval, structure, regime, order_flow, multi_flow, sweep,
        )
        result["analyzed_at_ms"] = end_ms
        closed_reference = next((c for c in reversed(candles) if int(c["close_time_ms"]) <= end_ms), None)
        result["reference"] = {"price": float(closed_reference["close"]) if closed_reference else None,
                               "close_time_ms": int(closed_reference["close_time_ms"]) if closed_reference else None,
                               "basis": "last locally stored candle fully closed at or before analyzed_at_ms"}
        result["coverage"] = {
            "historical_candle_count": len(candles),
            "aggregate_trade_count": len(trades),
            "aggregate_trade_query_limit": 50000,
            "aggregate_trade_limit_reached": len(trades) >= 50000,
            "order_book_sample_count": len(book_samples),
            "local_history_only": True,
            "backfill_performed": False,
            "historical_kline_coverage": history.get("coverage"),
        }
        result["configuration"] = {
            "order_flow_window_minutes": 60,
            "multi_timeframe_periods": selected_periods,
            "volume_profile_bin_size_bps": bin_size_bps,
            "value_area_pct": value_area_pct,
        }
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc



@app.post("/api/v1/history/market-confluence/snapshots", tags=["history"])
async def save_market_confluence_snapshot(payload: dict = Body(...)) -> dict:
    try:
        return await asyncio.to_thread(market_confluence_store.save, payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/history/market-confluence/{market}/{symbol}", tags=["history"])
async def get_market_confluence_history(
    market: Literal["SPOT", "USD_M", "COIN_M"], symbol: str,
    interval: str = "1h", limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    try:
        return await asyncio.to_thread(market_confluence_store.history, market, symbol, interval, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/analysis/market-confluence-performance/{market}/{symbol}", tags=["analysis"])
async def evaluate_market_confluence_performance(
    market: Literal["SPOT", "USD_M", "COIN_M"], symbol: str,
    interval: str = "1h", price_interval: str = "1h",
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    try:
        return await asyncio.to_thread(market_confluence_performance.evaluate, market, symbol, interval, price_interval, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

 
@app.get("/api/v1/history/market-confluence/{market}/{symbol}/{snapshot_id}/price-path", tags=["history"])
async def get_market_confluence_price_path(
    market: Literal["SPOT", "USD_M", "COIN_M"], symbol: str, snapshot_id: str,
    price_interval: str = "1h",
    hours: int = Query(default=720, ge=1, le=720),
) -> dict:
    try:
        return await asyncio.to_thread(
            market_confluence_performance.price_path,
            market, symbol, snapshot_id, price_interval, hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 422, detail=str(exc)) from exc


@app.get("/dashboard", include_in_schema=False)
async def market_research_dashboard():
    return FileResponse(Path(__file__).resolve().parents[2] / "dashboard" / "index.html", media_type="text/html")


@app.get("/api/v1/analysis/liquidity-sweep-confirmation/{market}/{symbol}", tags=["analysis"])
async def liquidity_sweep_confirmation(
    market: Literal["SPOT", "USD_M", "COIN_M"], symbol: str,
    interval: str = "5m",
    limit: int = Query(default=300, ge=30, le=1000),
    equal_level_tolerance_bps: float = Query(default=8.0, ge=0.1, le=100),
) -> dict:
    allowed_intervals = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}
    if interval not in allowed_intervals:
        raise HTTPException(status_code=422, detail="Unsupported candle interval")
    try:
        history = await asyncio.to_thread(
            historical_kline_store.history, market, symbol, interval, None, None, limit
        )
        candles = history["candles"]
        if not candles:
            return {
                "status": "INSUFFICIENT_CANDLE_DATA", "market": market,
                "symbol": symbol.upper(), "available_candles": 0,
                "sweep_candidates": [], "confirmation_status": "INSUFFICIENT_DATA",
                "historical_coverage": history.get("coverage"),
            }
        start_ms = int(candles[0]["open_time_ms"])
        end_ms = int(candles[-1]["close_time_ms"])
        trades, books = await asyncio.gather(
            asyncio.to_thread(aggregate_trade_store.recent, market, symbol, 10000, start_ms, end_ms),
            asyncio.to_thread(order_book_history_store.recent, market, symbol, 2000, start_ms, end_ms),
        )
        oi_records, funding_events = [], []
        if market == "USD_M":
            # Include a one-hour look-behind so nearest observations just before
            # the candle window can still qualify under the engine's explicit lag.
            derivatives_start_ms = max(0, start_ms - 60 * 60_000)
            oi_history, funding_history = await asyncio.gather(
                asyncio.to_thread(open_interest_store.history, "USD_M", symbol, "1h", derivatives_start_ms, end_ms, 500),
                asyncio.to_thread(funding_rate_store.history, "USD_M", symbol, derivatives_start_ms, end_ms, 100),
            )
            oi_records = oi_history["records"]
            funding_events = funding_history["events"]
        result = await asyncio.to_thread(
            analyze_liquidity_sweep_confirmation,
            candles, trades, books, market, symbol, oi_records, funding_events,
            2, 2, equal_level_tolerance_bps,
        )
        result["historical_coverage"] = history.get("coverage")
        result["collector_coverage"] = {
            "aggregate_trade_collector_enabled": settings.aggregate_trade_collector_enabled,
            "order_book_collector_enabled": settings.order_book_collector_enabled,
            "aggregate_trade_rows_returned": len(trades),
            "order_book_samples_returned": len(books),
            "query_limits": {"aggregate_trades": 10000, "order_book_samples": 2000},
            "derivatives_history_available": market == "USD_M",
            "local_history_only": True,
            "backfill_performed": False,
        }
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/analysis/order-flow/multi-timeframe/{market}/{symbol}", tags=["analysis"])
async def multi_timeframe_order_flow(
    market: Literal["SPOT", "USD_M", "COIN_M"], symbol: str,
    periods: str = "5m,15m,1h,4h,1d",
    bin_size_bps: float = Query(default=5.0, ge=0.1, le=500),
    value_area_pct: float = Query(default=70.0, ge=50, le=99),
) -> dict:
    selected_periods = [item.strip() for item in periods.split(",") if item.strip()]
    if not selected_periods or len(selected_periods) > 9:
        raise HTTPException(status_code=422, detail="Select between 1 and 9 timeframes")
    if len(set(selected_periods)) != len(selected_periods):
        raise HTTPException(status_code=422, detail="Timeframes must be unique")
    allowed_periods = {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}
    if any(item not in allowed_periods for item in selected_periods):
        raise HTTPException(status_code=422, detail="Unsupported timeframe")
    end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    longest_minutes = max(
        {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120,
         "4h": 240, "6h": 360, "12h": 720, "1d": 1440}.get(item, 1441)
        for item in selected_periods
    )
    if longest_minutes > 1440:
        raise HTTPException(status_code=422, detail="Unsupported timeframe")
    start_time_ms = end_time_ms - longest_minutes * 60 * 1000
    trades = await asyncio.to_thread(
        aggregate_trade_store.recent, market, symbol, 50000,
        start_time_ms, end_time_ms,
    )
    result = await asyncio.to_thread(
        analyze_multi_timeframe_order_flow, trades, market, symbol,
        end_time_ms, selected_periods, bin_size_bps, value_area_pct,
    )
    result["collector_coverage"] = {
        "aggregate_trade_collector_enabled": settings.aggregate_trade_collector_enabled,
        "collector_state": (
            "RUNNING" if aggregate_trade_collector is not None
            else "DISABLED" if not settings.aggregate_trade_collector_enabled
            else "STARTING"
        ),
        "stored_trade_count_in_query": len(trades),
        "query_limit": 50000,
        "limit_reached": len(trades) >= 50000,
        "history_is_local_only": True,
        "backfill_available": False,
    }
    return result


@app.get("/api/v1/analysis/order-flow/{market}/{symbol}", tags=["analysis"])
async def order_flow_intelligence(
    market: Literal["SPOT", "USD_M", "COIN_M"], symbol: str,
    lookback_minutes: int = Query(default=60, ge=1, le=1440),
    bin_size_bps: float = Query(default=5.0, ge=0.1, le=500),
    value_area_pct: float = Query(default=70.0, ge=50, le=99),
) -> dict:
    end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time_ms = end_time_ms - lookback_minutes * 60 * 1000
    trades = await asyncio.to_thread(
        aggregate_trade_store.recent, market, symbol, 50000,
        start_time_ms, end_time_ms,
    )
    result = await asyncio.to_thread(
        analyze_order_flow, trades, market, symbol,
        start_time_ms, end_time_ms, bin_size_bps, value_area_pct,
    )
    result["collector_coverage"] = {
        "aggregate_trade_collector_enabled": settings.aggregate_trade_collector_enabled,
        "collector_state": (
            "RUNNING" if aggregate_trade_collector is not None
            else "DISABLED" if not settings.aggregate_trade_collector_enabled
            else "STARTING"
        ),
        "stored_trade_count_in_requested_window": len(trades),
        "query_limit": 50000,
        "limit_reached": len(trades) >= 50000,
        "history_is_local_only": True,
        "backfill_available": False,
    }
    return result


@app.get("/api/v1/analysis/order-book/{market}/{symbol}", tags=["analysis"])
async def order_book_liquidity_intelligence(
    market: Literal["SPOT", "USD_M", "COIN_M"],
    symbol: str,
    limit: int = Query(default=100, ge=1, le=1000),
    wall_multiplier: float = Query(default=3.0, ge=1, le=20),
) -> dict:
    try:
        if market == "SPOT":
            if limit not in {1, 5, 10, 20, 50, 100, 500, 1000}:
                raise ValueError("Unsupported Spot order book limit")
            provider = get_spot_provider()
        else:
            if limit not in {5, 10, 20, 50, 100, 500, 1000}:
                raise ValueError("Unsupported futures order book limit")
            provider = get_futures_provider(market)
        book = await provider.order_book(symbol, limit)
        return await asyncio.to_thread(
            analyze_order_book, book, market, symbol, limit, wall_multiplier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "status": "FAILED", "error": "ORDER_BOOK_UNAVAILABLE",
            "error_type": type(exc).__name__,
        }) from exc


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
        raise HTTPException(status_code=502, detail={
            "status": "FAILED",
            "error": "DERIVATIVES_ANALYSIS_UNAVAILABLE",
            "error_type": type(exc).__name__,
        }) from exc


@app.get("/api/v1/analysis/spot-futures/basis/{symbol}", tags=["analysis"])
async def spot_futures_basis_intelligence(symbol: str) -> dict:
    try:
        return await analyze_spot_futures_basis(
            get_spot_provider(), get_futures_provider("USD_M"), symbol
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "status": "FAILED",
            "error": "SPOT_FUTURES_ANALYSIS_UNAVAILABLE",
            "error_type": type(exc).__name__,
        }) from exc


@app.get("/api/v1/analysis/market-evidence/{symbol}", tags=["analysis"])
async def market_evidence_snapshot(symbol: str) -> dict:
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status_code=422, detail="symbol must not be empty")

    spot = get_spot_provider()
    futures = get_futures_provider("USD_M")

    async def capture(awaitable):
        try:
            return await awaitable
        except Exception as exc:
            return {"status": "FAILED", "error": "UPSTREAM_UNAVAILABLE",
                    "error_type": type(exc).__name__}

    async def volume_snapshot():
        rows = await spot.klines(normalized, "1h", 300)
        vwap = calculate_vwap(rows)
        profile = calculate_volume_profile(rows)
        structure = analyze_market_structure(rows)
        sections = (vwap["status"], profile["status"], structure["status"])
        return {
            "status": "COMPLETED" if all(value == "COMPLETED" for value in sections) else "INCOMPLETE",
            "source": "Binance Spot public REST klines",
            "symbol": normalized,
            "interval": "1h",
            "candle_count": len(rows),
            "vwap": vwap,
            "volume_profile": profile,
            "market_structure": structure,
            "warning": "OHLCV-based approximations only; not trade-level volume-at-price.",
        }

    base_asset = normalized
    for quote in ("USDT", "USDC", "BUSD", "FDUSD", "BTC", "ETH", "BNB"):
        if normalized.endswith(quote) and len(normalized) > len(quote):
            base_asset = normalized[:-len(quote)]
            break

    multi_task = capture(analyze_multiple_timeframes(spot, normalized))
    basis_task = capture(analyze_spot_futures_basis(spot, futures, normalized))
    derivatives_task = capture(get_derivatives_intelligence(futures, normalized))
    volume_task = capture(volume_snapshot())
    news_task = capture(news_catalysts(symbols=base_asset, hours=72, limit=50))

    multi, basis, derivatives, volume, catalysts = await asyncio.gather(
        multi_task, basis_task, derivatives_task, volume_task, news_task
    )
    return build_market_evidence_snapshot(
        normalized, multi, basis, derivatives, volume, catalysts
    )


@app.post("/api/v1/analysis/signal-lifecycle", tags=["analysis"])
async def signal_lifecycle(payload: dict[str, Any] = Body(...)) -> dict:
    try:
        return build_signal_lifecycle(**payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/analysis/trade-risk-plan", tags=["analysis"])
async def trade_risk_plan(payload: dict[str, Any] = Body(...)) -> dict:
    try:
        result = build_trade_risk_plan(**payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        **result,
        "analysis_only": True,
        "trading_enabled": False,
        "warning": "User-supplied scenario arithmetic only. This endpoint does not generate or validate a live trading signal.",
    }


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
    required_indicator_paths = {
        "ema_20": indicators.get("ema_20"),
        "ema_50": indicators.get("ema_50"),
        "ema_100": indicators.get("ema_100"),
        "ema_200": indicators.get("ema_200"),
        "rsi_14_wilder": indicators.get("rsi_14_wilder"),
        "macd_12_26": indicators.get("macd_12_26"),
        "macd_signal_9": indicators.get("macd_signal_9"),
        "bollinger_20_2": indicators.get("bollinger_20_2", {}).get("middle"),
    }
    missing_indicators = [name for name, value in required_indicator_paths.items() if value is None]
    return {
        "status": "COMPLETED" if not missing_indicators else "INCOMPLETE",
        "missing_indicators": missing_indicators,
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


@app.get("/api/v1/history/collector/status", tags=["history"])
async def historical_collector_status() -> dict:
    if not settings.historical_collector_enabled:
        return {
            "status": "DISABLED",
            "enabled": False,
            "message": "Set HISTORICAL_COLLECTOR_ENABLED=true and configure HISTORICAL_COLLECTOR_JOBS to enable scheduled collection.",
        }
    if historical_collector is None:
        return {"status": "STARTING", "enabled": True}
    return historical_collector.status()


@app.post("/api/v1/history/funding-rates/USD_M/{symbol}/collect", tags=["history"])
async def collect_historical_funding_rates(
    symbol: str,
    start_time_ms: int | None = Query(default=None, ge=0),
    end_time_ms: int | None = Query(default=None, ge=0),
    limit: int = Query(default=1000, ge=1, le=1000),
) -> dict:
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status_code=422, detail="symbol must not be empty")
    if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
        raise HTTPException(status_code=422, detail="end_time_ms must be >= start_time_ms")
    try:
        rows = await get_futures_provider("USD_M").funding_rate(
            normalized, limit=limit, start_time_ms=start_time_ms, end_time_ms=end_time_ms
        )
        if not rows:
            return {
                "status": "NO_NEW_DATA", "market": "USD_M", "symbol": normalized,
                "received_count": 0, "warning": "The exchange returned no funding events; no history was stored.",
            }
        return await asyncio.to_thread(
            funding_rate_store.save, "USD_M", normalized, rows
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "status": "FAILED", "error": "FUNDING_RATE_COLLECTION_UNAVAILABLE",
            "error_type": type(exc).__name__,
        }) from exc


@app.get("/api/v1/history/funding-rates/USD_M/{symbol}", tags=["history"])
async def get_historical_funding_rates(
    symbol: str,
    start_time_ms: int | None = Query(default=None, ge=0),
    end_time_ms: int | None = Query(default=None, ge=0),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict:
    try:
        return await asyncio.to_thread(
            funding_rate_store.history, "USD_M", symbol, start_time_ms, end_time_ms, limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/history/derivatives-collector/status", tags=["history"])
async def get_derivatives_collector_status() -> dict:
    if not settings.derivatives_collector_enabled:
        return {"status": "DISABLED", "enabled": False, "jobs": []}
    if derivatives_collector is None:
        return {"status": "STARTING", "enabled": True, "jobs": []}
    return derivatives_collector.status()


@app.post("/api/v1/history/open-interest/USD_M/{symbol}/collect", tags=["history"])
async def collect_historical_open_interest(
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] = "1h",
    start_time_ms: int | None = Query(default=None, ge=0),
    end_time_ms: int | None = Query(default=None, ge=0),
    limit: int = Query(default=500, ge=1, le=500),
) -> dict:
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status_code=422, detail="symbol must not be empty")
    if start_time_ms is not None and end_time_ms is not None and end_time_ms < start_time_ms:
        raise HTTPException(status_code=422, detail="end_time_ms must be >= start_time_ms")
    try:
        rows = await get_futures_provider("USD_M").open_interest_history(
            normalized, period=period, limit=limit,
            start_time_ms=start_time_ms, end_time_ms=end_time_ms,
        )
        if not rows:
            return {
                "status": "NO_NEW_DATA", "market": "USD_M", "symbol": normalized,
                "period": period, "received_count": 0,
                "warning": "The exchange returned no open-interest records; no history was stored.",
            }
        return await asyncio.to_thread(
            open_interest_store.save, "USD_M", normalized, period, rows
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "status": "FAILED", "error": "OPEN_INTEREST_COLLECTION_UNAVAILABLE",
            "error_type": type(exc).__name__,
        }) from exc


@app.get("/api/v1/analysis/derivatives/combined/{symbol}", tags=["analysis"])
async def analyze_combined_derivatives_intelligence(
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] = "1h",
    limit: int = Query(default=100, ge=2, le=500),
) -> dict:
    try:
        engine = CombinedDerivativesIntelligence(
            open_interest_store, funding_rate_store, derivatives_ratio_store
        )
        return await asyncio.to_thread(engine.analyze, symbol, period, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/history/derivatives-ratios/USD_M/{ratio_type}/{symbol}/collect", tags=["history"])
async def collect_derivatives_ratio_history(
    ratio_type: Literal["GLOBAL_LONG_SHORT", "TAKER_BUY_SELL"],
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] = "1h",
    limit: int = Query(default=500, ge=1, le=500),
) -> dict:
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status_code=422, detail="symbol must not be empty")
    try:
        provider = get_futures_provider("USD_M")
        if ratio_type == "GLOBAL_LONG_SHORT":
            rows = await provider.global_long_short_ratio(normalized, period, limit)
        else:
            rows = await provider.taker_long_short_ratio(normalized, period, limit)
        if not rows:
            return {
                "status": "NO_NEW_DATA", "market": "USD_M", "ratio_type": ratio_type,
                "symbol": normalized, "period": period, "received_count": 0,
            }
        return await asyncio.to_thread(
            derivatives_ratio_store.save, ratio_type, normalized, period, rows
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "status": "FAILED", "error": "DERIVATIVES_RATIO_COLLECTION_UNAVAILABLE",
            "error_type": type(exc).__name__,
        }) from exc


@app.get("/api/v1/history/derivatives-ratios/USD_M/{ratio_type}/{symbol}", tags=["history"])
async def get_derivatives_ratio_history(
    ratio_type: Literal["GLOBAL_LONG_SHORT", "TAKER_BUY_SELL"],
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] = "1h",
    start_time_ms: int | None = Query(default=None, ge=0),
    end_time_ms: int | None = Query(default=None, ge=0),
    limit: int = Query(default=500, ge=1, le=500),
) -> dict:
    try:
        return await asyncio.to_thread(
            derivatives_ratio_store.history, ratio_type, symbol, period,
            start_time_ms, end_time_ms, limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/analysis/derivatives/funding-open-interest/{symbol}", tags=["analysis"])
async def analyze_funding_open_interest(
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] = "1h",
    price_interval: str = "1h",
    limit: int = Query(default=24, ge=2, le=500),
) -> dict:
    try:
        engine = FundingOpenInterestAnalysis(
            funding_rate_store, open_interest_store, historical_kline_store
        )
        return await asyncio.to_thread(
            engine.analyze, symbol, period, price_interval, limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/analysis/derivatives/multi-timeframe/{symbol}", tags=["analysis"])
async def analyze_multi_timeframe_derivatives(
    symbol: str,
    periods: str = "5m,15m,1h,4h,1d",
    limit: int = Query(default=48, ge=6, le=500),
) -> dict:
    try:
        requested = [part.strip() for part in periods.split(",")]
        engine = AdvancedDerivativesAnalysis(
            funding_rate_store, open_interest_store, historical_kline_store,
            liquidation_store, derivatives_signal_store,
        )
        multi = MultiTimeframeDerivativesAnalysis(engine)
        return await asyncio.to_thread(multi.analyze, symbol, requested, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/analysis/derivatives/advanced/{symbol}", tags=["analysis"])
async def analyze_advanced_derivatives(
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] = "1h",
    price_interval: Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"] = "1h",
    limit: int = Query(default=48, ge=6, le=500),
    funding_abs_threshold: float = Query(default=0.001, ge=0, le=0.1),
    spike_mad_multiplier: float = Query(default=3.5, ge=1, le=10),
) -> dict:
    try:
        engine = AdvancedDerivativesAnalysis(
            funding_rate_store, open_interest_store, historical_kline_store,
            liquidation_store, derivatives_signal_store,
        )
        return await asyncio.to_thread(
            engine.analyze, symbol, period, price_interval, limit,
            funding_abs_threshold, spike_mad_multiplier,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/history/derivatives-signals/{symbol}", tags=["history"])
async def get_derivatives_signal_history(
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] = "1h",
    start_time_ms: int | None = Query(default=None, ge=0),
    end_time_ms: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    try:
        return await asyncio.to_thread(
            derivatives_signal_store.history, symbol, period,
            start_time_ms, end_time_ms, limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/analysis/derivatives/signal-performance/{symbol}", tags=["analysis"])
async def evaluate_historical_signal_performance(
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] = "1h",
    price_interval: Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"] = "1h",
    limit: int = Query(default=500, ge=1, le=1000),
    round_trip_cost_bps: float = Query(default=0.0, ge=0, le=500),
) -> dict:
    try:
        engine = HistoricalSignalPerformance(derivatives_signal_store, historical_kline_store)
        return await asyncio.to_thread(
            engine.evaluate, symbol, period, price_interval, limit, round_trip_cost_bps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/history/open-interest/USD_M/{symbol}", tags=["history"])
async def get_historical_open_interest(
    symbol: str,
    period: Literal["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"] = "1h",
    start_time_ms: int | None = Query(default=None, ge=0),
    end_time_ms: int | None = Query(default=None, ge=0),
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict:
    try:
        return await asyncio.to_thread(
            open_interest_store.history, "USD_M", symbol, period,
            start_time_ms, end_time_ms, limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/history/klines/{market}/{symbol}/collect", tags=["history"])
async def collect_historical_klines(
    market: Literal["SPOT", "USD_M", "COIN_M"],
    symbol: str,
    interval: Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"] = "1h",
    limit: int = Query(default=500, ge=1, le=1500),
) -> dict:
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(status_code=422, detail="symbol must not be empty")
    try:
        provider = get_spot_provider() if market == "SPOT" else get_futures_provider(market)
        rows = await provider.klines(normalized, interval, limit)
        if not rows:
            return {"status": "INCOMPLETE", "market": market, "symbol": normalized, "interval": interval, "received_count": 0, "warning": "The exchange returned no candles; no history was stored."}
        return await asyncio.to_thread(historical_kline_store.save_klines, market, normalized, interval, rows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"status": "FAILED", "error": "HISTORICAL_KLINE_COLLECTION_UNAVAILABLE", "error_type": type(exc).__name__}) from exc


@app.get("/api/v1/quality/market-data/{market}/{symbol}", tags=["quality"])
async def inspect_market_data_quality(
    market: Literal["SPOT", "USD_M", "COIN_M"],
    symbol: str,
    interval: Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"] = "1h",
    lookback_hours: int = Query(default=168, ge=1, le=2160),
) -> dict:
    engine = MarketDataQualityEngine(
        settings.historical_kline_database_path,
        settings.funding_rate_database_path,
        settings.open_interest_database_path,
        settings.derivatives_ratio_database_path,
        settings.aggregate_trade_database_path,
        settings.order_book_database_path,
    )
    try:
        report = await asyncio.to_thread(
            engine.inspect, market, symbol, interval, lookback_hours
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    report["collectors"] = {
        "historical_klines": (
            historical_collector.status() if historical_collector is not None else
            {"status": "DISABLED", "enabled": False} if not settings.historical_collector_enabled else
            {"status": "STARTING", "enabled": True}
        ),
        "derivatives": (
            derivatives_collector.status() if derivatives_collector is not None else
            {"status": "DISABLED", "enabled": False} if not settings.derivatives_collector_enabled else
            {"status": "STARTING", "enabled": True}
        ),
        "aggregate_trades": (
            aggregate_trade_collector.status() if aggregate_trade_collector is not None else
            {"status": "DISABLED", "enabled": False} if not settings.aggregate_trade_collector_enabled else
            {"status": "STARTING", "enabled": True}
        ),
        "order_book": (
            order_book_collector.status() if order_book_collector is not None else
            {"status": "DISABLED", "enabled": False} if not settings.order_book_collector_enabled else
            {"status": "STARTING", "enabled": True}
        ),
    }
    return report


@app.get("/api/v1/history/klines/{market}/{symbol}/coverage", tags=["history"])
async def inspect_historical_kline_coverage(
    market: Literal["SPOT", "USD_M", "COIN_M"],
    symbol: str,
    interval: Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"] = "1h",
    start_time_ms: int = Query(..., ge=0),
    end_time_ms: int = Query(..., ge=0),
) -> dict:
    engine = HistoricalCoverageEngine(settings.historical_kline_database_path)
    try:
        return await asyncio.to_thread(
            engine.inspect, market, symbol, interval, start_time_ms, end_time_ms
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/history/klines/{market}/{symbol}", tags=["history"])
async def get_historical_klines(
    market: Literal["SPOT", "USD_M", "COIN_M"],
    symbol: str,
    interval: Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"] = "1h",
    start_time_ms: int | None = Query(default=None, ge=0),
    end_time_ms: int | None = Query(default=None, ge=0),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict:
    try:
        return await asyncio.to_thread(historical_kline_store.history, market, symbol, interval, start_time_ms, end_time_ms, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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


@app.get("/api/v1/analysis/smart-money-structure/{market}/{symbol}", tags=["analysis"])
async def analyze_smart_money_structure(
    market: Literal["SPOT", "USD_M", "COIN_M"],
    symbol: str,
    interval: Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"] = "1h",
    limit: int = Query(default=300, ge=30, le=1000),
    swing_left: int = Query(default=3, ge=1, le=10),
    swing_right: int = Query(default=3, ge=1, le=10),
) -> dict:
    try:
        engine = SmartMoneyMarketStructure(historical_kline_store)
        return await asyncio.to_thread(
            engine.analyze, market, symbol, interval, limit, swing_left, swing_right,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/analysis/market-regime/{market}/{symbol}", tags=["analysis"])
async def analyze_historical_market_regime(
    market: Literal["SPOT", "USD_M", "COIN_M"],
    symbol: str,
    interval: Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"] = "1h",
    limit: int = Query(default=200, ge=40, le=1000),
) -> dict:
    try:
        engine = MarketRegimeAnalysis(historical_kline_store)
        return await asyncio.to_thread(engine.analyze, market, symbol, interval, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc



@app.get("/api/v1/analysis/futures/liquidation-clusters/{symbol}", tags=["analysis"])
async def analyze_liquidation_clusters(
    symbol: str,
    start_time_ms: int | None = Query(default=None, ge=0),
    end_time_ms: int | None = Query(default=None, ge=0),
    limit: int = Query(default=5000, ge=1, le=20000),
    bucket_bps: int = Query(default=25, ge=1, le=500),
    min_events: int = Query(default=1, ge=1, le=1000),
) -> dict:
    try:
        engine = LiquidationClusterAnalysis(liquidation_store)
        return await asyncio.to_thread(
            engine.analyze, symbol, start_time_ms, end_time_ms, limit,
            bucket_bps, min_events,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
