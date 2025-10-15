"""
Business logic services for the Wazo Call Survey Plugin
"""
import hashlib
import hmac
import json
import random
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from .models import *
from .database import SurveyDatabase

class SurveyService:
    """Main service for survey operations"""
    
    def __init__(self, db: SurveyDatabase):
        self.db = db
    
    def create_survey_template(self, template_data: Dict[str, Any]) -> str:
        """Create a new survey template"""
        template = SurveyTemplate(
            name=template_data.get('name', ''),
            survey_type=SurveyType(template_data.get('survey_type', 'csat')),
            tenant_uuid=template_data.get('tenant_uuid'),
            created_by=template_data.get('created_by'),
            languages=[Language(lang) for lang in template_data.get('languages', ['en'])],
            prompts=template_data.get('prompts', {}),
            questions=template_data.get('questions', []),
            branching_logic=template_data.get('branching_logic', {}),
            sampling_rules=template_data.get('sampling_rules', {}),
            eligibility_filters=template_data.get('eligibility_filters', {})
        )
        return self.db.create_survey_template(template)
    
    def create_survey_instance(self, instance_data: Dict[str, Any]) -> str:
        """Create a new survey instance"""
        instance = SurveyInstance(
            template_id=instance_data['template_id'],
            tenant_uuid=instance_data.get('tenant_uuid'),
            name=instance_data.get('name', ''),
            trigger_mode=TriggerMode(instance_data.get('trigger_mode', 'post_call_ivr')),
            target_queues=instance_data.get('target_queues', []),
            target_agents=instance_data.get('target_agents', []),
            sampling_percentage=instance_data.get('sampling_percentage', 100.0),
            cooldown_hours=instance_data.get('cooldown_hours', 24),
            start_date=datetime.fromisoformat(instance_data['start_date']) if instance_data.get('start_date') else None,
            end_date=datetime.fromisoformat(instance_data['end_date']) if instance_data.get('end_date') else None
        )
        return self.db.create_survey_instance(instance)
    
    def is_caller_eligible(self, caller_id: str, tenant_uuid: str, instance_id: str) -> Tuple[bool, str]:
        """Check if caller is eligible for survey"""
        # Get caller eligibility
        eligibility = self.db.get_caller_eligibility(caller_id, tenant_uuid)
        
        if not eligibility:
            return True, "New caller"
        
        # Check blacklist
        if eligibility.is_blacklisted:
            return False, f"Blacklisted: {eligibility.blacklist_reason}"
        
        # Check cooldown period
        if eligibility.last_surveyed:
            cooldown_hours = 24  # Default cooldown
            if eligibility.last_surveyed > datetime.utcnow() - timedelta(hours=cooldown_hours):
                return False, "Still in cooldown period"
        
        # Check survey count limits
        max_surveys = 10  # Default limit
        if eligibility.survey_count >= max_surveys:
            return False, "Maximum survey count reached"
        
        return True, "Eligible"
    
    def should_sample_caller(self, caller_id: str, sampling_percentage: float) -> bool:
        """Determine if caller should be sampled based on percentage"""
        # Use caller ID hash for consistent sampling
        hash_value = int(hashlib.md5(caller_id.encode()).hexdigest(), 16)
        return (hash_value % 100) < sampling_percentage
    
    def process_survey_response(self, response_data: Dict[str, Any]) -> str:
        """Process and store survey response"""
        response = SurveyResponse(
            instance_id=response_data['instance_id'],
            call_id=response_data.get('call_id'),
            caller_id=response_data.get('caller_id'),
            queue_name=response_data.get('queue_name'),
            agent_id=response_data.get('agent_id'),
            language=Language(response_data.get('language', 'en')),
            responses=response_data.get('responses', {}),
            voice_comments=response_data.get('voice_comments'),
            voice_recording_uri=response_data.get('voice_recording_uri'),
            text_comments=response_data.get('text_comments'),
            completion_time=response_data.get('completion_time'),
            status=ResponseStatus(response_data.get('status', 'completed')),
            cdr_data=response_data.get('cdr_data', {}),
            metadata=response_data.get('metadata', {})
        )
        
        if response.status == ResponseStatus.COMPLETED:
            response.completed_at = datetime.utcnow()
        
        response_id = self.db.create_survey_response(response)
        
        # Update caller eligibility
        if response.caller_id:
            eligibility = self.db.get_caller_eligibility(response.caller_id, response_data.get('tenant_uuid', ''))
            if not eligibility:
                eligibility = CallerEligibility(
                    caller_id=response.caller_id,
                    tenant_uuid=response_data.get('tenant_uuid', ''),
                    survey_count=1,
                    last_surveyed=datetime.utcnow()
                )
            else:
                eligibility.survey_count += 1
                eligibility.last_surveyed = datetime.utcnow()
                eligibility.updated_at = datetime.utcnow()
            
            self.db.update_caller_eligibility(eligibility)
        
        return response_id
    
    def get_survey_analytics(self, instance_id: str, period_days: int = 30) -> Dict[str, Any]:
        """Get survey analytics for a period"""
        period_start = datetime.utcnow() - timedelta(days=period_days)
        period_end = datetime.utcnow()
        
        analytics = self.db.get_survey_analytics(instance_id, period_start, period_end)
        
        if not analytics:
            return {
                'total_responses': 0,
                'completion_rate': 0.0,
                'average_score': 0.0,
                'nps_score': 0.0,
                'csat_score': 0.0,
                'ces_score': 0.0,
                'detractor_count': 0,
                'promoter_count': 0,
                'passive_count': 0,
                'queue_breakdown': {},
                'agent_breakdown': {},
                'sentiment_analysis': {}
            }
        
        return {
            'total_responses': analytics.total_responses,
            'completion_rate': analytics.completion_rate,
            'average_score': analytics.average_score,
            'nps_score': analytics.nps_score,
            'csat_score': analytics.csat_score,
            'ces_score': analytics.ces_score,
            'detractor_count': analytics.detractor_count,
            'promoter_count': analytics.promoter_count,
            'passive_count': analytics.passive_count,
            'queue_breakdown': analytics.queue_breakdown,
            'agent_breakdown': analytics.agent_breakdown,
            'sentiment_analysis': analytics.sentiment_analysis
        }

