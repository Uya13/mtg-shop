import os
from concurrent.futures import ThreadPoolExecutor

import pytest


def test_catalog_lifecycle(client, deck_data):
    response = client.post("/decks", json=deck_data)
    assert response.status_code == 201
    deck_id = response.json()["id"]
    assert response.json()["stock"] == 0
    assert response.json()["cards"][0]["quantity"] == 24
    assert client.get(f"/decks/{deck_id}").json()["sku"] == "MTG-001"
    assert len(client.get("/decks").json()) == 1
    updated = {**deck_data, "name": "Новое название", "cards": []}
    assert client.put(f"/decks/{deck_id}", json=updated).json()["cards"] == []
    assert client.get(f"/decks/{deck_id}").json()["name"] == "Новое название"
    assert client.delete(f"/decks/{deck_id}").status_code == 204
    assert client.get(f"/decks/{deck_id}").status_code == 404


def test_duplicate_sku(client, deck_data):
    assert client.post("/decks", json=deck_data).status_code == 201
    assert client.post("/decks", json=deck_data).status_code == 409
    assert len(client.get("/decks").json()) == 1


def test_sale_receipt_and_history(client, deck_data):
    deck_id = client.post("/decks", json=deck_data).json()["id"]
    url = f"/decks/{deck_id}/movements"
    assert client.post(url, json={"kind": "sale", "quantity": 1}).status_code == 409
    assert client.post(url, json={"kind": "receipt", "quantity": 3}).status_code == 201
    assert client.post(url, json={"kind": "sale", "quantity": 2}).status_code == 201
    assert client.get(f"/decks/{deck_id}").json()["stock"] == 1
    assert client.post(url, json={"kind": "sale", "quantity": 2}).status_code == 409
    assert client.get(f"/decks/{deck_id}").json()["stock"] == 1
    assert len(client.get(url).json()) == 2
    assert client.delete(f"/decks/{deck_id}").status_code == 409


def test_revenue_keeps_sale_price(client, deck_data):
    deck_id = client.post("/decks", json=deck_data).json()["id"]
    url = f"/decks/{deck_id}/movements"
    client.post(url, json={"kind": "receipt", "quantity": 3})
    client.post(url, json={"kind": "sale", "quantity": 2})
    client.put(f"/decks/{deck_id}", json={**deck_data, "price_rub": "2000.00"})
    summary = client.get("/summary").json()
    assert summary == {
        "deck_types": 1,
        "decks_in_stock": 1,
        "stock_value_rub": "2000.00",
        "sold_quantity": 2,
        "revenue_rub": "3001.00",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"price_rub": "-1"},
        {"price_rub": "1.001"},
        {"name": "   "},
        {"format": "Unknown"},
        {"stock": 5},
        {"cards": [{"name": "Forest", "quantity": 0}]},
        {"cards": [{"name": "Forest", "quantity": 1}] * 2},
    ],
)
def test_invalid_deck(client, deck_data, change):
    assert client.post("/decks", json={**deck_data, **change}).status_code == 422


def test_invalid_movements(client, deck_data):
    deck_id = client.post("/decks", json=deck_data).json()["id"]
    url = f"/decks/{deck_id}/movements"
    for quantity in [0, -1, True, 1.5]:
        assert client.post(url, json={"kind": "receipt", "quantity": quantity}).status_code == 422


def test_filters(client, deck_data):
    deck_id = client.post("/decks", json=deck_data).json()["id"]
    assert client.get("/decks?in_stock=true").json() == []
    client.post(f"/decks/{deck_id}/movements", json={"kind": "receipt", "quantity": 1})
    assert len(client.get("/decks?in_stock=true&format=Other").json()) == 1
    assert client.get("/decks?format=Commander").json() == []
    assert client.get("/decks?offset=1").json() == []
    assert client.get("/decks?limit=0").status_code == 422


def test_health_docs_metrics(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}
    assert client.get("/docs").status_code == 200
    assert "/decks" in client.get("/openapi.json").json()["paths"]
    assert "http_requests_total" in client.get("/metrics").text


def test_missing_deck(client):
    assert client.get("/decks/999").status_code == 404
    assert client.get("/decks/999/movements").status_code == 404


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="Конкурентные продажи проверяются на настоящем PostgreSQL",
)
def test_concurrent_sales_cannot_oversell(client, deck_data):
    deck_id = client.post("/decks", json=deck_data).json()["id"]
    url = f"/decks/{deck_id}/movements"
    client.post(url, json={"kind": "receipt", "quantity": 1})

    def sell(_):
        return client.post(url, json={"kind": "sale", "quantity": 1}).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(sell, range(2))) == [201, 409]
    assert client.get(f"/decks/{deck_id}").json()["stock"] == 0
    assert len(client.get(url).json()) == 2
