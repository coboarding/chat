# worker/utils/helpers.py
"""
Helper utilities for worker processes
Provides configuration, task queue management, and health monitoring
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import aioredis
from loguru import logger


class TaskStatus(Enum):
    """Task status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class WorkerConfig:
    """Worker configuration settings"""

    def __init__(self):
        # Redis configuration
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

        # Database configuration
        self.database_url = os.getenv('DATABASE_URL',
                                      'postgresql://coboarding:secure_password_123@postgres:5432/coboarding')

        # Ollama configuration
        self.ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')

        # Worker settings
        self.concurrency = int(os.getenv('WORKER_CONCURRENCY', '3'))
        self.task_timeout = int(os.getenv('TASK_TIMEOUT', '300'))  # 5 minutes
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('RETRY_DELAY', '60'))  # 1 minute

        # Browser automation settings
        self.headless = os.getenv('HEADLESS', 'true').lower() == 'true'
        self.browser_timeout = int(os.getenv('BROWSER_TIMEOUT', '60'))
        self.download_timeout = int(os.getenv('DOWNLOAD_TIMEOUT', '30'))

        # File handling
        self.max_file_size = int(os.getenv('MAX_FILE_SIZE', '10485760'))  # 10MB
        self.allowed_file_types = os.getenv('ALLOWED_FILE_TYPES', 'pdf,docx,txt').split(',')

        # Logging
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.log_retention = os.getenv('LOG_RETENTION', '7 days')

        # Performance settings
        self.memory_limit_mb = int(os.getenv('MEMORY_LIMIT_MB', '2048'))
        self.cpu_limit = float(os.getenv('CPU_LIMIT', '2.0'))


