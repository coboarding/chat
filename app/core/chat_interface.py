# core/chat_interface.py
import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import ollama
import aioredis
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import os


class ChatInterface:
    """AI-powered chat interface for candidate-employer communication"""

    def __init__(self, ollama_url: str = "http://localhost:11434", redis_url: str = "redis://localhost:6379"):
        self.ollama_client = ollama.Client(host=ollama_url)
        self.redis_url = redis_url
        self.conversation_cache = {}

    async def process_message(self, message: str, cv_data: Dict, company: Dict) -> str:
        """Process chat message with context awareness"""
        # Generate conversation context
        context = await self._build_conversation_context(cv_data, company)

        # Generate AI response
        response = await self._generate_ai_response(message, context, cv_data, company)

        # Store conversation in cache
        await self._store_conversation(cv_data, company, message, response)

        return response

    async def _build_conversation_context(self, cv_data: Dict, company: Dict) -> str:
        """Build conversation context for AI"""
        context = f"""
        You are an AI assistant helping facilitate communication between a job candidate and an employer.

        CANDIDATE PROFILE:
        - Name: {cv_data.get('name', 'Unknown')}
        - Title: {cv_data.get('title', 'Unknown')}
        - Experience: {cv_data.get('experience_years', 0)} years
        - Skills: {', '.join(cv_data.get('skills', []))}
        - Location: {cv_data.get('location', 'Unknown')}

        COMPANY & POSITION:
        - Company: {company.get('company', 'Unknown')}
        - Position: {company.get('position', 'Unknown')}
        - Requirements: {', '.join(company.get('requirements', []))}
        - Location: {company.get('location', 'Unknown')}
        - Remote: {company.get('remote', False)}

        CONTEXT:
        - This is a speed hiring platform focused on quick decision making (24h response time)
        - Be professional but efficient and direct
        - Focus on relevant experience and skills matching
        - Help facilitate quick hiring decisions
        - If asked about availability, mention the candidate expects a response within 24h
        """

        return context

    async def _generate_ai_response(self, message: str, context: str, cv_data: Dict, company: Dict) -> str:
        """Generate AI response using local LLM"""
        prompt = f"""
        {context}

        Candidate message: "{message}"

        Generate a professional response that:
        1. Addresses the candidate's message appropriately
        2. Provides relevant information about the match
        3. Maintains professional tone
        4. Encourages next steps if appropriate
        5. Keeps response concise (2-3 sentences max)

        Response:
        """

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.ollama_client.generate(
                    model='mistral:7b-instruct',
                    prompt=prompt,
                    options={
                        'temperature': 0.3,
                        'num_predict': 200
                    }
                )
            )

            return response['response'].strip()

        except Exception as e:
            print(f"AI response generation error: {e}")
            return "Thank you for your message. We'll review your application and get back to you within 24 hours."

    async def _store_conversation(self, cv_data: Dict, company: Dict, message: str, response: str):
        """Store conversation in Redis with TTL"""
        try:
            redis = aioredis.from_url(self.redis_url)

            conversation_key = f"conversation:{cv_data.get('email', 'unknown')}:{company.get('id', 'unknown')}"

            conversation_data = {
                'timestamp': datetime.now().isoformat(),
                'candidate_message': message,
                'ai_response': response,
                'cv_data': cv_data,
                'company': company
            }

            # Store with 24h TTL (GDPR compliance)
            await redis.setex(
                conversation_key,
                86400,  # 24 hours
                json.dumps(conversation_data)
            )

            await redis.close()

        except Exception as e:
            print(f"Conversation storage error: {e}")

    async def generate_technical_questions(self, cv_data: Dict, company: Dict) -> List[Dict]:
        """Generate technical validation questions to prevent spam"""
        requirements = company.get('requirements', [])
        candidate_skills = cv_data.get('skills', [])

        # Find overlapping skills for targeted questions
        overlap_skills = [skill for skill in requirements if skill in candidate_skills]

        if not overlap_skills:
            overlap_skills = requirements[:3]  # Use first 3 requirements

        prompt = f"""
        Generate 3 technical validation questions for a candidate applying to:
        Position: {company.get('position', 'Software Developer')}
        Company: {company.get('company', 'Tech Company')}
        Requirements: {', '.join(requirements)}

        Candidate claims experience in: {', '.join(candidate_skills)}

        Create questions that:
        1. Test real understanding (not googleable)
        2. Are specific to the mentioned technologies
        3. Require practical experience to answer correctly
        4. Are tricky enough to prevent AI assistance
        5. Can be answered in 2-3 sentences

        Focus on: {', '.join(overlap_skills[:2])}

        Return as JSON array:
        [
            {{
                "question": "Specific technical question",
                "topic": "Technology/skill being tested",
                "difficulty": "medium/hard",
                "expected_answer_length": "2-3 sentences"
            }}
        ]
        """

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.ollama_client.generate(
                    model='mistral:7b-instruct',
                    prompt=prompt,
                    options={
                        'temperature': 0.4,
                        'format': 'json'
                    }
                )
            )

            # Parse JSON response
            questions_json = response['response'].strip()
            questions = json.loads(questions_json)

            return questions if isinstance(questions, list) else []

        except Exception as e:
            print(f"Question generation error: {e}")
            return self._get_fallback_questions(overlap_skills)

    def _get_fallback_questions(self, skills: List[str]) -> List[Dict]:
        """Fallback technical questions"""
        fallback_questions = [
            {
                "question": "Describe a challenging technical problem you solved recently and your approach.",
                "topic": "Problem Solving",
                "difficulty": "medium",
                "expected_answer_length": "3-4 sentences"
            },
            {
                "question": "What's the difference between synchronous and asynchronous programming, and when would you use each?",
                "topic": "Programming Concepts",
                "difficulty": "medium",
                "expected_answer_length": "2-3 sentences"
            },
            {
                "question": "How do you handle error handling and logging in production applications?",
                "topic": "Production Systems",
                "difficulty": "medium",
                "expected_answer_length": "2-3 sentences"
            }
        ]

        return fallback_questions[:2]  # Return 2 questions


