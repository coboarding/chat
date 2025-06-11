"""
Automation Engine for the coBoarding platform.

This module provides the AutomationEngine class which handles automated workflows
and scheduled tasks for the application.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.connection import get_db_session
from app.database.models import (
    JobListing, Application, Notification, Candidate, AuditLog
)
from app.core.notification_service import NotificationService

logger = logging.getLogger(__name__)

class AutomationEngine:
    """
    Handles automated workflows and scheduled tasks for the application.
    
    This includes tasks like:
    - Sending reminder notifications
    - Updating application statuses
    - Processing expired job listings
    - Running background tasks
    """
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        """
        Initialize the AutomationEngine.
        
        Args:
            db_session: Optional database session. If not provided, a new one will be created.
        """
        self.db_session = db_session
        self.notification_service = NotificationService()
        self._running = False
    
    async def start(self):
        """Start the automation engine."""
        self._running = True
        logger.info("Automation Engine started")
        
        try:
            while self._running:
                try:
                    # Process all scheduled tasks
                    await self.process_scheduled_tasks()
                    
                    # Sleep for a while before checking again
                    await asyncio.sleep(60)  # Check every minute
                    
                except Exception as e:
                    logger.error(f"Error in automation engine loop: {str(e)}")
                    await asyncio.sleep(60)  # Wait a bit before retrying
                    
        except asyncio.CancelledError:
            logger.info("Automation Engine stopped")
        except Exception as e:
            logger.error(f"Automation Engine crashed: {str(e)}")
            raise
        finally:
            self._running = False
    
    async def stop(self):
        """Stop the automation engine."""
        self._running = False
        logger.info("Stopping Automation Engine...")
    
    async def process_scheduled_tasks(self):
        """Process all scheduled tasks."""
        # Process overdue applications
        await self.process_overdue_applications()
        
        # Process expired job listings
        await self.process_expired_job_listings()
        
        # Process pending notifications
        await self.process_pending_notifications()
    
    async def process_overdue_applications(self):
        """Process applications that are past their due date."""
        session = self.db_session or await get_db_session()
        try:
            # Get overdue applications
            overdue_apps = await get_overdue_applications(session)
            
            for app in overdue_apps:
                try:
                    # Update status to 'overdue'
                    app.status = 'overdue'
                    app.updated_at = datetime.utcnow()
                    
                    # Send notification to the candidate
                    await self.notification_service.send_notification(
                        recipient_id=app.candidate_id,
                        notification_type='application_overdue',
                        title='Application Overdue',
                        message=f'Your application for {app.job_listing.title} is now overdue.',
                        metadata={
                            'job_listing_id': str(app.job_listing_id),
                            'application_id': str(app.id)
                        }
                    )
                    
                    # Log the event
                    await log_audit_event(
                        session=session,
                        event_type='application_overdue',
                        target_id=str(app.id),
                        target_type='application',
                        details={'status': 'overdue'},
                        ip_address='system',
                        user_agent='automation_engine/1.0'
                    )
                    
                    await session.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing overdue application {app.id}: {str(e)}")
                    await session.rollback()
                    
        except Exception as e:
            logger.error(f"Error in process_overdue_applications: {str(e)}")
            raise
        finally:
            if not self.db_session:
                await session.close()
    
    async def process_expired_job_listings(self):
        """Process job listings that have expired."""
        session = self.db_session or await get_db_session()
        try:
            # Get expired job listings
            expired_jobs = await get_expired_job_listings(session)
            
            for job in expired_jobs:
                try:
                    # Update status to 'expired'
                    job.status = 'expired'
                    job.updated_at = datetime.utcnow()
                    
                    # Get all pending applications for this job
                    pending_apps = await get_applications_for_job_listing(
                        session, 
                        job_id=str(job.id),
                        status='pending'
                    )
                    
                    # Update all pending applications to 'expired'
                    for app in pending_apps:
                        app.status = 'expired'
                        app.updated_at = datetime.utcnow()
                        
                        # Send notification to the candidate
                        await self.notification_service.send_notification(
                            recipient_id=app.candidate_id,
                            notification_type='job_expired',
                            title='Job Listing Expired',
                            message=f'The job listing for {job.title} has expired.',
                            metadata={
                                'job_listing_id': str(job.id),
                                'application_id': str(app.id)
                            }
                        )
                    
                    # Log the event
                    await log_audit_event(
                        session=session,
                        event_type='job_expired',
                        target_id=str(job.id),
                        target_type='job_listing',
                        details={'status': 'expired'},
                        ip_address='system',
                        user_agent='automation_engine/1.0'
                    )
                    
                    await session.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing expired job {job.id}: {str(e)}")
                    await session.rollback()
                    
        except Exception as e:
            logger.error(f"Error in process_expired_job_listings: {str(e)}")
            raise
        finally:
            if not self.db_session:
                await session.close()
    
    async def process_pending_notifications(self):
        """Process pending notifications and send them."""
        session = self.db_session or await get_db_session()
        try:
            # Get pending notifications
            pending_notifs = await get_pending_notifications(session, limit=50)
            
            for notif in pending_notifs:
                try:
                    # Mark as sending
                    notif.status = 'sending'
                    notif.updated_at = datetime.utcnow()
                    await session.commit()
                    
                    # Send the notification
                    success = await self.notification_service.send_notification(
                        recipient_id=notif.recipient_id,
                        notification_type=notif.notification_type,
                        title=notif.title,
                        message=notif.message,
                        metadata=notif.metadata or {}
                    )
                    
                    # Update status based on result
                    notif.status = 'sent' if success else 'failed'
                    notif.sent_at = datetime.utcnow()
                    notif.updated_at = datetime.utcnow()
                    
                    await session.commit()
                    
                except Exception as e:
                    logger.error(f"Error sending notification {notif.id}: {str(e)}")
                    notif.status = 'failed'
                    notif.updated_at = datetime.utcnow()
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Error in process_pending_notifications: {str(e)}")
            raise
        finally:
            if not self.db_session:
                await session.close()
    
    async def trigger_workflow(self, workflow_name: str, data: Dict[str, Any]):
        """
        Trigger a specific workflow by name.
        
        Args:
            workflow_name: Name of the workflow to trigger
            data: Data to pass to the workflow
            
        Returns:
            bool: True if the workflow was triggered successfully
        """
        try:
            if workflow_name == 'new_application':
                return await self._handle_new_application(data)
            elif workflow_name == 'application_reviewed':
                return await self._handle_application_reviewed(data)
            elif workflow_name == 'interview_scheduled':
                return await self._handle_interview_scheduled(data)
            else:
                logger.warning(f"Unknown workflow: {workflow_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error in workflow {workflow_name}: {str(e)}")
            return False
    
    async def _handle_new_application(self, data: Dict[str, Any]) -> bool:
        """Handle a new application workflow."""
        session = self.db_session or await get_db_session()
        try:
            # Get the application and related data
            application_id = data.get('application_id')
            if not application_id:
                logger.error("No application_id provided for new_application workflow")
                return False
                
            # Get the application with related data
            app = await get_application(session, application_id)
            if not app:
                logger.error(f"Application not found: {application_id}")
                return False
                
            # Send confirmation to candidate
            await self.notification_service.send_notification(
                recipient_id=app.candidate_id,
                notification_type='application_received',
                title='Application Received',
                message=f'We have received your application for {app.job_listing.title}.',
                metadata={
                    'job_listing_id': str(app.job_listing_id),
                    'application_id': str(app.id)
                }
            )
            
            # Notify HR/recruiter (in a real app, this would be more sophisticated)
            await self.notification_service.send_notification(
                recipient_id='hr-team',  # This would be a group or specific user in a real app
                notification_type='new_application',
                title='New Application Received',
                message=f'New application for {app.job_listing.title} from {app.candidate.email}.',
                metadata={
                    'job_listing_id': str(app.job_listing_id),
                    'application_id': str(app.id),
                    'candidate_id': str(app.candidate_id)
                }
            )
            
            # Log the event
            await log_audit_event(
                session=session,
                event_type='workflow_triggered',
                target_id=str(app.id),
                target_type='application',
                details={
                    'workflow': 'new_application',
                    'status': 'completed'
                },
                ip_address='system',
                user_agent='automation_engine/1.0'
            )
            
            await session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error in _handle_new_application: {str(e)}")
            if session.in_transaction():
                await session.rollback()
            return False
            
        finally:
            if not self.db_session:
                await session.close()
    
    async def _handle_application_reviewed(self, data: Dict[str, Any]) -> bool:
        """Handle an application review workflow."""
        # Implementation would be similar to _handle_new_application
        # but specific to the application_reviewed workflow
        return True
    
    async def _handle_interview_scheduled(self, data: Dict[str, Any]) -> bool:
        """Handle an interview scheduled workflow."""
        # Implementation would be similar to _handle_new_application
        # but specific to the interview_scheduled workflow
        return True


# Singleton instance
_automation_engine = None


def get_automation_engine() -> AutomationEngine:
    """
    Get or create the singleton instance of AutomationEngine.
    
    Returns:
        AutomationEngine: The singleton instance
    """
    global _automation_engine
    if _automation_engine is None:
        _automation_engine = AutomationEngine()
    return _automation_engine


async def start_automation_engine():
    """Start the automation engine."""
    engine = get_automation_engine()
    await engine.start()


async def stop_automation_engine():
    """Stop the automation engine."""
    engine = get_automation_engine()
    await engine.stop()


# Export the AutomationEngine class for direct import
__all__ = [
    'AutomationEngine',
    'get_automation_engine',
    'start_automation_engine',
    'stop_automation_engine'
]