class TaskQueue:
    """Redis-based task queue for background processing"""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.queue_key = "coboarding:task_queue"
        self.processing_key = "coboarding:processing_tasks"
        self.completed_key = "coboarding:completed_tasks"
        self.failed_key = "coboarding:failed_tasks"
        self.stats_key = "coboarding:task_stats"

    async def add_task(self, task_type: str, task_data: Dict, priority: int = 0) -> str:
        """Add a new task to the queue"""
        task_id = f"task_{datetime.utcnow().timestamp()}_{task_type}"

        task = {
            'id': task_id,
            'type': task_type,
            'data': task_data,
            'status': TaskStatus.PENDING.value,
            'priority': priority,
            'created_at': datetime.utcnow().isoformat(),
            'attempts': 0,
            'max_retries': 3
        }

        # Add to queue with priority (lower number = higher priority)
        await self.redis.zadd(self.queue_key, {json.dumps(task): priority})

        # Update stats
        await self._update_stats('tasks_queued', 1)

        logger.info(f"Task {task_id} added to queue with priority {priority}")
        return task_id

    async def get_task(self, timeout: int = 30) -> Optional[Dict]:
        """Get next task from queue (blocking with timeout)"""
        try:
            # Pop task with highest priority (lowest score)
            result = await self.redis.bzpopmin(self.queue_key, timeout=timeout)

            if result:
                queue_name, task_json, score = result
                task = json.loads(task_json)

                # Move to processing queue
                await self.redis.hset(
                    self.processing_key,
                    task['id'],
                    json.dumps({
                        **task,
                        'status': TaskStatus.PROCESSING.value,
                        'started_at': datetime.utcnow().isoformat()
                    })
                )

                logger.info(f"Retrieved task {task['id']} from queue")
                return task

            return None

        except Exception as e:
            logger.error(f"Error getting task from queue: {e}")
            return None

    async def mark_processing(self, task_id: str, worker_id: str):
        """Mark task as being processed by worker"""
        task_data = await self.redis.hget(self.processing_key, task_id)

        if task_data:
            task = json.loads(task_data)
            task.update({
                'status': TaskStatus.PROCESSING.value,
                'worker_id': worker_id,
                'processing_started': datetime.utcnow().isoformat()
            })

            await self.redis.hset(
                self.processing_key,
                task_id,
                json.dumps(task)
            )

    async def mark_completed(self, task_id: str, result: Dict, processing_time: float):
        """Mark task as completed successfully"""
        # Remove from processing queue
        task_data = await self.redis.hget(self.processing_key, task_id)
        await self.redis.hdel(self.processing_key, task_id)

        if task_data:
            task = json.loads(task_data)
            task.update({
                'status': TaskStatus.COMPLETED.value,
                'result': result,
                'completed_at': datetime.utcnow().isoformat(),
                'processing_time': processing_time
            })

            # Store in completed tasks (with TTL)
            await self.redis.hset(
                self.completed_key,
                task_id,
                json.dumps(task)
            )
            await self.redis.expire(self.completed_key, 86400)  # 24 hours

            # Update stats
            await self._update_stats('tasks_completed', 1)
            await self._update_stats('total_processing_time', processing_time)

    async def mark_failed(self, task_id: str, error: str, processing_time: float):
        """Mark task as failed"""
        # Get task from processing queue
        task_data = await self.redis.hget(self.processing_key, task_id)

        if task_data:
            task = json.loads(task_data)
            task['attempts'] = task.get('attempts', 0) + 1

            # Check if we should retry
            if task['attempts'] < task.get('max_retries', 3):
                # Schedule retry
                retry_delay = min(60 * (2 ** task['attempts']), 3600)  # Exponential backoff, max 1 hour
                retry_time = datetime.utcnow() + timedelta(seconds=retry_delay)

                task.update({
                    'status': TaskStatus.RETRYING.value,
                    'last_error': error,
                    'retry_at': retry_time.isoformat(),
                    'processing_time': processing_time
                })

                # Re-queue for retry
                await self.redis.zadd(
                    self.queue_key,
                    {json.dumps(task): task.get('priority', 0)}
                )

                await self.redis.hdel(self.processing_key, task_id)

                logger.warning(
                    f"Task {task_id} failed, scheduled for retry in {retry_delay}s (attempt {task['attempts']})")
            else:
                # Max retries reached, mark as permanently failed
                task.update({
                    'status': TaskStatus.FAILED.value,
                    'error': error,
                    'failed_at': datetime.utcnow().isoformat(),
                    'processing_time': processing_time
                })

                await self.redis.hdel(self.processing_key, task_id)
                await self.redis.hset(
                    self.failed_key,
                    task_id,
                    json.dumps(task)
                )
                await self.redis.expire(self.failed_key, 86400 * 7)  # 7 days

                # Update stats
                await self._update_stats('tasks_failed', 1)

                logger.error(f"Task {task_id} permanently failed after {task['attempts']} attempts: {error}")

    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get current status of a task"""
        # Check processing queue
        task_data = await self.redis.hget(self.processing_key, task_id)
        if task_data:
            return json.loads(task_data)

        # Check completed queue
        task_data = await self.redis.hget(self.completed_key, task_id)
        if task_data:
            return json.loads(task_data)

        # Check failed queue
        task_data = await self.redis.hget(self.failed_key, task_id)
        if task_data:
            return json.loads(task_data)

        # Check main queue
        tasks = await self.redis.zrange(self.queue_key, 0, -1)
        for task_json in tasks:
            task = json.loads(task_json)
            if task['id'] == task_id:
                return task

        return None

    async def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        stats = {}

        # Queue lengths
        stats['pending'] = await self.redis.zcard(self.queue_key)
        stats['processing'] = await self.redis.hlen(self.processing_key)
        stats['completed'] = await self.redis.hlen(self.completed_key)
        stats['failed'] = await self.redis.hlen(self.failed_key)

        # Historical stats
        historical_stats = await self.redis.hgetall(self.stats_key)
        for key, value in historical_stats.items():
            try:
                stats[key] = float(value)
            except (ValueError, TypeError):
                stats[key] = value

        return stats

    async def _update_stats(self, metric: str, value: float):
        """Update task statistics"""
        await self.redis.hincrbyfloat(self.stats_key, metric, value)
        await self.redis.expire(self.stats_key, 86400 * 30)  # 30 days

    async def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old completed and failed tasks"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        cutoff_timestamp = cutoff_time.isoformat()

        cleaned_completed = 0
        cleaned_failed = 0

        # Clean completed tasks
        completed_tasks = await self.redis.hgetall(self.completed_key)
        for task_id, task_data in completed_tasks.items():
            try:
                task = json.loads(task_data)
                if task.get('completed_at', '') < cutoff_timestamp:
                    await self.redis.hdel(self.completed_key, task_id)
                    cleaned_completed += 1
            except json.JSONDecodeError:
                # Remove invalid task data
                await self.redis.hdel(self.completed_key, task_id)
                cleaned_completed += 1

        # Clean failed tasks
        failed_tasks = await self.redis.hgetall(self.failed_key)
        for task_id, task_data in failed_tasks.items():
            try:
                task = json.loads(task_data)
                if task.get('failed_at', '') < cutoff_timestamp:
                    await self.redis.hdel(self.failed_key, task_id)
                    cleaned_failed += 1
            except json.JSONDecodeError:
                await self.redis.hdel(self.failed_key, task_id)
                cleaned_failed += 1

        logger.info(f"Cleaned up {cleaned_completed} completed and {cleaned_failed} failed tasks")
        return {'completed': cleaned_completed, 'failed': cleaned_failed}


class HealthMonitor:
    """Health monitoring for worker processes"""

    def __init__(self, worker_id: str, redis_client: aioredis.Redis):
        self.worker_id = worker_id
        self.redis = redis_client
        self.health_key = f"worker_health:{worker_id}"
        self.last_heartbeat = datetime.utcnow()

    async def get_worker_status(self, worker_id: Optional[str] = None) -> Optional[Dict]:
        """Get health status for a specific worker"""
        target_worker = worker_id or self.worker_id
        health_key = f"worker_health:{target_worker}"

        status_data = await self.redis.get(health_key)
        if status_data:
            return json.loads(status_data)
        return None

    async def get_all_workers_status(self) -> List[Dict]:
        """Get health status for all workers"""
        pattern = "worker_health:*"
        keys = await self.redis.keys(pattern)

        workers = []
        for key in keys:
            status_data = await self.redis.get(key)
            if status_data:
                try:
                    worker_status = json.loads(status_data)
                    workers.append(worker_status)
                except json.JSONDecodeError:
                    # Remove invalid status data
                    await self.redis.delete(key)

        return workers

    async def check_worker_health(self) -> Dict:
        """Perform health check and return status"""
        try:
            # Check Redis connectivity
            await self.redis.ping()
            redis_healthy = True
        except Exception:
            redis_healthy = False

        # Check memory usage
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_healthy = memory_info.rss < (2 * 1024 * 1024 * 1024)  # Less than 2GB
        except ImportError:
            memory_healthy = True  # Can't check without psutil
        except Exception:
            memory_healthy = False

        # Overall health status
        overall_healthy = redis_healthy and memory_healthy

        return {
            'healthy': overall_healthy,
            'redis_connected': redis_healthy,
            'memory_ok': memory_healthy,
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'uptime_seconds': (datetime.utcnow() - self.last_heartbeat).total_seconds()
        }

    async def cleanup_dead_workers(self, max_silence_minutes: int = 5):
        """Remove health records for workers that haven't reported in a while"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=max_silence_minutes)

        pattern = "worker_health:*"
        keys = await self.redis.keys(pattern)

        cleaned_count = 0
        for key in keys:
            status_data = await self.redis.get(key)
            if status_data:
                try:
                    worker_status = json.loads(status_data)
                    last_heartbeat = datetime.fromisoformat(worker_status['last_heartbeat'])

                    if last_heartbeat < cutoff_time:
                        await self.redis.delete(key)
                        cleaned_count += 1
                        logger.info(f"Removed dead worker status: {key}")

                except (json.JSONDecodeError, KeyError, ValueError):
                    # Remove invalid status data
                    await self.redis.delete(key)
                    cleaned_count += 1

        return cleaned_count