# core/notification_service.py
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

    async def notify_employer(self, company: Dict, cv_data: Dict, message: str) -> Dict:
        """Send instant notification to employer about new candidate"""
        notification_data = {
            'type': 'new_candidate',
            'candidate': {
                'name': cv_data.get('name', 'Unknown'),
                'title': cv_data.get('title', 'Unknown'),
                'experience': cv_data.get('experience_years', 0),
                'skills': cv_data.get('skills', []),
                'email': cv_data.get('email', 'Unknown'),
                'message': message
            },
            'company': company,
            'timestamp': datetime.now().isoformat(),
            'urgency': 'high',  # 24h response expected
            'match_score': self._calculate_match_score(cv_data, company)
        }

        # Send notifications through all configured channels
        results = {}
        for channel_name, notifier in self.notification_channels.items():
            try:
                if await notifier.is_configured(company):
                    result = await notifier.send_notification(notification_data)
                    results[channel_name] = result
            except Exception as e:
                results[channel_name] = {'success': False, 'error': str(e)}

        # Store notification in Redis
        await self._store_notification(notification_data, results)

        return results

    async def notify_candidate(self, cv_data: Dict, company: Dict, message: str) -> Dict:
        """Send notification to candidate about employer response"""
        notification_data = {
            'type': 'employer_response',
            'candidate_email': cv_data.get('email'),
            'company': company.get('company'),
            'position': company.get('position'),
            'message': message,
            'timestamp': datetime.now().isoformat()
        }

        # For now, just email notification to candidate
        try:
            email_notifier = self.notification_channels['email']
            result = await email_notifier.send_candidate_notification(notification_data)
            return {'email': result}
        except Exception as e:
            return {'email': {'success': False, 'error': str(e)}}

    def _calculate_match_score(self, cv_data: Dict, company: Dict) -> float:
        """Calculate match score between candidate and company"""
        candidate_skills = set(skill.lower() for skill in cv_data.get('skills', []))
        required_skills = set(req.lower() for req in company.get('requirements', []))

        if not required_skills:
            return 0.5  # Default match if no requirements specified

        overlap = len(candidate_skills.intersection(required_skills))
        score = overlap / len(required_skills)

        # Boost score for experience level
        experience = cv_data.get('experience_years', 0)
        if experience >= 5:
            score += 0.1
        elif experience >= 2:
            score += 0.05

        return min(score, 1.0)

    async def _store_notification(self, notification_data: Dict, results: Dict):
        """Store notification in Redis with TTL"""
        try:
            redis = aioredis.from_url(self.redis_url)

            notification_key = f"notification:{notification_data['candidate']['email']}:{datetime.now().timestamp()}"

            storage_data = {
                **notification_data,
                'delivery_results': results
            }

            # Store with 24h TTL
            await redis.setex(
                notification_key,
                86400,
                json.dumps(storage_data)
            )

            await redis.close()

        except Exception as e:
            print(f"Notification storage error: {e}")

    async def get_recent_notifications(self, session_id: str) -> List[Dict]:
        """Get recent notifications for a session"""
        try:
            redis = aioredis.from_url(self.redis_url)

            # Search for notifications related to this session
            keys = await redis.keys(f"notification:*")
            notifications = []

            for key in keys[-10:]:  # Get last 10
                data = await redis.get(key)
                if data:
                    notification = json.loads(data)
                    notifications.append(notification)

            await redis.close()
            return notifications

        except Exception as e:
            print(f"Notification retrieval error: {e}")
            return []


