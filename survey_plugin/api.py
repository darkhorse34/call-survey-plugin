import os
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import requests
from .database import SurveyDatabase
from .services import SurveyService, LanguageDetectionService, SentimentAnalysisService, WebhookService, AlertService
from .models import *

bp = Blueprint("wazo_survey", __name__)

# Initialize services
db = SurveyDatabase()
survey_service = SurveyService(db)
language_service = LanguageDetectionService()
sentiment_service = SentimentAnalysisService()
webhook_service = WebhookService(db)
alert_service = AlertService(db)

def _token():
    h = request.headers
    if "X-Auth-Token" in h: return h["X-Auth-Token"]
    if h.get("Authorization","").startswith("Bearer "):
        return h["Authorization"][7:]
    return None

def _cfg(app):
    return app.config.get("wazo_survey", {}) or {}

def _get_tenant_uuid():
    """Extract tenant UUID from JWT token or request"""
    try:
        jwt_data = get_jwt()
        return jwt_data.get('tenant_uuid')
    except:
        return request.headers.get('X-Tenant-UUID')

# ============================================================================
# SURVEY TEMPLATES API
# ============================================================================

@bp.route("/survey/templates", methods=["POST"])
@jwt_required()
def create_survey_template():
    """Create a new survey template"""
    try:
        data = request.get_json()
        data['tenant_uuid'] = _get_tenant_uuid()
        data['created_by'] = get_jwt_identity()
        
        template_id = survey_service.create_survey_template(data)
        return jsonify({"ok": True, "template_id": template_id}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@bp.route("/survey/templates/<template_id>", methods=["GET"])
@jwt_required()
def get_survey_template(template_id):
    """Get survey template by ID"""
    template = db.get_survey_template(template_id)
    if not template:
        return jsonify({"ok": False, "error": "Template not found"}), 404
    
    return jsonify({
        "ok": True,
        "template": {
            "template_id": template.template_id,
            "name": template.name,
            "survey_type": template.survey_type.value,
            "version": template.version,
            "is_active": template.is_active,
            "languages": [lang.value for lang in template.languages],
            "prompts": template.prompts,
            "questions": template.questions,
            "branching_logic": template.branching_logic,
            "sampling_rules": template.sampling_rules,
            "eligibility_filters": template.eligibility_filters,
            "created_at": template.created_at.isoformat(),
            "updated_at": template.updated_at.isoformat()
        }
    }), 200

@bp.route("/survey/templates", methods=["GET"])
@jwt_required()
def list_survey_templates():
    """List all survey templates for tenant"""
    # This would implement pagination and filtering
    return jsonify({"ok": True, "templates": []}), 200

# ============================================================================
# SURVEY INSTANCES API
# ============================================================================

@bp.route("/survey/instances", methods=["POST"])
@jwt_required()
def create_survey_instance():
    """Create a new survey instance"""
    try:
        data = request.get_json()
        data['tenant_uuid'] = _get_tenant_uuid()
        
        instance_id = survey_service.create_survey_instance(data)
        return jsonify({"ok": True, "instance_id": instance_id}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@bp.route("/survey/instances/<instance_id>", methods=["GET"])
@jwt_required()
def get_survey_instance(instance_id):
    """Get survey instance by ID"""
    instances = db.get_active_survey_instances(_get_tenant_uuid())
    instance = next((i for i in instances if i.instance_id == instance_id), None)
    
    if not instance:
        return jsonify({"ok": False, "error": "Instance not found"}), 404
    
    return jsonify({
        "ok": True,
        "instance": {
            "instance_id": instance.instance_id,
            "template_id": instance.template_id,
            "name": instance.name,
            "trigger_mode": instance.trigger_mode.value,
            "target_queues": instance.target_queues,
            "target_agents": instance.target_agents,
            "sampling_percentage": instance.sampling_percentage,
            "cooldown_hours": instance.cooldown_hours,
            "start_date": instance.start_date.isoformat() if instance.start_date else None,
            "end_date": instance.end_date.isoformat() if instance.end_date else None,
            "is_active": instance.is_active,
            "created_at": instance.created_at.isoformat(),
            "updated_at": instance.updated_at.isoformat()
        }
    }), 200

@bp.route("/survey/instances", methods=["GET"])
@jwt_required()
def list_survey_instances():
    """List all survey instances for tenant"""
    instances = db.get_active_survey_instances(_get_tenant_uuid())
    
    return jsonify({
        "ok": True,
        "instances": [{
            "instance_id": i.instance_id,
            "template_id": i.template_id,
            "name": i.name,
            "trigger_mode": i.trigger_mode.value,
            "is_active": i.is_active,
            "created_at": i.created_at.isoformat()
        } for i in instances]
    }), 200

# ============================================================================
# SURVEY RESPONSES API
# ============================================================================

@bp.route("/survey/responses", methods=["POST"])
def create_survey_response():
    """Create a new survey response"""
    try:
        data = request.get_json()
        data['tenant_uuid'] = _get_tenant_uuid()
        
        response_id = survey_service.process_survey_response(data)
        return jsonify({"ok": True, "response_id": response_id}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@bp.route("/survey/responses/<response_id>", methods=["GET"])
@jwt_required()
def get_survey_response(response_id):
    """Get survey response by ID"""
    # This would implement response retrieval
    return jsonify({"ok": True, "response": {}}), 200

# ============================================================================
# ANALYTICS API
# ============================================================================

@bp.route("/survey/analytics/<instance_id>", methods=["GET"])
@jwt_required()
def get_survey_analytics(instance_id):
    """Get survey analytics for instance"""
    try:
        period_days = int(request.args.get('period_days', 30))
        analytics = survey_service.get_survey_analytics(instance_id, period_days)
        return jsonify({"ok": True, "analytics": analytics}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@bp.route("/survey/analytics/<instance_id>/export", methods=["GET"])
@jwt_required()
def export_survey_analytics(instance_id):
    """Export survey analytics as CSV/JSON"""
    format_type = request.args.get('format', 'json')
    period_days = int(request.args.get('period_days', 30))
    
    analytics = survey_service.get_survey_analytics(instance_id, period_days)
    
    if format_type == 'csv':
        # Convert to CSV format
        return jsonify({"ok": True, "data": analytics, "format": "csv"}), 200
    else:
        return jsonify({"ok": True, "data": analytics, "format": "json"}), 200

# ============================================================================
# ELIGIBILITY API
# ============================================================================

@bp.route("/survey/eligibility/check", methods=["POST"])
def check_caller_eligibility():
    """Check if caller is eligible for survey"""
    try:
        data = request.get_json()
        caller_id = data.get('caller_id')
        tenant_uuid = _get_tenant_uuid()
        instance_id = data.get('instance_id')
        
        if not caller_id or not instance_id:
            return jsonify({"ok": False, "error": "Missing required fields"}), 400
        
        eligible, reason = survey_service.is_caller_eligible(caller_id, tenant_uuid, instance_id)
        
        return jsonify({
            "ok": True,
            "eligible": eligible,
            "reason": reason
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@bp.route("/survey/eligibility/sample", methods=["POST"])
def check_sampling_eligibility():
    """Check if caller should be sampled"""
    try:
        data = request.get_json()
        caller_id = data.get('caller_id')
        sampling_percentage = float(data.get('sampling_percentage', 100.0))
        
        if not caller_id:
            return jsonify({"ok": False, "error": "Missing caller_id"}), 400
        
        should_sample = survey_service.should_sample_caller(caller_id, sampling_percentage)
        
        return jsonify({
            "ok": True,
            "should_sample": should_sample
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

# ============================================================================
# LANGUAGE DETECTION API
# ============================================================================

@bp.route("/survey/language/detect", methods=["POST"])
def detect_language():
    """Detect language from caller ID or DNIS"""
    try:
        data = request.get_json()
        caller_id = data.get('caller_id')
        dnis = data.get('dnis')
        
        language = Language.EN  # Default
        
        if caller_id:
            language = language_service.detect_language_from_cli(caller_id)
        elif dnis:
            language = language_service.detect_language_from_dnis(dnis)
        
        return jsonify({
            "ok": True,
            "language": language.value
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

# ============================================================================
# SENTIMENT ANALYSIS API
# ============================================================================

@bp.route("/survey/sentiment/analyze", methods=["POST"])
def analyze_sentiment():
    """Analyze sentiment of text comments"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({"ok": False, "error": "No text provided"}), 400
        
        sentiment_data = sentiment_service.analyze_sentiment(text)
        keywords = sentiment_service.extract_keywords(text)
        
        return jsonify({
            "ok": True,
            "sentiment": sentiment_data,
            "keywords": keywords
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

# ============================================================================
# WEBHOOK API
# ============================================================================

@bp.route("/survey/webhooks/events", methods=["POST"])
def create_webhook_event():
    """Create webhook event"""
    try:
        data = request.get_json()
        event_type = data.get('event_type')
        payload = data.get('payload', {})
        webhook_url = data.get('webhook_url')
        
        if not event_type or not webhook_url:
            return jsonify({"ok": False, "error": "Missing required fields"}), 400
        
        event_id = webhook_service.create_webhook_event(event_type, payload, webhook_url)
        
        return jsonify({
            "ok": True,
            "event_id": event_id
        }), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@bp.route("/survey/webhooks/verify", methods=["POST"])
def verify_webhook_signature():
    """Verify webhook signature"""
    try:
        data = request.get_json()
        payload = data.get('payload')
        signature = data.get('signature')
        secret = data.get('secret')
        
        if not all([payload, signature, secret]):
            return jsonify({"ok": False, "error": "Missing required fields"}), 400
        
        is_valid = webhook_service.verify_webhook_signature(payload, signature, secret)
        
        return jsonify({
            "ok": True,
            "valid": is_valid
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

# ============================================================================
# ALERTS API
# ============================================================================

@bp.route("/survey/alerts/check", methods=["POST"])
def check_alert_conditions():
    """Check if response triggers alert conditions"""
    try:
        data = request.get_json()
        response_data = data.get('response', {})
        
        # Create response object for checking
        response = SurveyResponse(
            instance_id=response_data.get('instance_id'),
            call_id=response_data.get('call_id'),
            caller_id=response_data.get('caller_id'),
            queue_name=response_data.get('queue_name'),
            agent_id=response_data.get('agent_id'),
            responses=response_data.get('responses', {}),
            text_comments=response_data.get('text_comments')
        )
        
        alerts = alert_service.check_alert_conditions(response)
        
        return jsonify({
            "ok": True,
            "alerts": alerts
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

# ============================================================================
# LEGACY API (for backward compatibility)
# ============================================================================

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

    # Process through new service
    try:
        body['tenant_uuid'] = _get_tenant_uuid()
        response_id = survey_service.process_survey_response(body)
        
        # Check for alerts
        response = SurveyResponse(
            instance_id=body.get('instance_id'),
            call_id=body.get('call_id'),
            caller_id=body.get('caller_id'),
            responses=body.get('responses', {}),
            text_comments=body.get('text_comments')
        )
        alerts = alert_service.check_alert_conditions(response)
        
        # Send alerts
        for alert in alerts:
            alert_service.send_alert(alert, ['log'])
        
        return jsonify({"ok": True, "response_id": response_id, "alerts": len(alerts)}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

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
    
    # Use new webhook service
    try:
        webhook_url = cfg.get("webhook_url")
        if not webhook_url:
            return jsonify({"ok": False, "error": "No webhook URL configured"}), 400
        
        event_id = webhook_service.create_webhook_event("test", test_payload, webhook_url)
        return jsonify({"ok": True, "event_id": event_id}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
