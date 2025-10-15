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


def _forward_webhook(app, payload):
    cfg = _cfg(app)
    webhook = cfg.get("webhook_url")
    if not webhook:
        return None
    headers = {"Content-Type": "application/json"}
    secret = cfg.get("webhook_secret")
    if secret:
        headers["X-Survey-Secret"] = secret
    try:
        r = requests.post(webhook, json=payload, headers=headers, timeout=5)
        r.raise_for_status()
        return r.json() if r.headers.get("Content-Type",""
                                     ).startswith("application/json") else {"status": r.status_code}
    except Exception as exc:
        # don't fail the entire request if webhook is unavailable
        return {"error": str(exc)}


@bp.route("/survey/response", methods=["POST"])
def survey_response():
    """
    Accept survey responses from external callers (or dialplan). Body should be JSON, examples:
    { "call_id": "<id>", "survey": "nps", "score": 9, "comments": "..." }
    Will store nothing locally but will forward to configured webhook if present.
    """
    body = request.get_json(force=True)
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "invalid json body"}), 400

    # add server-side metadata
    meta = {
        "received_at": request.date if hasattr(request, "date") else None,
        "remote_addr": request.remote_addr,
    }
    payload = {"payload": body, "meta": meta}
    forwarded = _forward_webhook(request.app if hasattr(request, "app") else None, payload)
    return jsonify({"ok": True, "forwarded": forwarded}), 200


@bp.route("/survey/config", methods=["GET"])
def survey_config():
    """Return non-sensitive survey config for debugging (does not include webhook_secret)."""
    cfg = _cfg(request.app) if hasattr(request, "app") else {}
    safe = {k: v for k, v in cfg.items() if k != "webhook_secret"}
    return jsonify({"ok": True, "config": safe}), 200


@bp.route("/survey/webhook/test", methods=["POST"])
def webhook_test():
    """Trigger a test payload to the configured webhook (useful for setup).
    Returns the webhook response or error.
    """
    cfg = _cfg(request.app) if hasattr(request, "app") else {}
    test_payload = request.get_json(force=True) if request.data else {"test": True}
    result = _forward_webhook(request.app if hasattr(request, "app") else None, {"test": test_payload})
    return jsonify({"ok": True, "result": result}), 200
