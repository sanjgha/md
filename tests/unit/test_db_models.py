"""Tests for SQLAlchemy ORM models."""

from datetime import datetime
from src.db.models import Stock, DailyCandle, EconomicIndicator


def test_stock_model_creation(db_session):
    """Verify Stock model can be created and retrieved."""
    stock = Stock(symbol="AAPL", name="Apple Inc.", sector="Technology")
    db_session.add(stock)
    db_session.commit()

    retrieved = db_session.query(Stock).filter_by(symbol="AAPL").first()
    assert retrieved is not None
    assert retrieved.name == "Apple Inc."
    assert retrieved.sector == "Technology"


def test_daily_candle_relationship(db_session):
    """Verify DailyCandle foreign key relationship with Stock."""
    stock = Stock(symbol="MSFT", name="Microsoft", sector="Technology")
    db_session.add(stock)
    db_session.flush()

    candle = DailyCandle(
        stock_id=stock.id,
        timestamp=datetime(2024, 1, 2),
        open=150.0,
        high=152.0,
        low=149.0,
        close=151.0,
        volume=1000000,
    )
    db_session.add(candle)
    db_session.commit()

    retrieved = db_session.query(Stock).filter_by(symbol="MSFT").first()
    assert len(retrieved.daily_candles) == 1
    assert float(retrieved.daily_candles[0].close) == 151.0


def test_economic_indicator_model(db_session):
    """Verify EconomicIndicator model persists correctly."""
    ei = EconomicIndicator(
        indicator_name="CPI",
        release_date=datetime(2024, 1, 15),
        value=3.4,
        unit="percent",
    )
    db_session.add(ei)
    db_session.commit()

    retrieved = db_session.query(EconomicIndicator).filter_by(indicator_name="CPI").first()
    assert retrieved is not None
    assert float(retrieved.value) == 3.4


def test_scanner_result_jsonb_default(db_session):
    """Verify JSONB default=dict creates independent dicts per instance."""
    from src.db.models import ScannerResult

    stock = Stock(symbol="TSLA", name="Tesla")
    db_session.add(stock)
    db_session.flush()

    r1 = ScannerResult(stock_id=stock.id, scanner_name="test", matched_at=datetime.utcnow())
    r2 = ScannerResult(stock_id=stock.id, scanner_name="test2", matched_at=datetime.utcnow())
    db_session.add_all([r1, r2])
    db_session.commit()

    # Verify the two rows have independent metadata dicts
    r1.result_metadata["key"] = "val"
    assert "key" not in (r2.result_metadata or {})


def test_user_model_tablename():
    from src.db.models import User

    assert User.__tablename__ == "users"


def test_ui_setting_model_tablename():
    from src.db.models import UiSetting

    assert UiSetting.__tablename__ == "ui_settings"


def test_ui_setting_has_user_id_fk():
    from src.db.models import UiSetting

    col = UiSetting.__table__.c["user_id"]
    assert col.nullable is False
    assert len(col.foreign_keys) == 1


def test_ui_setting_unique_constraint():
    from src.db.models import UiSetting

    constraint_names = {c.name for c in UiSetting.__table__.constraints}
    assert "uq_ui_settings_user_key" in constraint_names


def test_schedule_config_model_has_expected_columns():
    """ScheduleConfig model defines all required columns."""
    from src.db.models import ScheduleConfig
    from sqlalchemy import inspect

    mapper = inspect(ScheduleConfig)
    col_names = {c.key for c in mapper.columns}
    assert col_names == {"job_id", "hour", "minute", "enabled", "auto_save", "updated_at"}
