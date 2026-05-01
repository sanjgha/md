from src.scanner.registry_factory import build_scanner_registry, REGISTERED_SCANNER_NAMES


def test_build_scanner_registry_returns_all_active_scanners():
    registry = build_scanner_registry()
    names = set(registry.list().keys())
    assert names == {
        "volume",
        "smart_money",
        "six_month_high",
        "weekly_options",
        "pullback_continuation",
    }


def test_registered_scanner_names_matches_registry():
    registry = build_scanner_registry()
    assert REGISTERED_SCANNER_NAMES == set(registry.list().keys())


def test_registry_get_returns_scanner_instance():
    registry = build_scanner_registry()
    scanner = registry.get("volume")
    assert scanner is not None
    assert hasattr(scanner, "scan")


def test_registry_get_unknown_returns_none():
    registry = build_scanner_registry()
    assert registry.get("momentum") is None
    assert registry.get("price_action") is None