class SlackNotifier:
    """Slack notification implementation"""

    async def is_configured(self, company: Dict) -> bool:
        """Check if Slack is configured for this company"""
        return company.get('slack_webhook_url') is not None

    async def send_notification(self, notification_data: Dict) -> Dict:
        """Send Slack notification"""
        company = notification_data['company']
        candidate = notification_data['candidate']

        webhook_url = company.get('slack_webhook_url')
        if not webhook_url:
            return {'success': False, 'error': 'No Slack webhook configured'}

        # Format Slack message
        message = {
            "text": f"🚀 New Candidate Application - {candidate['name']}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"New Application: {company.get('position')}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Candidate:* {candidate['name']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Title:* {candidate['title']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Experience:* {candidate['experience']} years"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Match Score:* {notification_data['match_score']:.0%}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Skills:* {', '.join(candidate['skills'][:5])}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Message:* {candidate['message']}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "⏰ *This candidate expects a response within 24 hours!*"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Contact Candidate"
                            },
                            "style": "primary",
                            "url": f"mailto:{candidate['email']}"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "View Profile"
                            },
                            "url": "#"  # Would link to candidate profile
                        }
                    ]
                }
            ]
        }

        try:
            response = requests.post(webhook_url, json=message, timeout=10)
            response.raise_for_status()
            return {'success': True, 'message': 'Slack notification sent'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class EmailNotifier:
    """Email notification implementation"""

    async def is_configured(self, company: Dict) -> bool:
        """Check if email is configured"""
        return company.get('notification_email') is not None

    async def send_notification(self, notification_data: Dict) -> Dict:
        """Send email notification"""
        company = notification_data['company']
        candidate = notification_data['candidate']

        to_email = company.get('notification_email')
        if not to_email:
            return {'success': False, 'error': 'No notification email configured'}

        # Email configuration (would be in environment variables)
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        from_email = os.getenv('FROM_EMAIL', 'noreply@coboarding.com')
        email_password = os.getenv('EMAIL_PASSWORD', '')

        # Create email content
        subject = f"🚀 New Candidate: {candidate['name']} - {company.get('position')}"

        html_content = f"""
        <html>
        <body>
            <h2>New Candidate Application</h2>
            <p><strong>Position:</strong> {company.get('position', 'N/A')}</p>
            <p><strong>Company:</strong> {company.get('company', 'N/A')}</p>

            <h3>Candidate Information</h3>
            <ul>
                <li><strong>Name:</strong> {candidate.get('name', 'N/A')}</li>
                <li><strong>Title:</strong> {candidate.get('title', 'N/A')}</li>
                <li><strong>Email:</strong> {candidate.get('email', 'N/A')}</li>
                <li><strong>Phone:</strong> {candidate.get('phone', 'N/A')}</li>
            </ul>

            <h3>Message</h3>
            <p>{notification_data.get('message', 'No additional message provided.')}</p>

            <p>Please log in to the coBoarding platform to view the full candidate profile and respond.</p>
            
            <p>Best regards,<br>The coBoarding Team</p>
        </body>
        </html>
        """