class LanguageDetectionService:
    """Service for automatic language detection"""
    
    @staticmethod
    def detect_language_from_cli(caller_id: str) -> Language:
        """Detect language from caller ID (country code)"""
        # Simple country code to language mapping
        country_mapping = {
            '1': Language.EN,    # US/Canada
            '44': Language.EN,   # UK
            '33': Language.FR,   # France
            '49': Language.DE,   # Germany
            '39': Language.IT,   # Italy
            '34': Language.ES,   # Spain
            '351': Language.PT,  # Portugal
        }
        
        # Extract country code from caller ID
        if caller_id.startswith('+'):
            caller_id = caller_id[1:]
        
        for code, lang in country_mapping.items():
            if caller_id.startswith(code):
                return lang
        
        return Language.EN  # Default to English
    
    @staticmethod
    def detect_language_from_dnis(dnis: str) -> Language:
        """Detect language from DNIS (Dialed Number Identification Service)"""
        # This would typically map specific phone numbers to languages
        # For now, return default
        return Language.EN

class SentimentAnalysisService:
    """Service for sentiment analysis of survey responses"""
    
    def __init__(self):
        try:
            from textblob import TextBlob
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self.textblob = TextBlob
            self.vader = SentimentIntensityAnalyzer()
        except ImportError:
            self.textblob = None
            self.vader = None
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        if not text or not self.textblob or not self.vader:
            return {'sentiment': 'neutral', 'score': 0.0, 'confidence': 0.0}
        
        # TextBlob sentiment
        blob = self.textblob(text)
        polarity = blob.sentiment.polarity
        
        # VADER sentiment
        vader_scores = self.vader.polarity_scores(text)
        
        # Combine results
        combined_score = (polarity + vader_scores['compound']) / 2
        
        if combined_score > 0.1:
            sentiment = 'positive'
        elif combined_score < -0.1:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        return {
            'sentiment': sentiment,
            'score': combined_score,
            'confidence': abs(combined_score),
            'textblob_polarity': polarity,
            'vader_compound': vader_scores['compound'],
            'vader_positive': vader_scores['pos'],
            'vader_negative': vader_scores['neg'],
            'vader_neutral': vader_scores['neu']
        }
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        if not text:
            return []
        
        # Simple keyword extraction (could be enhanced with NLP libraries)
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter out common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
        
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Count frequency and return top keywords
        from collections import Counter
        return [word for word, count in Counter(keywords).most_common(10)]

class WebhookService:
    """Service for webhook management and delivery"""
    
    def __init__(self, db: SurveyDatabase):
        self.db = db
    
    def create_webhook_event(self, event_type: str, payload: Dict[str, Any], 
                           webhook_url: str) -> str:
        """Create a webhook event"""
        event = WebhookEvent(
            event_type=event_type,
            payload=payload,
            webhook_url=webhook_url
        )
        return self.db.create_webhook_event(event)
    
    def sign_webhook_payload(self, payload: Dict[str, Any], secret: str) -> str:
        """Sign webhook payload with HMAC"""
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    def verify_webhook_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Verify webhook signature"""
        expected_signature = self.sign_webhook_payload(json.loads(payload), secret)
        return hmac.compare_digest(signature, expected_signature)

class AlertService:
    """Service for real-time alerts and notifications"""
    
    def __init__(self, db: SurveyDatabase):
        self.db = db
    
    def check_alert_conditions(self, response: SurveyResponse) -> List[Dict[str, Any]]:
        """Check if response triggers any alert conditions"""
        # This would check against alert rules in the database
        # For now, return basic detractor alerts
        alerts = []
        
        if 'score' in response.responses:
            score = response.responses['score']
            
            # NPS detractor alert
            if isinstance(score, (int, float)) and score <= 6:
                alerts.append({
                    'type': 'nps_detractor',
                    'message': f'Low NPS score detected: {score}',
                    'priority': 'high',
                    'response_id': response.response_id,
                    'caller_id': response.caller_id,
                    'agent_id': response.agent_id
                })
            
            # CSAT detractor alert
            if isinstance(score, (int, float)) and score <= 2:
                alerts.append({
                    'type': 'csat_detractor',
                    'message': f'Low CSAT score detected: {score}',
                    'priority': 'high',
                    'response_id': response.response_id,
                    'caller_id': response.caller_id,
                    'agent_id': response.agent_id
                })
        
        # Check for profanity or complaint keywords
        if response.text_comments:
            complaint_keywords = ['terrible', 'awful', 'horrible', 'worst', 'hate', 'angry', 'frustrated']
            if any(keyword in response.text_comments.lower() for keyword in complaint_keywords):
                alerts.append({
                    'type': 'complaint_detected',
                    'message': 'Complaint keywords detected in comments',
                    'priority': 'medium',
                    'response_id': response.response_id,
                    'caller_id': response.caller_id,
                    'agent_id': response.agent_id
                })
        
        return alerts
    
    def send_alert(self, alert: Dict[str, Any], notification_channels: List[str]) -> bool:
        """Send alert to notification channels"""
        # This would integrate with Slack, email, etc.
        # For now, just log the alert
        print(f"ALERT: {alert['type']} - {alert['message']}")
        return True
