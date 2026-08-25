from fastapi.routing import APIRoute

from app.api.routes import api_router


def _route_keys() -> set[tuple[str, str]]:
    routes = [route for route in api_router.routes if isinstance(route, APIRoute)]
    return {
        (method, route.path)
        for route in routes
        for method in (route.methods or set())
    }


def test_api_router_has_no_duplicate_methods_and_paths():
    keys = _route_keys()
    assert len(keys) == len({key for key in keys})


def test_quote_routes_are_explicit_and_not_duplicated():
    keys = _route_keys()
    assert ("POST", "/quotes") in keys
    assert ("POST", "/quotes/estimate") in keys
    assert ("PUT", "/quotes/{item_id}") in keys
    assert ("GET", "/quotes") in keys
    assert ("GET", "/quotes/{item_id}") in keys
    assert ("DELETE", "/quotes/{item_id}") in keys
