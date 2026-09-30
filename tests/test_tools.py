import json
from pathlib import Path

import app


def test_get_existing_order():
    result = app.get_order("ORD-1002")
    assert result["status"] == "success"
    assert result["order"]["status"] == "delayed"


def test_unknown_order():
    result = app.get_order("ORD-9999")
    assert result["status"] == "error"
    assert result["error"] == "order_not_found"


def test_policy_lookup():
    result = app.get_policy("late_delivery")
    assert result["status"] == "success"
    assert "escalation ticket" in result["policy"]["rule"]


def test_ticket_creation_and_verification(tmp_path, monkeypatch):
    # Use a temporary copy so the real demo ticket file is not changed.
    original_data_dir = app.DATA_DIR
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)

    (tmp_path / "orders.json").write_text(
        (original_data_dir / "orders.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "policies.json").write_text(
        (original_data_dir / "policies.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "tickets.json").write_text("[]", encoding="utf-8")

    created = app.create_support_ticket(
        order_id="ORD-1002",
        issue="Late delivery",
        priority="high",
    )
    assert created["status"] == "success"

    ticket_id = created["ticket"]["ticket_id"]
    verified = app.get_ticket(ticket_id)

    assert verified["status"] == "success"
    assert verified["ticket"]["order_id"] == "ORD-1002"
