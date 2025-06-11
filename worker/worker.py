# worker/worker.py
"""
Form automation worker for coBoarding platform
Handles background automation tasks including form detection and filling
"""

import asyncio
import json
import os
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import traceback

import aioredis
from loguru import logger

# Configure logging
logger.add(
    "/worker/logs/worker.log",
    rotation="100 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

# Import worker components
from core.automation_worker import AutomationWorker
from utils.helpers import WorkerConfig, TaskQueue, HealthMonitor

class FormAutomationWorker:
    """Main worker class for form automation tasks"""
    
    def __init__(self):
        self.config = WorkerConfig()
        self.running = False
        self.worker_id = f"worker_{os.getpid()}"
        self.start_time = datetime.utcnow()
        
        # Components
        self.redis_client: Optional[aioredis.Redis] = None
        self.task_queue: Optional[TaskQueue] = None
        self.automation_worker: Optional[AutomationWorker] = None
        self.health_monitor: Optional[HealthMonitor] = None
        
        # Metrics
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.last_task_time: Optional[datetime] = None
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    async def initialize(self):
        """Initialize worker components"""
        try:
            logger.info(f"Initializing worker {self.worker_id}...")
            
            # Initialize Redis connection
            self.redis_client = aioredis.from_url(
                self.config.redis_url,
                decode_responses=True,
                max_connections=10
            )
            
            # Test Redis connection
            await self.redis_client.ping()
            logger.info("✅ Redis connection established")
            
            # Initialize components
            self.task_queue = TaskQueue(self.redis_client)
            self.automation_worker = AutomationWorker(
                redis_client=self.redis_client,
                config=self.config
            )
            self.health_monitor = HealthMonitor(
                worker_id=self.worker_id,
                redis_client=self.redis_client
            )
            
            # Register worker
            await self._register_worker()
            
            logger.info(f"✅ Worker {self.worker_id} initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Worker initialization failed: {e}")
            logger.error(traceback.format_exc())
            raise

    async def start(self):
        """Start the worker main loop"""
        if self.running:
            logger.warning("Worker is already running")
            return
        
        self.running = True
        logger.info(f"🚀 Starting worker {self.worker_id}...")
        
        try:
            # Start health monitoring
            health_task = asyncio.create_task(self._health_monitor_loop())
            
            # Start main processing loop
            processing_task = asyncio.create_task(self._processing_loop())
            
            # Wait for either task to complete (should not happen in normal operation)
            done, pending = await asyncio.wait(
                [health_task, processing_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
        except Exception as e:
            logger.error(f"❌ Worker error: {e}")
            logger.error(traceback.format_exc())
        finally:
            await self.stop()

    async def stop(self):
        """Stop the worker gracefully"""
        if not self.running:
            return
        
        logger.info(f"🛑 Stopping worker {self.worker_id}...")
        self.running = False
        
        try:
            # Unregister worker
            await self._unregister_worker()
            
            # Close connections
            if self.redis_client:
                await self.redis_client.close()
            
            logger.info(f"✅ Worker {self.worker_id} stopped gracefully")
            
        except Exception as e:
            logger.error(f"❌ Error during worker shutdown: {e}")

    async def _processing_loop(self):
        """Main processing loop"""
        logger.info("🔄 Starting task processing loop...")
        
        consecutive_empty_polls = 0
        max_empty_polls = 10
        
        while self.running:
            try:
                # Get task from queue
                task = await self.task_queue.get_task(
                    timeout=self.config.task_timeout
                )
                
                if task:
                    consecutive_empty_polls = 0
                    await self._process_task(task)
                else:
                    consecutive_empty_polls += 1
                    
                    # Implement backoff when no tasks available
                    if consecutive_empty_polls >= max_empty_polls:
                        await asyncio.sleep(5)  # Sleep 5 seconds
                        consecutive_empty_polls = 0
                    else:
                        await asyncio.sleep(1)  # Short sleep
                
            except asyncio.CancelledError:
                logger.info("Processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in processing loop: {e}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(5)  # Wait before retrying

    async def _process_task(self, task: Dict):
        """Process a single automation task"""
        task_id = task.get('id', 'unknown')
        task_type = task.get('type', 'unknown')
        
        logger.info(f"📋 Processing task {task_id} (type: {task_type})")
        
        start_time = datetime.utcnow()
        self.last_task_time = start_time
        
        try:
            # Mark task as processing
            await self.task_queue.mark_processing(task_id, self.worker_id)
            
            # Process based on task type
            result = None
            if task_type == 'form_detection':
                result = await self._handle_form_detection(task)
            elif task_type == 'form_filling':
                result = await self._handle_form_filling(task)
            elif task_type == 'cv_upload_automation':
                result = await self._handle_cv_upload_automation(task)
            elif task_type == 'job_application':
                result = await self._handle_job_application(task)
            else:
                raise ValueError(f"Unknown task type: {task_type}")
            
            # Mark task as completed
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            await self.task_queue.mark_completed(
                task_id, 
                result, 
                processing_time
            )
            
            self.tasks_processed += 1
            logger.info(f"✅ Task {task_id} completed in {processing_time:.2f}s")
            
        except Exception as e:
            # Mark task as failed
            error_msg = str(e)
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            await self.task_queue.mark_failed(
                task_id, 
                error_msg, 
                processing_time
            )
            
            self.tasks_failed += 1
            logger.error(f"❌ Task {task_id} failed after {processing_time:.2f}s: {error_msg}")
            logger.error(traceback.format_exc())

    async def _handle_form_detection(self, task: Dict) -> Dict:
        """Handle form detection task"""
        url = task['data']['url']
        detection_method = task['data'].get('method', 'hybrid')
        
        logger.info(f"🔍 Detecting forms on {url} using {detection_method} method")
        
        result = await self.automation_worker.detect_forms(
            url=url,
            method=detection_method
        )
        
        return {
            'url': url,
            'method': detection_method,
            'fields_found': len(result.get('fields', [])),
            'fields': result.get('fields', []),
            'processing_time': result.get('processing_time', 0),
            'success': result.get('success', False)
        }

    async def _handle_form_filling(self, task: Dict) -> Dict:
        """Handle form filling task"""
        url = task['data']['url']
        cv_data = task['data']['cv_data']
        form_fields = task['data'].get('form_fields', [])
        
        logger.info(f"📝 Filling forms on {url}")
        
        result = await self.automation_worker.fill_forms(
            url=url,
            cv_data=cv_data,
            form_fields=form_fields
        )
        
        return {
            'url': url,
            'fields_filled': result.get('fields_filled', 0),
            'success': result.get('success', False),
            'screenshots': result.get('screenshots', []),
            'errors': result.get('errors', []),
            'processing_time': result.get('processing_time', 0)
        }

    async def _handle_cv_upload_automation(self, task: Dict) -> Dict:
        """Handle CV upload automation task"""
        url = task['data']['url']
        cv_file_path = task['data']['cv_file_path']
        additional_data = task['data'].get('additional_data', {})
        
        logger.info(f"📄 Uploading CV to {url}")
        
        result = await self.automation_worker.upload_cv(
            url=url,
            cv_file_path=cv_file_path,
            additional_data=additional_data
        )
        
        return {
            'url': url,
            'upload_success': result.get('upload_success', False),
            'form_filled': result.get('form_filled', False),
            'submitted': result.get('submitted', False),
            'confirmation_received': result.get('confirmation_received', False),
            'processing_time': result.get('processing_time', 0),
            'errors': result.get('errors', [])
        }

    async def _handle_job_application(self, task: Dict) -> Dict:
        """Handle complete job application automation"""
        job_listing = task['data']['job_listing']
        cv_data = task['data']['cv_data']
        application_url = job_listing.get('application_url')
        
        if not application_url:
            raise ValueError("No application URL provided in job listing")
        
        logger.info(f"🎯 Applying to {job_listing.get('company')} - {job_listing.get('position')}")
        
        result = await self.automation_worker.complete_job_application(
            job_listing=job_listing,
            cv_data=cv_data
        )
        
        return {
            'job_id': job_listing.get('id'),
            'company': job_listing.get('company'),
            'position': job_listing.get('position'),
            'application_submitted': result.get('application_submitted', False),
            'confirmation_received': result.get('confirmation_received', False),
            'follow_up_required': result.get('follow_up_required', False),
            'processing_time': result.get('processing_time', 0),
            'errors': result.get('errors', []),
            'screenshots': result.get('screenshots', [])
        }

    async def _health_monitor_loop(self):
        """Health monitoring loop"""
        while self.running:
            try:
                await self.health_monitor.update_status({
                    'status': 'healthy',
                    'tasks_processed': self.tasks_processed,
                    'tasks_failed': self.tasks_failed,
                    'last_task_time': self.last_task_time.isoformat() if self.last_task_time else None,
                    'uptime_seconds': (datetime.utcnow() - self.start_time).total_seconds(),
                    'memory_usage': self._get_memory_usage(),
                    'concurrent_tasks': getattr(self.automation_worker, 'active_tasks', 0)
                })
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Health monitor error: {e}")
                await asyncio.sleep(30)

    async def _register_worker(self):
        """Register worker in Redis"""
        worker_info = {
            'id': self.worker_id,
            'pid': os.getpid(),
            'start_time': self.start_time.isoformat(),
            'config': {
                'concurrency': self.config.concurrency,
                'task_timeout': self.config.task_timeout,
                'max_retries': self.config.max_retries
            },
            'status': 'starting'
        }
        
        await self.redis_client.hset(
            'workers:active',
            self.worker_id,
            json.dumps(worker_info)
        )
        
        # Set TTL for worker registration
        await self.redis_client.expire(f'workers:active', 300)  # 5 minutes
        
        logger.info(f"✅ Worker {self.worker_id} registered")

    async def _unregister_worker(self):
        """Unregister worker from Redis"""
        await self.redis_client.hdel('workers:active', self.worker_id)
        logger.info(f"✅ Worker {self.worker_id} unregistered")

    def _get_memory_usage(self) -> Dict:
        """Get current memory usage"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                'rss_mb': memory_info.rss / 1024 / 1024,
                'vms_mb': memory_info.vms / 1024 / 1024,
                'percent': process.memory_percent()
            }
        except ImportError:
            return {'error': 'psutil not available'}
        except Exception as e:
            return {'error': str(e)}

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum}, initiating graceful shutdown...")
        self.running = False

# Health check endpoint for Docker/Kubernetes
async def health_check():
    """Simple health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'worker_id': f"worker_{os.getpid()}"
    }

# Main execution
async def main():
    """Main entry point"""
    logger.info("🚀 Starting coBoarding Form Automation Worker...")
    
    worker = FormAutomationWorker()
    
    try:
        await worker.initialize()
        await worker.start()
    except KeyboardInterrupt:
        logger.info("📡 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Worker crashed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        await worker.stop()

if __name__ == "__main__":
    # Set up event loop policy for better performance
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Worker shutdown complete")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)