from app.main import app


OPENAPI_PATHS = app.openapi()["paths"]


def _methods(path: str) -> set[str]:
    return {method.upper() for method in OPENAPI_PATHS.get(path, {})}


def test_quote_routes_are_exposed_in_openapi_contract():
    prefix = "/api/v1/quotes"

    assert "POST" in _methods(prefix)
    assert "GET" in _methods(prefix)
    assert "POST" in _methods(f"{prefix}/estimate")
    assert "PUT" in _methods(f"{prefix}/{{item_id}}")
    assert "GET" in _methods(f"{prefix}/{{item_id}}")
    assert "DELETE" in _methods(f"{prefix}/{{item_id}}")


def test_openapi_operation_ids_are_unique():
    operation_ids = [
        operation["operationId"]
        for path_item in OPENAPI_PATHS.values()
        for method, operation in path_item.items()
        if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}
        and isinstance(operation, dict)
        and "operationId" in operation
    ]

    assert len(operation_ids) == len(set(operation_ids))
