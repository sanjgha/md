"""Client for reading options chains from a local dolt sql-server."""

import time
from dataclasses import dataclass
from datetime import date

import pymysql
import pymysql.cursors


@dataclass
class OptionsContract:
    """A single options contract row from Dolthub."""

    symbol: str
    expiry_date: date
    contract_type: str  # "C" | "P"
    strike: float
    bid: float | None
    ask: float | None
    mid: float | None
    last: float | None
    volume: int | None
    open_interest: int | None
    iv: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None


class DoltOptionsClient:
    """Connects to a Dolt SQL server and fetches options chain data."""

    def __init__(self, url: str):
        """Parse mysql+pymysql URL and store connection kwargs."""
        rest = url.replace("mysql+pymysql://", "")
        user_host, db = rest.rsplit("/", 1)
        if "@" in user_host:
            user, host_port = user_host.rsplit("@", 1)
        else:
            user, host_port = "root", user_host
        if ":" in host_port:
            host, port_str = host_port.rsplit(":", 1)
            port = int(port_str)
        else:
            host, port = host_port, 3306
        self._connect_kwargs = dict(
            host=host,
            port=port,
            user=user,
            database=db,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def _connect(self):
        """Open and return a new pymysql connection."""
        return pymysql.connect(**self._connect_kwargs)

    def ping(self) -> bool:
        """Return True if the Dolt server is reachable."""
        try:
            conn = self._connect()
            conn.close()
            return True
        except Exception:
            return False

    def fetch_chain(
        self, symbol: str, as_of: date, expiries: list[date] | None = None, retries: int = 3
    ) -> list[OptionsContract]:
        """Fetch options contracts for symbol on as_of date.

        If expiries is provided, filters to those expiration dates at the SQL level.
        Otherwise fetches the entire chain (backward compatible).
        """
        if expiries is not None and len(expiries) == 0:
            return []

        sql = """
            SELECT underlying, expiration, type, strike,
                   bid, ask, (bid+ask)/2 as mid, last,
                   volume, open_interest,
                   implied_volatility as iv,
                   delta, gamma, theta, vega
            FROM options
            WHERE underlying = %s AND date = %s
        """
        params = [symbol.upper(), as_of.isoformat()]

        if expiries:
            placeholders = ", ".join(["%s"] * len(expiries))
            sql += f" AND expiration IN ({placeholders})"
            params.extend([e.isoformat() for e in expiries])

        for attempt in range(retries):
            try:
                conn = self._connect()
                with conn.cursor() as cur:
                    cur.execute(sql, tuple(params))
                    rows = cur.fetchall()
                conn.close()
                return [self._row_to_contract(r) for r in rows]
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("unreachable")  # loop always returns or raises

    def _row_to_contract(self, row: dict) -> OptionsContract:
        """Convert a DB row dict to an OptionsContract dataclass."""
        return OptionsContract(
            symbol=row["underlying"],
            expiry_date=(
                row["expiration"]
                if isinstance(row["expiration"], date)
                else date.fromisoformat(str(row["expiration"]))
            ),
            contract_type=row["type"],
            strike=float(row["strike"]),
            bid=float(row["bid"]) if row["bid"] is not None else None,
            ask=float(row["ask"]) if row["ask"] is not None else None,
            mid=float(row["mid"]) if row["mid"] is not None else None,
            last=float(row["last"]) if row["last"] is not None else None,
            volume=int(row["volume"]) if row["volume"] is not None else None,
            open_interest=int(row["open_interest"]) if row["open_interest"] is not None else None,
            iv=float(row["iv"]) if row["iv"] is not None else None,
            delta=float(row["delta"]) if row["delta"] is not None else None,
            gamma=float(row["gamma"]) if row["gamma"] is not None else None,
            theta=float(row["theta"]) if row["theta"] is not None else None,
            vega=float(row["vega"]) if row["vega"] is not None else None,
        )
