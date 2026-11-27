import json
import sys
import urllib.error
import urllib.request
import uuid

base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def request(path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        base + path, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"HTTP {error.code}: {error.read().decode()}") from error
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


deck = request(
    "/decks",
    {
        "sku": f"DEMO-{uuid.uuid4().hex[:8]}",
        "name": "Учебная колода — зелёная",
        "format": "Other",
        "price_rub": "1500.50",
        "cards": [
            {"name": "Forest", "quantity": 24},
            {"name": "Llanowar Elves", "quantity": 4},
        ],
    },
)
path = f"/decks/{deck['id']}"
request(path + "/movements", {"kind": "receipt", "quantity": 5})
request(path + "/movements", {"kind": "sale", "quantity": 2})
request(path)
request("/summary")
