from starlette.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Activity, User


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    return {"X-CSRF-Token": token} if token else {}


def admin_client(email: str) -> TestClient:
    client = TestClient(app)
    password = "Senha-Forte-123!"
    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Production Admin", "email": email, "password": password},
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
    return client


def test_project_production_workflow_requires_ordered_transitions():
    client = admin_client("project.workflow@example.com")
    headers = csrf_headers(client)

    customer = client.post(
        "/api/v1/customers",
        json={"name": "Cliente Produção", "email": "producao@example.com", "phone": "13999990001"},
        headers=headers,
    )
    assert customer.status_code == 201

    project = client.post(
        "/api/v1/projects",
        json={
            "customer_id": customer.json()["id"],
            "name": "Cozinha Produção",
            "description": "Projeto para validar fluxo de fábrica",
            "status": "planning",
        },
        headers=headers,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    assert project.json()["status"] == "planning"

    bypass = client.put(
        f"/api/v1/projects/{project_id}",
        json={"status": "completed"},
        headers=headers,
    )
    assert bypass.status_code == 422

    invalid_jump = client.patch(
        f"/api/v1/projects/{project_id}/status",
        json={"status": "production"},
        headers=headers,
    )
    assert invalid_jump.status_code == 409

    expected_flow = [
        "measurement",
        "technical_design",
        "purchasing",
        "production",
        "installation",
        "delivered",
        "completed",
    ]
    for status in expected_flow:
        response = client.patch(
            f"/api/v1/projects/{project_id}/status",
            json={"status": status},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    after_completed = client.patch(
        f"/api/v1/projects/{project_id}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert after_completed.status_code == 409

    db = SessionLocal()
    try:
        transitions = (
            db.query(Activity)
            .filter(
                Activity.entity == "project",
                Activity.entity_id == project_id,
                Activity.action == "status_changed",
            )
            .all()
        )
        assert len(transitions) == len(expected_flow)
        assert "planning → measurement" in transitions[0].description
        assert "delivered → completed" in transitions[-1].description
    finally:
        db.close()


def test_project_can_be_cancelled_before_completion():
    client = admin_client("project.cancel@example.com")
    headers = csrf_headers(client)

    customer = client.post(
        "/api/v1/customers",
        json={"name": "Cliente Cancelamento", "email": "cancelamento@example.com"},
        headers=headers,
    )
    assert customer.status_code == 201

    project = client.post(
        "/api/v1/projects",
        json={"customer_id": customer.json()["id"], "name": "Projeto Cancelável"},
        headers=headers,
    )
    assert project.status_code == 201

    cancelled = client.patch(
        f"/api/v1/projects/{project.json()['id']}/status",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
