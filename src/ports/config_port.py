from __future__ import annotations

from typing import Protocol, Literal, Optional
from pydantic import BaseModel
from typing import Optional


ModeType = Literal["testnet", "real"]
MarketType = Literal["futures", "spot"]


class ApiKeys(BaseModel):
    exchange: str
    mode: ModeType
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    passphrase: Optional[str] = None
    use_testnet: bool = True


class TradingConfig(BaseModel):
    timeframe: str = "5m"
    rr: float = 1.5
    filter_weak_signal: bool = True
    weak_body_ratio_max: float = 0.25
    range_cross_ema_count: int = 3
    sessions_filter: bool = True
    sessions_timezone: str = "Europe/Madrid"
    sessions_allowed: str = "08:00-17:00,14:00-22:00"
    position_mode: str = "usdt_value"
    reduce_only_on_exit: bool = True
    max_retries: int = 5
    pairs_source: str = "exchange"
    pairs_file: str = "config/pairs.txt"
    spread_max_pct: float = 0.08
    slippage_pct: float = 0.02
    # Break-even
    breakeven_enabled: bool = True
    breakeven_trigger_rr: float = 1.0
    breakeven_offset_ticks: int = 0
    breakeven_offset_pct: float = 0.02
    # Trailing
    trailing_enabled: bool = True
    trailing_mode: str = "percent"  # percent | atr
    trailing_percent: float = 0.5
    trailing_step_pct: float = 0.1
    atr_period: int = 14
    atr_multiplier: float = 2.0
    # TP mode
    take_profit_mode: str = "fixed"  # fixed | none


class RiskConfig(BaseModel):
    max_open_trades: int = 1
    max_daily_loss_pct: float = 3
    max_daily_trades: int = 10


class ConfigPort(Protocol):
    def ensure_defaults(self) -> None: ...

    def load_api_keys(self, preferred_exchange: Optional[str] = None) -> ApiKeys: ...

    def load_trading(self) -> TradingConfig: ...

    def load_risk(self) -> RiskConfig: ...

    def load_pairs_from_file(self, path: str) -> list[str]: ...
