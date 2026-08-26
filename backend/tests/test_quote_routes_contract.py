from collections import Counter

from app.api.routes import api_router


def _route_keys() -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for route in api_router.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        keys.extend((method, path) for method in methods)
    return keys


def test_api_router_has_no_duplicate_methods_and_paths():
    counts = Counter(_route_keys())
    duplicates = {key: count for key, count in counts.items() if count > 1}
    assert duplicates == {}


def test_quote_routes_are_explicit_and_not_duplicated():
    keys = set(_route_keys())
    prefix = "/api/v1/quotes"
    assert ("POST", prefix) in keys
    assert ("POST", f"{prefix}/estimate") in keys
    assert ("PUT", f"{prefix}/{{item_id}}") in keys
    assert ("GET", prefix) in keys
    assert ("GET", f"{prefix}/{{item_id}}") in keys
    assert ("DELETE", f"{prefix}/{{item_id}}") in keys
