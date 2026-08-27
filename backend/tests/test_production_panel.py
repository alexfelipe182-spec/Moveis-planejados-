import pytest

from app.core.security import create_access_token
from test_access_boundaries import access_client as access_client


def test_supplier_material_search_and_paginated_project_costs(access_client):
    access_client.headers["Authorization"] = f"Bearer {create_access_token('1')}"
    supplier = access_client.post("/api/v1/suppliers", json={"name": "Fornecedor Especial", "email": None})
    assert supplier.status_code == 201
    supplier_id = supplier.json()["id"]
    material = access_client.post("/api/v1/materials", json={
        "name": "Chapa de teste", "kind": "mdf", "supplier_id": supplier_id,
        "unit_cost": "100", "waste_percent": "10",
    })
    assert material.status_code == 201
    found = access_client.get("/api/v1/materials?q=Fornecedor%20Especial")
    assert found.headers["X-Total-Count"] == "1"
    assert found.json()[0]["id"] == material.json()["id"]
    assert access_client.get("/api/v1/suppliers?q=Especial").json()[0]["id"] == supplier_id
    customer = access_client.post("/api/v1/customers", json={"name": "Cliente Produção"}).json()
    project = access_client.post("/api/v1/projects", json={"name": "Projeto teste", "customer_id": customer["id"]}).json()
    for description in ("Chapas de MDF", "Mais chapas"):
        response = access_client.post("/api/v1/project-costs", json={
            "project_id": project["id"], "material_id": material.json()["id"],
            "description": description, "category": "material", "quantity": "2", "unit_cost": "0",
        })
        assert response.status_code == 201
        assert response.json()["total_cost"] == "220.00"
    costs = access_client.get(f"/api/v1/project-costs/project/{project['id']}?offset=1&limit=1")
    assert costs.status_code == 200
    assert costs.headers["X-Total-Count"] == "2"
    assert len(costs.json()) == 1
    assert costs.json()[0]["description"] == "Mais chapas"
    total = access_client.get(f"/api/v1/project-costs/project/{project['id']}/total")
    assert total.json()["total_cost"] == "440.00"
    assert access_client.get(f"/api/v1/project-costs/project/{project['id']}?limit=101").status_code == 422


def test_costs_without_material_are_isolated_by_project(access_client):
    access_client.headers["Authorization"] = f"Bearer {create_access_token('1')}"
    customer = access_client.post("/api/v1/customers", json={"name": "Cliente teste"}).json()
    projects = [access_client.post("/api/v1/projects", json={
        "name": name, "customer_id": customer["id"],
    }).json()["id"] for name in ("Projeto A", "Projeto B")]
    response = access_client.post("/api/v1/project-costs", json={
        "project_id": projects[0], "material_id": None, "category": "labor",
        "description": "Montagem de teste", "quantity": "1.5", "unit_cost": "50",
    })
    assert response.status_code == 201
    assert response.json()["total_cost"] == "75.00"
    assert response.json()["material_id"] is None
    other = access_client.get(f"/api/v1/project-costs/project/{projects[1]}")
    assert other.json() == []
    assert other.headers["X-Total-Count"] == "0"
    assert access_client.get(f"/api/v1/project-costs/project/{projects[1]}/total").json()["total_cost"] == "0.00"
    beyond = access_client.get(f"/api/v1/project-costs/project/{projects[0]}?offset=10&limit=1")
    assert beyond.json() == []
    assert beyond.headers["X-Total-Count"] == "1"


@pytest.mark.parametrize("query", ["offset=-1", "limit=0", "limit=101", "limit=invalid"])
def test_cost_pagination_rejects_invalid_parameters(access_client, query):
    access_client.headers["Authorization"] = f"Bearer {create_access_token('1')}"
    assert access_client.get(f"/api/v1/project-costs/project/1?{query}").status_code == 422


def test_missing_project_cost_reads_return_not_found(access_client):
    access_client.headers["Authorization"] = f"Bearer {create_access_token('1')}"
    for suffix in ("", "/total"):
        assert access_client.get(f"/api/v1/project-costs/project/999{suffix}").status_code == 404
