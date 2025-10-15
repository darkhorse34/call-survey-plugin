"""
Database models for the Wazo Call Survey Plugin
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
import json
import uuid

class SurveyType(Enum):
    CSAT = "csat"  # 1-5 scale
    NPS = "nps"    # 0-10 scale
    CES = "ces"    # Customer Effort Score
    YES_NO = "yes_no"  # Binary compliance
    CUSTOM = "custom"  # Custom scale

class TriggerMode(Enum):
    POST_CALL_IVR = "post_call_ivr"
    IN_QUEUE_INTERCEPT = "in_queue_intercept"
    OUT_OF_BAND_SMS = "out_of_band_sms"
    OUT_OF_BAND_EMAIL = "out_of_band_email"

class Language(Enum):
    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"
    IT = "it"
    PT = "pt"

class ResponseStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"

class SurveyTemplate:
    """Survey template with branching logic and multi-language support"""
    
    def __init__(self, 
                 template_id: str = None,
                 name: str = "",
                 survey_type: SurveyType = SurveyType.CSAT,
                 tenant_uuid: str = None,
                 created_by: str = None,
                 version: int = 1,
                 is_active: bool = True,
                 languages: List[Language] = None,
                 prompts: Dict[str, Dict[str, str]] = None,  # {language: {step: prompt}}
                 questions: List[Dict] = None,
                 branching_logic: Dict = None,
                 sampling_rules: Dict = None,
                 eligibility_filters: Dict = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        
        self.template_id = template_id or str(uuid.uuid4())
        self.name = name
        self.survey_type = survey_type
        self.tenant_uuid = tenant_uuid
        self.created_by = created_by
        self.version = version
        self.is_active = is_active
        self.languages = languages or [Language.EN]
        self.prompts = prompts or {}
        self.questions = questions or []
        self.branching_logic = branching_logic or {}
        self.sampling_rules = sampling_rules or {}
        self.eligibility_filters = eligibility_filters or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

class SurveyInstance:
    """Active survey instance with targeting and scheduling"""
    
    def __init__(self,
                 instance_id: str = None,
                 template_id: str = None,
                 tenant_uuid: str = None,
                 name: str = "",
                 trigger_mode: TriggerMode = TriggerMode.POST_CALL_IVR,
                 target_queues: List[str] = None,
                 target_agents: List[str] = None,
                 sampling_percentage: float = 100.0,
                 cooldown_hours: int = 24,
                 start_date: datetime = None,
                 end_date: datetime = None,
                 is_active: bool = True,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        
        self.instance_id = instance_id or str(uuid.uuid4())
        self.template_id = template_id
        self.tenant_uuid = tenant_uuid
        self.name = name
        self.trigger_mode = trigger_mode
        self.target_queues = target_queues or []
        self.target_agents = target_agents or []
        self.sampling_percentage = sampling_percentage
        self.cooldown_hours = cooldown_hours
        self.start_date = start_date or datetime.utcnow()
        self.end_date = end_date
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

class SurveyResponse:
    """Individual survey response with metadata and CDR linkage"""
    
    def __init__(self,
                 response_id: str = None,
                 instance_id: str = None,
                 call_id: str = None,
                 caller_id: str = None,
                 queue_name: str = None,
                 agent_id: str = None,
                 language: Language = Language.EN,
                 responses: Dict[str, Any] = None,
                 voice_comments: str = None,
                 voice_recording_uri: str = None,
                 text_comments: str = None,
                 completion_time: int = None,  # seconds
                 status: ResponseStatus = ResponseStatus.PENDING,
                 cdr_data: Dict = None,
                 metadata: Dict = None,
                 created_at: datetime = None,
                 completed_at: datetime = None):
        
        self.response_id = response_id or str(uuid.uuid4())
        self.instance_id = instance_id
        self.call_id = call_id
        self.caller_id = caller_id
        self.queue_name = queue_name
        self.agent_id = agent_id
        self.language = language
        self.responses = responses or {}
        self.voice_comments = voice_comments
        self.voice_recording_uri = voice_recording_uri
        self.text_comments = text_comments
        self.completion_time = completion_time
        self.status = status
        self.cdr_data = cdr_data or {}
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.completed_at = completed_at

class CallerEligibility:
    """Track caller eligibility and cooldown periods"""
    
    def __init__(self,
                 caller_id: str = None,
                 tenant_uuid: str = None,
                 last_surveyed: datetime = None,
                 survey_count: int = 0,
                 is_blacklisted: bool = False,
                 blacklist_reason: str = None,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        
        self.caller_id = caller_id
        self.tenant_uuid = tenant_uuid
        self.last_surveyed = last_surveyed
        self.survey_count = survey_count
        self.is_blacklisted = is_blacklisted
        self.blacklist_reason = blacklist_reason
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

class SurveyAnalytics:
    """Analytics data for surveys"""
    
    def __init__(self,
                 analytics_id: str = None,
                 instance_id: str = None,
                 tenant_uuid: str = None,
                 period_start: datetime = None,
                 period_end: datetime = None,
                 total_responses: int = 0,
                 completion_rate: float = 0.0,
                 average_score: float = 0.0,
                 nps_score: float = 0.0,
                 csat_score: float = 0.0,
                 ces_score: float = 0.0,
                 detractor_count: int = 0,
                 promoter_count: int = 0,
                 passive_count: int = 0,
                 queue_breakdown: Dict = None,
                 agent_breakdown: Dict = None,
                 sentiment_analysis: Dict = None,
                 created_at: datetime = None):
        
        self.analytics_id = analytics_id or str(uuid.uuid4())
        self.instance_id = instance_id
        self.tenant_uuid = tenant_uuid
        self.period_start = period_start
        self.period_end = period_end
        self.total_responses = total_responses
        self.completion_rate = completion_rate
        self.average_score = average_score
        self.nps_score = nps_score
        self.csat_score = csat_score
        self.ces_score = ces_score
        self.detractor_count = detractor_count
        self.promoter_count = promoter_count
        self.passive_count = passive_count
        self.queue_breakdown = queue_breakdown or {}
        self.agent_breakdown = agent_breakdown or {}
        self.sentiment_analysis = sentiment_analysis or {}
        self.created_at = created_at or datetime.utcnow()

class AlertRule:
    """Real-time alert rules for survey responses"""
    
    def __init__(self,
                 rule_id: str = None,
                 tenant_uuid: str = None,
                 name: str = "",
                 instance_id: str = None,
                 conditions: Dict = None,
                 actions: List[Dict] = None,
                 is_active: bool = True,
                 created_at: datetime = None,
                 updated_at: datetime = None):
        
        self.rule_id = rule_id or str(uuid.uuid4())
        self.tenant_uuid = tenant_uuid
        self.name = name
        self.instance_id = instance_id
        self.conditions = conditions or {}
        self.actions = actions or []
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

class WebhookEvent:
    """Webhook event tracking"""
    
    def __init__(self,
                 event_id: str = None,
                 event_type: str = None,
                 payload: Dict = None,
                 webhook_url: str = None,
                 status: str = "pending",
                 response_code: int = None,
                 response_body: str = None,
                 retry_count: int = 0,
                 created_at: datetime = None,
                 processed_at: datetime = None):
        
        self.event_id = event_id or str(uuid.uuid4())
        self.event_type = event_type
        self.payload = payload or {}
        self.webhook_url = webhook_url
        self.status = status
        self.response_code = response_code
        self.response_body = response_body
        self.retry_count = retry_count
        self.created_at = created_at or datetime.utcnow()
        self.processed_at = processed_at
