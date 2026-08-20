from app.main import app


def test_auth_routes_are_registered_once():
    matching_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/auth/login" and "POST" in getattr(route, "methods", set())
    ]

    assert len(matching_routes) == 1