class TaskValidator:
    """Validates task data and parameters"""

    @staticmethod
    def validate_form_detection_task(task_data: Dict) -> bool:
        """Validate form detection task data"""
        required_fields = ['url']
        optional_fields = ['method', 'timeout', 'user_agent']

        # Check required fields
        for field in required_fields:
            if field not in task_data:
                logger.error(f"Missing required field: {field}")
                return False

        # Validate URL format
        url = task_data['url']
        if not url.startswith(('http://', 'https://')):
            logger.error(f"Invalid URL format: {url}")
            return False

        # Validate optional fields
        if 'method' in task_data:
            valid_methods = ['dom', 'visual', 'tab', 'hybrid']
            if task_data['method'] not in valid_methods:
                logger.error(f"Invalid detection method: {task_data['method']}")
                return False

        return True

    @staticmethod
    def validate_form_filling_task(task_data: Dict) -> bool:
        """Validate form filling task data"""
        required_fields = ['url', 'cv_data']

        for field in required_fields:
            if field not in task_data:
                logger.error(f"Missing required field: {field}")
                return False

        # Validate CV data structure
        cv_data = task_data['cv_data']
        if not isinstance(cv_data, dict):
            logger.error("CV data must be a dictionary")
            return False

        # Check for essential CV fields
        essential_fields = ['name', 'email']
        for field in essential_fields:
            if field not in cv_data or not cv_data[field]:
                logger.warning(f"Missing essential CV field: {field}")

        return True

    @staticmethod
    def validate_job_application_task(task_data: Dict) -> bool:
        """Validate job application task data"""
        required_fields = ['job_listing', 'cv_data']

        for field in required_fields:
            if field not in task_data:
                logger.error(f"Missing required field: {field}")
                return False

        # Validate job listing
        job_listing = task_data['job_listing']
        if not isinstance(job_listing, dict):
            logger.error("Job listing must be a dictionary")
            return False

        if 'application_url' not in job_listing:
            logger.error("Job listing must contain application_url")
            return False

        return TaskValidator.validate_form_filling_task(task_data)


