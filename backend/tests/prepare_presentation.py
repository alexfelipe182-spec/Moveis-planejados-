"""Prepare a repeatable synthetic case ONLY in the existing loopback preview.

IDEAL_LOCAL_PREVIEW=1 python tests/prepare_presentation.py
No database imports, production URLs, redirects, deletions or record updates.
Run one instance at a time. Existing matching records are reused, never reset.
"""

import json
import os
from decimal import Decimal
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, ProxyHandler, Request, build_opener

ORIGIN = "http://127.0.0.1:8765"
TAG = "DEMONSTRAÇÃO"


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("A prévia não pode redirecionar para outro endereço.")


class PreviewClient:
    def __init__(self):
        self.opener = build_opener(ProxyHandler({}), NoRedirects(), HTTPCookieProcessor(CookieJar()))
        self.csrf = ""
        self.verified = False
        self.created = 0

    def raw(self, path, method="GET", payload=None):
        if not path.startswith("/") or path.startswith("//") or method not in {"GET", "POST"}:
            raise RuntimeError("Operação não permitida na preparação.")
        if method != "GET" and not self.verified:
            raise RuntimeError("Confirme a prévia sintética antes de gravar.")
        headers = {"Content-Type": "application/json", "X-CSRF-Token": self.csrf}
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        if path == "/api/v1/auth/login" and payload is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = urlencode(payload).encode("utf-8")
        with self.opener.open(Request(ORIGIN + path, data=data, headers=headers, method=method), timeout=20) as response:
            return response.read().decode("utf-8")

    def verify(self):
        if os.getenv("IDEAL_LOCAL_PREVIEW") != "1":
            raise RuntimeError("Ative IDEAL_LOCAL_PREVIEW=1 para preparar apenas a demonstração local.")
        html = self.raw("/")
        config = self.raw("/site-config.js")
        if "AMBIENTE DE TESTE — dados sintéticos, sem envio de mensagens" not in html:
            raise RuntimeError("Página sem identificação da prévia sintética; nada foi gravado.")
        if "window.API_BASE_URL = window.location.origin + '/api/v1';" not in config:
            raise RuntimeError("A API não foi identificada como local; nada foi gravado.")
        self.verified = True

    def api(self, path, payload=None):
        text = self.raw("/api/v1" + path, "GET" if payload is None else "POST", payload)
        return json.loads(text) if text else None

    def rows(self, path):
        rows, offset = [], 0
        while True:
            query = urlencode({"offset": offset, "limit": 100})
            page = self.api(path + "?" + query)
            if not isinstance(page, list):
                raise RuntimeError("Resposta inesperada da lista de demonstração.")
            rows.extend(page)
            if len(page) < 100 or path.endswith("/items"):
                return rows
            offset += 100

    def ensure(self, path, key, payload, list_path=None):
        matches = [row for row in self.rows(list_path or path) if row.get(key) == payload[key]]
        if len(matches) > 1:
            raise RuntimeError("Há exemplos duplicados. Confira a lista; nenhum deles será apagado.")
        if matches:
            row = matches[0]
            numeric = {"quantity", "unit_cost", "unit_price", "waste_percent"}
            for field, expected in payload.items():
                actual = row.get(field)
                if field in numeric and actual is not None:
                    actual, expected = Decimal(str(actual)), Decimal(str(expected))
                if actual != expected:
                    raise RuntimeError("O exemplo foi alterado. Seus dados foram preservados; confira " + field + ".")
            return row
        result = self.api(path, payload)
        self.created += 1
        return result


def prepare(client):
    customer = client.ensure("/customers", "name", {
        "name": "Cliente Aurora — " + TAG, "email": "aurora@example.com",
    })
    supplier = client.ensure("/suppliers", "name", {
        "name": "Fornecedor Aurora — " + TAG, "notes": "Cadastro fictício. Sem contato ou pedidos reais.",
    })
    material = client.ensure("/materials", "name", {
        "name": "MDF 18 mm — " + TAG, "kind": "mdf", "supplier_id": supplier["id"],
        "unit": "chapa", "unit_cost": "300.00", "waste_percent": "10.00",
    })
    quote = client.ensure("/quotes", "description", {
        "customer_id": customer["id"], "description": "[DEMONSTRAÇÃO] Cozinha Aurora",
        "measurements": "Parede de 3,00 m; medidas ilustrativas, sujeitas a conferência.",
        "materials": "MDF 18 mm e ferragens de demonstração.",
    })
    items_path = f"/quotes/{quote['id']}/items"
    for name, price in [("Armário inferior", "2400.00"), ("Armário aéreo", "1800.00")]:
        client.ensure(items_path, "name", {
            "name": name + " — " + TAG, "description": "Móvel fictício para apresentação.",
            "quantity": "1.00", "unit_price": price,
        })
    project = client.ensure("/projects", "name", {
        "customer_id": customer["id"], "name": "Cozinha Aurora — " + TAG,
        "description": "Projeto demonstrativo cadastrado separadamente do orçamento. Sem obra real.",
    })
    costs_path = f"/project-costs/project/{project['id']}"
    for category, name, quantity, cost, material_id in [
        ("material", "Duas chapas de MDF com perda de 10%", "2", "300.00", material["id"]),
        ("labor", "Oito horas de marcenaria", "8", "50.00", None),
        ("installation", "Instalação ilustrativa", "1", "200.00", None),
    ]:
        client.ensure("/project-costs", "description", {
            "project_id": project["id"], "category": category, "description": name + " — " + TAG,
            "quantity": quantity, "unit_cost": cost, "material_id": material_id,
        }, list_path=costs_path)
    quote = client.api(f"/quotes/{quote['id']}")
    costs = client.api(costs_path + "/total")
    if Decimal(str(quote["total"])) != Decimal("4200") or Decimal(str(costs["total_cost"])) != Decimal("1260"):
        raise RuntimeError("Totais diferentes do roteiro. Confira os lançamentos; nada foi removido.")
    return {"cliente": customer["id"], "orcamento": quote["id"], "projeto": project["id"],
            "proposta": quote["total"], "custos_registrados": costs["total_cost"],
            "registros_criados": client.created}


def main():
    client = PreviewClient()
    client.verify()
    login = client.api("/auth/login", {"username": "preview@example.com", "password": "Preview-local-123!"})
    client.csrf = login["csrf_token"]
    try:
        me = client.api("/me")
        if me.get("email") != "preview@example.com" or me.get("is_admin") is not True:
            raise RuntimeError("A conta sintética administrativa não foi confirmada.")
        print(json.dumps(prepare(client), ensure_ascii=False))
    finally:
        client.api("/auth/logout", {})


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, HTTPError, OSError) as error:
        # Do not dump response bodies, cookies or credentials on failure.
        raise SystemExit("Preparação interrompida; confira a prévia antes de repetir. " + str(error)) from None
