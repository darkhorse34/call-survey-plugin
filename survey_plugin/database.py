"""
Database service layer for the Wazo Call Survey Plugin
"""
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from .models import *

class SurveyDatabase:
    """SQLite-based database service for survey data"""
    
    def __init__(self, db_path: str = "/var/lib/wazo/survey.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Survey Templates
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS survey_templates (
                    template_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    survey_type TEXT NOT NULL,
                    tenant_uuid TEXT,
                    created_by TEXT,
                    version INTEGER DEFAULT 1,
                    is_active BOOLEAN DEFAULT 1,
                    languages TEXT,  -- JSON array
                    prompts TEXT,    -- JSON object
                    questions TEXT,  -- JSON array
                    branching_logic TEXT,  -- JSON object
                    sampling_rules TEXT,   -- JSON object
                    eligibility_filters TEXT,  -- JSON object
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Survey Instances
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS survey_instances (
                    instance_id TEXT PRIMARY KEY,
                    template_id TEXT NOT NULL,
                    tenant_uuid TEXT,
                    name TEXT NOT NULL,
                    trigger_mode TEXT NOT NULL,
                    target_queues TEXT,  -- JSON array
                    target_agents TEXT,  -- JSON array
                    sampling_percentage REAL DEFAULT 100.0,
                    cooldown_hours INTEGER DEFAULT 24,
                    start_date TIMESTAMP,
                    end_date TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES survey_templates(template_id)
                )
            """)
            
            # Survey Responses
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS survey_responses (
                    response_id TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    call_id TEXT,
                    caller_id TEXT,
                    queue_name TEXT,
                    agent_id TEXT,
                    language TEXT DEFAULT 'en',
                    responses TEXT,  -- JSON object
                    voice_comments TEXT,
                    voice_recording_uri TEXT,
                    text_comments TEXT,
                    completion_time INTEGER,
                    status TEXT DEFAULT 'pending',
                    cdr_data TEXT,  -- JSON object
                    metadata TEXT,  -- JSON object
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (instance_id) REFERENCES survey_instances(instance_id)
                )
            """)
            
            # Caller Eligibility
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS caller_eligibility (
                    caller_id TEXT,
                    tenant_uuid TEXT,
                    last_surveyed TIMESTAMP,
                    survey_count INTEGER DEFAULT 0,
                    is_blacklisted BOOLEAN DEFAULT 0,
                    blacklist_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (caller_id, tenant_uuid)
                )
            """)
            
            # Survey Analytics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS survey_analytics (
                    analytics_id TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    tenant_uuid TEXT,
                    period_start TIMESTAMP,
                    period_end TIMESTAMP,
                    total_responses INTEGER DEFAULT 0,
                    completion_rate REAL DEFAULT 0.0,
                    average_score REAL DEFAULT 0.0,
                    nps_score REAL DEFAULT 0.0,
                    csat_score REAL DEFAULT 0.0,
                    ces_score REAL DEFAULT 0.0,
                    detractor_count INTEGER DEFAULT 0,
                    promoter_count INTEGER DEFAULT 0,
                    passive_count INTEGER DEFAULT 0,
                    queue_breakdown TEXT,  -- JSON object
                    agent_breakdown TEXT,  -- JSON object
                    sentiment_analysis TEXT,  -- JSON object
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (instance_id) REFERENCES survey_instances(instance_id)
                )
            """)
            
            # Alert Rules
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_rules (
                    rule_id TEXT PRIMARY KEY,
                    tenant_uuid TEXT,
                    name TEXT NOT NULL,
                    instance_id TEXT,
                    conditions TEXT,  -- JSON object
                    actions TEXT,     -- JSON array
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (instance_id) REFERENCES survey_instances(instance_id)
                )
            """)
            
            # Webhook Events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webhook_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT,  -- JSON object
                    webhook_url TEXT,
                    status TEXT DEFAULT 'pending',
                    response_code INTEGER,
                    response_body TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def create_survey_template(self, template: SurveyTemplate) -> str:
        """Create a new survey template"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO survey_templates 
                (template_id, name, survey_type, tenant_uuid, created_by, version, is_active,
                 languages, prompts, questions, branching_logic, sampling_rules, eligibility_filters)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                template.template_id,
                template.name,
                template.survey_type.value,
                template.tenant_uuid,
                template.created_by,
                template.version,
                template.is_active,
                json.dumps([lang.value for lang in template.languages]),
                json.dumps(template.prompts),
                json.dumps(template.questions),
                json.dumps(template.branching_logic),
                json.dumps(template.sampling_rules),
                json.dumps(template.eligibility_filters)
            ))
            conn.commit()
            return template.template_id
    
    def get_survey_template(self, template_id: str) -> Optional[SurveyTemplate]:
        """Get survey template by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM survey_templates WHERE template_id = ?", (template_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return SurveyTemplate(
                template_id=row[0],
                name=row[1],
                survey_type=SurveyType(row[2]),
                tenant_uuid=row[3],
                created_by=row[4],
                version=row[5],
                is_active=bool(row[6]),
                languages=[Language(lang) for lang in json.loads(row[7] or '["en"]')],
                prompts=json.loads(row[8] or '{}'),
                questions=json.loads(row[9] or '[]'),
                branching_logic=json.loads(row[10] or '{}'),
                sampling_rules=json.loads(row[11] or '{}'),
                eligibility_filters=json.loads(row[12] or '{}'),
                created_at=datetime.fromisoformat(row[13]) if row[13] else None,
                updated_at=datetime.fromisoformat(row[14]) if row[14] else None
            )
    
    def create_survey_instance(self, instance: SurveyInstance) -> str:
        """Create a new survey instance"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO survey_instances 
                (instance_id, template_id, tenant_uuid, name, trigger_mode, target_queues,
                 target_agents, sampling_percentage, cooldown_hours, start_date, end_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                instance.instance_id,
                instance.template_id,
                instance.tenant_uuid,
                instance.name,
                instance.trigger_mode.value,
                json.dumps(instance.target_queues),
                json.dumps(instance.target_agents),
                instance.sampling_percentage,
                instance.cooldown_hours,
                instance.start_date.isoformat() if instance.start_date else None,
                instance.end_date.isoformat() if instance.end_date else None,
                instance.is_active
            ))
            conn.commit()
            return instance.instance_id
    
    def get_active_survey_instances(self, tenant_uuid: str = None) -> List[SurveyInstance]:
        """Get all active survey instances"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM survey_instances WHERE is_active = 1"
            params = []
            
            if tenant_uuid:
                query += " AND tenant_uuid = ?"
                params.append(tenant_uuid)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            instances = []
            for row in rows:
                instances.append(SurveyInstance(
                    instance_id=row[0],
                    template_id=row[1],
                    tenant_uuid=row[2],
                    name=row[3],
                    trigger_mode=TriggerMode(row[4]),
                    target_queues=json.loads(row[5] or '[]'),
                    target_agents=json.loads(row[6] or '[]'),
                    sampling_percentage=row[7],
                    cooldown_hours=row[8],
                    start_date=datetime.fromisoformat(row[9]) if row[9] else None,
                    end_date=datetime.fromisoformat(row[10]) if row[10] else None,
                    is_active=bool(row[11]),
                    created_at=datetime.fromisoformat(row[12]) if row[12] else None,
                    updated_at=datetime.fromisoformat(row[13]) if row[13] else None
                ))
            
            return instances
    
    def create_survey_response(self, response: SurveyResponse) -> str:
        """Create a new survey response"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO survey_responses 
                (response_id, instance_id, call_id, caller_id, queue_name, agent_id,
                 language, responses, voice_comments, voice_recording_uri, text_comments,
                 completion_time, status, cdr_data, metadata, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                response.response_id,
                response.instance_id,
                response.call_id,
                response.caller_id,
                response.queue_name,
                response.agent_id,
                response.language.value,
                json.dumps(response.responses),
                response.voice_comments,
                response.voice_recording_uri,
                response.text_comments,
                response.completion_time,
                response.status.value,
                json.dumps(response.cdr_data),
                json.dumps(response.metadata),
                response.completed_at.isoformat() if response.completed_at else None
            ))
            conn.commit()
            return response.response_id
    
    def update_survey_response(self, response_id: str, updates: Dict[str, Any]) -> bool:
        """Update survey response"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Build dynamic update query
            set_clauses = []
            values = []
            
            for key, value in updates.items():
                if key in ['responses', 'cdr_data', 'metadata']:
                    set_clauses.append(f"{key} = ?")
                    values.append(json.dumps(value))
                elif key == 'completed_at' and value:
                    set_clauses.append(f"{key} = ?")
                    values.append(value.isoformat())
                else:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
            
            if not set_clauses:
                return False
            
            values.append(response_id)
            query = f"UPDATE survey_responses SET {', '.join(set_clauses)} WHERE response_id = ?"
            
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0
    
    def get_caller_eligibility(self, caller_id: str, tenant_uuid: str) -> Optional[CallerEligibility]:
        """Get caller eligibility status"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM caller_eligibility 
                WHERE caller_id = ? AND tenant_uuid = ?
            """, (caller_id, tenant_uuid))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return CallerEligibility(
                caller_id=row[0],
                tenant_uuid=row[1],
                last_surveyed=datetime.fromisoformat(row[2]) if row[2] else None,
                survey_count=row[3],
                is_blacklisted=bool(row[4]),
                blacklist_reason=row[5],
                created_at=datetime.fromisoformat(row[6]) if row[6] else None,
                updated_at=datetime.fromisoformat(row[7]) if row[7] else None
            )
    
    def update_caller_eligibility(self, eligibility: CallerEligibility) -> bool:
        """Update caller eligibility"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO caller_eligibility 
                (caller_id, tenant_uuid, last_surveyed, survey_count, is_blacklisted, 
                 blacklist_reason, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                eligibility.caller_id,
                eligibility.tenant_uuid,
                eligibility.last_surveyed.isoformat() if eligibility.last_surveyed else None,
                eligibility.survey_count,
                eligibility.is_blacklisted,
                eligibility.blacklist_reason,
                eligibility.updated_at.isoformat()
            ))
            conn.commit()
            return True
    
    def get_survey_analytics(self, instance_id: str, period_start: datetime = None, 
                           period_end: datetime = None) -> Optional[SurveyAnalytics]:
        """Get survey analytics for a period"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM survey_analytics WHERE instance_id = ?"
            params = [instance_id]
            
            if period_start:
                query += " AND period_start >= ?"
                params.append(period_start.isoformat())
            
            if period_end:
                query += " AND period_end <= ?"
                params.append(period_end.isoformat())
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return SurveyAnalytics(
                analytics_id=row[0],
                instance_id=row[1],
                tenant_uuid=row[2],
                period_start=datetime.fromisoformat(row[3]) if row[3] else None,
                period_end=datetime.fromisoformat(row[4]) if row[4] else None,
                total_responses=row[5],
                completion_rate=row[6],
                average_score=row[7],
                nps_score=row[8],
                csat_score=row[9],
                ces_score=row[10],
                detractor_count=row[11],
                promoter_count=row[12],
                passive_count=row[13],
                queue_breakdown=json.loads(row[14] or '{}'),
                agent_breakdown=json.loads(row[15] or '{}'),
                sentiment_analysis=json.loads(row[16] or '{}'),
                created_at=datetime.fromisoformat(row[17]) if row[17] else None
            )
    
    def create_webhook_event(self, event: WebhookEvent) -> str:
        """Create webhook event"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO webhook_events 
                (event_id, event_type, payload, webhook_url, status, response_code, 
                 response_body, retry_count, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.event_type,
                json.dumps(event.payload),
                event.webhook_url,
                event.status,
                event.response_code,
                event.response_body,
                event.retry_count,
                event.processed_at.isoformat() if event.processed_at else None
            ))
            conn.commit()
            return event.event_id
