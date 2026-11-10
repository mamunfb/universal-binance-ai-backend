from __future__ import annotations
import math
from typing import Any
from app.services.historical_klines import HistoricalKlineStore
from app.services.market_confluence_store import MarketConfluenceStore

class MarketConfluencePerformance:
    """Descriptive forward outcomes for saved snapshots, not a strategy backtest."""
    HORIZONS_HOURS=(1,4,24)
    INTERVAL_MS={"1m":60_000,"3m":180_000,"5m":300_000,"15m":900_000,"30m":1_800_000,
        "1h":3_600_000,"2h":7_200_000,"4h":14_400_000,"6h":21_600_000,
        "8h":28_800_000,"12h":43_200_000,"1d":86_400_000}
    def __init__(self,snapshots:MarketConfluenceStore,klines:HistoricalKlineStore)->None:
        self.snapshots=snapshots; self.klines=klines
    def evaluate(self,market:str,symbol:str,interval:str="1h",price_interval:str="1m",limit:int=200)->dict[str,Any]:
        if price_interval not in {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d"}: raise ValueError("Unsupported price interval")
        history=self.snapshots.history(market,symbol,interval,limit); summaries={}
        for hours in self.HORIZONS_HOURS:
            outcomes=[]; pending=missing_ref=0
            for snap in history["snapshots"]:
                stamp=int(snap["analyzed_at_ms"]); ref=snap["reference_price"]; bias=snap["bias"]
                if ref is None or not math.isfinite(float(ref)) or float(ref)<=0: missing_ref+=1; continue
                target=stamp+hours*3_600_000
                candles=self.klines.history(market,symbol,price_interval,stamp+1,target+3_600_000,5000)["candles"]
                future=[c for c in candles if int(c["open_time_ms"])>stamp]
                end=next((c for c in future if int(c["close_time_ms"])>=target),None)
                if end is None: pending+=1; continue
                window=[c for c in future if int(c["close_time_ms"])<=int(end["close_time_ms"])]
                if not window: pending+=1; continue
                step=self.INTERVAL_MS[price_interval]
                expected=max(1,((int(window[-1]["open_time_ms"])-int(window[0]["open_time_ms"]))//step)+1)
                coverage_complete=len(window)==expected
                price=float(ref); close=float(end["close"]); high=max(float(c["high"]) for c in window); low=min(float(c["low"]) for c in window)
                move=(close-price)/price*100
                if bias=="BULLISH": direction=move; mfe=(high-price)/price*100; mae=(price-low)/price*100
                elif bias=="BEARISH": direction=-move; mfe=(price-low)/price*100; mae=(high-price)/price*100
                else: direction=mfe=mae=None
                outcomes.append({"snapshot_id":snap["snapshot_id"],"analyzed_at_ms":stamp,"bias":bias,"alignment":snap["alignment"],
                    "reference_price":price,"outcome_close":close,"outcome_close_time_ms":int(end["close_time_ms"]),
                    "actual_elapsed_hours":(int(end["close_time_ms"])-stamp)/3_600_000,"market_return_percent":move,
                    "directional_return_percent":direction,"favorable_excursion_percent":mfe,"adverse_excursion_percent":mae,
                    "directional_positive":direction>0 if direction is not None else None,
                    "future_candle_count":len(window),"future_candle_coverage_complete":coverage_complete})
            directional=[x for x in outcomes if x["directional_positive"] is not None]
            summaries[str(hours)]={"horizon_hours":hours,"status":"COMPLETED" if outcomes else "INSUFFICIENT_FUTURE_DATA",
                "sample_size":len(outcomes),"directional_sample_size":len(directional),"pending_or_not_matured":pending,
                "missing_reference_price":missing_ref,
                "directional_positive_fraction":sum(x["directional_positive"] for x in directional)/len(directional) if directional else None,
                "mean_directional_return_percent":sum(x["directional_return_percent"] for x in directional)/len(directional) if directional else None,
                "mean_favorable_excursion_percent":sum(x["favorable_excursion_percent"] for x in directional)/len(directional) if directional else None,
                "mean_adverse_excursion_percent":sum(x["adverse_excursion_percent"] for x in directional)/len(directional) if directional else None,
                "outcomes":outcomes}
        return {"status":"COMPLETED" if history["snapshots"] else "NO_STORED_SNAPSHOTS","market":market.upper(),"symbol":symbol.upper(),
            "interval":interval,"price_interval":price_interval,"snapshot_count":history["returned_count"],"horizons":summaries,
            "method":{"baseline":"Saved close of the last local candle fully closed at or before snapshot time.",
                "future_data":"Only candles whose open_time_ms is strictly later than analyzed_at_ms are eligible; each outcome reports local candle continuity.",
                "directional_metric":"Directional-positive fraction is descriptive, not a validated strategy hit rate.",
                "mixed_unknown":"Retained in raw outcomes but excluded from directional aggregates.",
                "mfe_mae":"Directional high/low excursion; not a stop/target simulation."},
            "limitations":["Local history only; missing candles are not interpolated or backfilled.",
                "No execution, fees, slippage, funding, leverage, position sizing, stop or target is simulated.",
                "Not strategy profitability, investment advice, or a forecast."]}
