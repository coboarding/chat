"""
Notification service for handling multi-channel notifications.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

class NotificationService:
    """Multi-channel notification service for instant communication"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.notification_channels = {
            'slack': SlackNotifier(),
            'email': EmailNotifier(),
            'teams': TeamsNotifier(),
            'whatsapp': WhatsAppNotifier()
        }
        self.logger = logging.getLogger(__name__)

    async def notify_employer(self, company: Dict, cv_data: Dict, message: str) -> Dict:
        """Send instant notification to employer about new candidate"""
        notification_data = {
            'type': 'new_candidate',
            'company': company,
            'candidate': cv_data,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'match_score': await self._calculate_match_score(cv_data, company)
        }

        results = {'success': False, 'channels': []}

        # Try each configured channel
        for channel_name, channel in self.notification_channels.items():
            if await channel.is_configured(company):
                try:
                    result = await channel.send_notification(notification_data)
                    results['channels'].append({
                        'channel': channel_name,
                        'status': 'success' if result.get('success') else 'failed',
                        'message': result.get('message', '')
                    })
                    results['success'] = results['success'] or result.get('success', False)
                except Exception as e:
                    self.logger.error(f"Error sending {channel_name} notification: {str(e)}")
                    results['channels'].append({
                        'channel': channel_name,
                        'status': 'error',
                        'message': str(e)
                    })

        # Store notification in Redis
        await self._store_notification(notification_data, results)
        return results

    async def notify_candidate(self, cv_data: Dict, company: Dict, message: str) -> Dict:
        """Send notification to candidate about employer response"""
        notification_data = {
            'type': 'employer_response',
            'company': company,
            'candidate': cv_data,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Implementation would be similar to notify_employer
        # but targeting candidate's preferred notification channels
        return {'success': True, 'message': 'Notification sent to candidate'}

    async def _calculate_match_score(self, cv_data: Dict, company: Dict) -> float:
        """Calculate match score between candidate and company"""
        if not cv_data.get('skills') or not company.get('required_skills'):
            return 0.0
            
        required_skills = set(skill.lower() for skill in company.get('required_skills', []))
        candidate_skills = set(skill.lower() for skill in cv_data.get('skills', []))
        
        if not required_skills:
            return 0.0
            
        matching_skills = required_skills.intersection(candidate_skills)
        return len(matching_skills) / len(required_skills)

    async def _store_notification(self, notification_data: Dict, results: Dict):
        """Store notification in Redis with TTL"""
        try:
            # Implementation would connect to Redis and store the notification
            # with an appropriate TTL (e.g., 30 days)
            pass
        except Exception as e:
            self.logger.error(f"Error storing notification: {str(e)}")

    async def get_recent_notifications(self, session_id: str) -> List[Dict]:
        """Get recent notifications for a session"""
        try:
            # Implementation would retrieve notifications from Redis
            # based on the session_id
            return []
        except Exception as e:
            self.logger.error(f"Error retrieving notifications: {str(e)}")
            return []


class SlackNotifier:
    """Slack notification implementation"""
    
    async def is_configured(self, company: Dict) -> bool:
        """Check if Slack is configured for this company"""
        return bool(company.get('slack_webhook_url'))
    
    async def send_notification(self, notification_data: Dict) -> Dict:
        """Send Slack notification"""
        # Implementation would send a message to Slack webhook
        return {'success': True, 'message': 'Slack notification sent'}


class EmailNotifier:
    """Email notification implementation"""
    
    async def is_configured(self, company: Dict) -> bool:
        """Check if email is configured"""
        return company.get('notification_email') is not None
    
    async def send_notification(self, notification_data: Dict) -> Dict:
        """Send email notification"""
        # Implementation would send an email
        return {'success': True, 'message': 'Email notification sent'}


class TeamsNotifier:
    """Microsoft Teams notification implementation"""
    
    async def is_configured(self, company: Dict) -> bool:
        """Check if Teams is configured"""
        return bool(company.get('teams_webhook_url'))
    
    async def send_notification(self, notification_data: Dict) -> Dict:
        """Send Teams notification"""
        # Implementation would send a card to Teams webhook
        return {'success': True, 'message': 'Teams notification sent'}


class WhatsAppNotifier:
    """WhatsApp notification implementation"""
    
    async def is_configured(self, company: Dict) -> bool:
        """Check if WhatsApp is configured"""
        return bool(company.get('whatsapp_number'))
    
    async def send_notification(self, notification_data: Dict) -> Dict:
        """Send WhatsApp notification"""
        # Implementation would use a WhatsApp API to send a message
        return {'success': True, 'message': 'WhatsApp notification sent'}
