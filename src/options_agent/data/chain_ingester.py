"""Orchestrates pulling options chains from Dolthub into PostgreSQL."""

from datetime import date, datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.db.models import OptionsEodChain
from src.options_agent.data.dolt_client import DoltOptionsClient
from src.options_agent.data.expiries import ExpiryBucket


class ChainIngester:
    """Pulls options chain rows from Dolthub and upserts them into PostgreSQL."""

    def __init__(self, dolt_client: DoltOptionsClient, session: Session):
        """Store the Dolt client and DB session."""
        self._client = dolt_client
        self._session = session

    def ingest_for_symbol(
        self,
        symbol: str,
        as_of: date,
        buckets: list[ExpiryBucket],
    ) -> int:
        """Ingest contracts for symbol across all expiry buckets; return row count inserted."""
        total = 0
        now = datetime.now(timezone.utc)
        contracts = self._client.fetch_chain(symbol, as_of)
        for bucket in buckets:
            relevant = [c for c in contracts if c.expiry_date == bucket.expiry]
            if not relevant:
                continue
            rows = [
                {
                    "symbol": c.symbol,
                    "as_of_date": as_of,
                    "expiry_date": c.expiry_date,
                    "expiry_bucket": bucket.label,
                    "contract_type": c.contract_type,
                    "strike": c.strike,
                    "bid": c.bid,
                    "ask": c.ask,
                    "mid": c.mid,
                    "last": c.last,
                    "volume": c.volume,
                    "open_interest": c.open_interest,
                    "iv": c.iv,
                    "delta": c.delta,
                    "gamma": c.gamma,
                    "theta": c.theta,
                    "vega": c.vega,
                    "ingested_at": now,
                }
                for c in relevant
            ]
            stmt = (
                pg_insert(OptionsEodChain)
                .values(rows)
                .on_conflict_do_nothing(constraint="uq_chain_contract")
            )
            result = self._session.execute(stmt)
            self._session.commit()
            total += result.rowcount  # type: ignore[attr-defined]
        return total

    def ingest_for_symbols(
        self,
        symbols: list[str],
        as_of: date,
        buckets: list[ExpiryBucket],
    ) -> int:
        """Ingest contracts for multiple symbols; return total row count inserted."""
        return sum(self.ingest_for_symbol(s, as_of, buckets) for s in symbols)
