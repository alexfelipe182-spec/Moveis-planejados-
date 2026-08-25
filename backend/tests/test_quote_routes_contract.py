from fastapi.routing import APIRoute

from app.api.routes import api_router


def test_quote_routes_have_no_duplicate_methods_and_paths():
    routes = [route for route in api_router.routes if isinstance(route, APIRoute)]
    seen = set()
    for route in routes:
        for method in route.methods or set():
            key = (method, route.path)
            assert key not in seen, f"duplicate route: {key}"
            seen.add(key)


def test_quote_creation_and_estimate_are_explicit_routes():
    routes = [route for route in api_router.routes if isinstance(route, APIRoute)]
    paths = {(method, route.path) for route in routes for method in (route.methods or set())}
    assert ("POST", "/api/v1/quotes") in paths
    assert ("POST", "/api/v1/quotes/estimate") in paths
    assert ("PUT", "/api/v1/quotes/{item_id}") in paths
