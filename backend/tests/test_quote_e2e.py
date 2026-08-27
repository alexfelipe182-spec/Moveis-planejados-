import json

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Activity, Project, User


def csrf_headers(client):
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def test_quote_creation_end_to_end_persists_analysis_and_automation():
    client = TestClient(app)
    email = "quote.e2e.admin@example.com"
    password = "Senha-Forte-123!"

    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Quote E2E Admin", "email": email, "password": password},
    )
    assert registered.status_code == 201

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_admin = True
        db.commit()
    finally:
        db.close()

    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200

    customer = client.post(
        "/api/v1/customers",
        json={"name": "Cliente E2E", "email": "cliente.e2e@example.com", "phone": "+5513999999999"},
        headers=csrf_headers(client),
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    quote = client.post(
        "/api/v1/quotes",
        json={
            "customer_id": customer_id,
            "description": "Cozinha planejada E2E",
            "measurements": "3,00m x 2,50m",
            "materials": "MDF 18mm",
            "material_cost": "800.00",
            "hardware_cost": "350.00",
            "labor_cost": "900.00",
            "finishing_cost": "450.00",
            "profit_margin": "30.00",
        },
        headers=csrf_headers(client),
    )
    assert quote.status_code == 201, quote.text
    body = quote.json()
    assert body["suggested_total"] == "3250.00"
    assert body["total"] == "3250.00"
    assert body["status"] == "analysis"
    assert body["ai_analysis"] is not None
    analysis = json.loads(body["ai_analysis"])
    assert analysis["source"] == "local-analysis"
    assert analysis["financial_values_locked"] is True
    assert body["ai_analyzed_at"] is not None

    fetched = client.get(f"/api/v1/quotes/{body['id']}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["suggested_total"] == "3250.00"
    assert fetched_body["ai_analysis"] == body["ai_analysis"]
    assert fetched_body["ai_analyzed_at"] == body["ai_analyzed_at"]

    status_bypass = client.put(
        f"/api/v1/quotes/{body['id']}",
        json={"status": "accepted"},
        headers=csrf_headers(client),
    )
    assert status_bypass.status_code == 409

    share_before_approval = client.post(
        f"/api/v1/quotes/{body['id']}/shared",
        headers=csrf_headers(client),
    )
    assert share_before_approval.status_code == 409

    approved = client.patch(
        f"/api/v1/quotes/{body['id']}/decision",
        json={"status": "approved"},
        headers=csrf_headers(client),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    edit_after_approval = client.put(
        f"/api/v1/quotes/{body['id']}",
        json={"description": "Tentativa de alterar proposta já aprovada"},
        headers=csrf_headers(client),
    )
    assert edit_after_approval.status_code == 409

    shared = client.post(
        f"/api/v1/quotes/{body['id']}/shared",
        headers=csrf_headers(client),
    )
    assert shared.status_code == 200, shared.text
    assert shared.json()["status"] == "sent"

    second_share = client.post(
        f"/api/v1/quotes/{body['id']}/shared",
        headers=csrf_headers(client),
    )
    assert second_share.status_code == 409

    accepted = client.patch(
        f"/api/v1/quotes/{body['id']}/commercial-status",
        json={"status": "accepted"},
        headers=csrf_headers(client),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    second_commercial_decision = client.patch(
        f"/api/v1/quotes/{body['id']}/commercial-status",
        json={"status": "declined"},
        headers=csrf_headers(client),
    )
    assert second_commercial_decision.status_code == 409

    db = SessionLocal()
    try:
        shared_activity = (
            db.query(Activity)
            .filter(Activity.entity == "quote", Activity.entity_id == body["id"], Activity.action == "shared")
            .one()
        )
        assert "envio da proposta" in shared_activity.description

        accepted_activity = (
            db.query(Activity)
            .filter(Activity.entity == "quote", Activity.entity_id == body["id"], Activity.action == "accepted")
            .one()
        )
        assert "cliente aceitou" in accepted_activity.description

        project = db.query(Project).filter(Project.quote_id == body["id"]).one()
        assert project.customer_id == customer_id
        assert project.name == f"Projeto do orçamento #{body['id']}"
        assert project.description == "Cozinha planejada E2E"
        assert project.measurements == "3,00m x 2,50m"
        assert project.materials == "MDF 18mm"
        assert project.status == "planning"

        project_activity = (
            db.query(Activity)
            .filter(
                Activity.entity == "project",
                Activity.entity_id == project.id,
                Activity.action == "created_from_quote",
            )
            .one()
        )
        assert f"quote #{body['id']}" in project_activity.description
    finally:
        db.close()

    second_decision = client.patch(
        f"/api/v1/quotes/{body['id']}/decision",
        json={"status": "rejected"},
        headers=csrf_headers(client),
    )
    assert second_decision.status_code == 409