class PerformanceMonitor:
    """Monitor worker performance and resources"""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.metrics_key = "worker_metrics"

    async def record_task_metrics(self, task_id: str, metrics: Dict):
        """Record performance metrics for a task"""
        timestamp = datetime.utcnow().isoformat()
        metric_data = {
            'task_id': task_id,
            'timestamp': timestamp,
            **metrics
        }

        # Store metrics with TTL
        await self.redis.lpush(
            f"{self.metrics_key}:tasks",
            json.dumps(metric_data)
        )

        # Keep only last 1000 task metrics
        await self.redis.ltrim(f"{self.metrics_key}:tasks", 0, 999)
        await self.redis.expire(f"{self.metrics_key}:tasks", 86400)  # 24 hours

    async def record_system_metrics(self, worker_id: str):
        """Record system-level metrics"""
        try:
            import psutil

            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Get process metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent()

            metrics = {
                'worker_id': worker_id,
                'timestamp': datetime.utcnow().isoformat(),
                'system': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_available_gb': memory.available / (1024 ** 3),
                    'disk_percent': (disk.used / disk.total) * 100
                },
                'process': {
                    'cpu_percent': process_cpu,
                    'memory_rss_mb': process_memory.rss / (1024 ** 2),
                    'memory_vms_mb': process_memory.vms / (1024 ** 2),
                    'num_threads': process.num_threads()
                }
            }

            await self.redis.lpush(
                f"{self.metrics_key}:system",
                json.dumps(metrics)
            )

            # Keep only last 100 system metrics
            await self.redis.ltrim(f"{self.metrics_key}:system", 0, 99)
            await self.redis.expire(f"{self.metrics_key}:system", 86400)

        except ImportError:
            logger.warning("psutil not available for system metrics")
        except Exception as e:
            logger.error(f"Error recording system metrics: {e}")

    async def get_performance_summary(self, hours: int = 24) -> Dict:
        """Get performance summary for the last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        # Get task metrics
        task_metrics_raw = await self.redis.lrange(f"{self.metrics_key}:tasks", 0, -1)
        task_metrics = []

        for metric_json in task_metrics_raw:
            try:
                metric = json.loads(metric_json)
                metric_time = datetime.fromisoformat(metric['timestamp'])

                if metric_time >= cutoff_time:
                    task_metrics.append(metric)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        # Calculate task performance statistics
        if task_metrics:
            processing_times = [m.get('processing_time', 0) for m in task_metrics]
            memory_usage = [m.get('memory_usage', {}).get('rss_mb', 0) for m in task_metrics]

            task_stats = {
                'total_tasks': len(task_metrics),
                'avg_processing_time': sum(processing_times) / len(processing_times),
                'max_processing_time': max(processing_times),
                'min_processing_time': min(processing_times),
                'avg_memory_mb': sum(memory_usage) / len(memory_usage) if memory_usage else 0
            }
        else:
            task_stats = {
                'total_tasks': 0,
                'avg_processing_time': 0,
                'max_processing_time': 0,
                'min_processing_time': 0,
                'avg_memory_mb': 0
            }

        # Get latest system metrics
        system_metrics_raw = await self.redis.lrange(f"{self.metrics_key}:system", 0, 9)
        latest_system_metrics = None

        if system_metrics_raw:
            try:
                latest_system_metrics = json.loads(system_metrics_raw[0])
            except json.JSONDecodeError:
                pass

        return {
            'period_hours': hours,
            'task_performance': task_stats,
            'latest_system_metrics': latest_system_metrics,
            'summary_generated_at': datetime.utcnow().isoformat()
        }


# Utility functions for worker operations
async def create_task(redis_client: aioredis.Redis, task_type: str, task_data: Dict, priority: int = 0) -> str:
    """Convenience function to create a task"""
    task_queue = TaskQueue(redis_client)
    return await task_queue.add_task(task_type, task_data, priority)


async def get_worker_stats(redis_client: aioredis.Redis) -> Dict:
    """Get comprehensive worker statistics"""
    task_queue = TaskQueue(redis_client)
    performance_monitor = PerformanceMonitor(redis_client)

    queue_stats = await task_queue.get_queue_stats()
    performance_stats = await performance_monitor.get_performance_summary()

    # Get worker health information
    health_monitor = HealthMonitor("stats_collector", redis_client)
    all_workers = await health_monitor.get_all_workers_status()

    healthy_workers = [w for w in all_workers if w.get('status') == 'healthy']

    return {
        'queue_statistics': queue_stats,
        'performance_metrics': performance_stats,
        'worker_health': {
            'total_workers': len(all_workers),
            'healthy_workers': len(healthy_workers),
            'unhealthy_workers': len(all_workers) - len(healthy_workers),
            'worker_details': all_workers
        },
        'generated_at': datetime.utcnow().isoformat()
    }


# Error handling utilities
class WorkerException(Exception):
    """Base exception for worker operations"""
    pass


class TaskValidationError(WorkerException):
    """Raised when task data validation fails"""
    pass


class TaskTimeoutError(WorkerException):
    """Raised when task execution times out"""
    pass


class BrowserAutomationError(WorkerException):
    """Raised when browser automation fails"""
    pass.utcnow()

    async def update_status(self, status_data: Dict):
        """Update worker health status"""
        status = {
            'worker_id': self.worker_id,
            'last_heartbeat': datetime.utcnow().isoformat(),
            'status': status_data.get('status', 'unknown'),
            **status_data
        }

        # Store status with TTL (worker considered unhealthy if no update for 2 minutes)
        await self.redis.setex(
            self.health_key,
            120,  # 2 minutes TTL
            json.dumps(status)
        )

        self.last_heartbeat = datetime.utcnow()