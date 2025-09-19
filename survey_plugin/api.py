import os
from flask import Blueprint, request, jsonify
import requests

bp = Blueprint("wazo_survey", __name__)

def _token():
    h = request.headers
    if "X-Auth-Token" in h: return h["X-Auth-Token"]
    if h.get("Authorization","").startswith("Bearer "):
        return h["Authorization"][7:]
    return None

def _cfg(app):
    return app.config.get("wazo_survey", {}) or {}

@bp.route("/survey/transfer", methods=["POST"])
def transfer_to_survey():
    """
    Body: { "call_id": "<live caller>", "context": "xivo-extrafeatures", "exten": "8899", "timeout": 15 }
    context/exten/timeout are optional; fall back to plugin config.
    """
    token = _token()
    body = request.get_json(force=True)
    cfg = _cfg(request.app) if hasattr(request, "app") else {}

    context = body.get("context") or cfg.get("survey_context", "xivo-extrafeatures")
    exten   = body.get("exten")   or cfg.get("survey_exten", "8899")
    timeout = int(body.get("timeout") or cfg.get("survey_timeout", 15))

    base = os.environ.get("WAZO_CALLD_URL", "http://127.0.0.1:9486/api/calld/1.0")
    headers = {"X-Auth-Token": token, "Content-Type": "application/json"}
    payload = {
        "transferred": body["call_id"],
        "initiator":   body["call_id"],
        "flow": "blind",
        "context": context,
        "exten": exten,
        "timeout": timeout
    }
    r = requests.post(f"{base}/transfers", headers=headers, json=payload, timeout=10)
    r.raise_for_status()
    return jsonify({"ok": True, "to": {"context": context, "exten": exten}, "transfer": r.json()}), 200

@bp.route("/survey/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True}), 200
