"""
Helper classes and utilities for the coBoarding platform.

This module provides various utility classes and functions that are used throughout
the application, including configuration management, task queuing, and health monitoring.
"""
import os
import time
import json
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Coroutine
from datetime import datetime, timedelta
import logging
import psutil
import aiohttp
from loguru import logger


@dataclass
class WorkerConfig:
    """
    Configuration for worker processes.
    
    This class holds configuration parameters for background workers, including
    concurrency settings, timeouts, and retry logic.
    """
    # Worker identification
    worker_id: str = field(default_factory=lambda: f'worker-{os.getpid()}')
    worker_type: str = 'default'
    
    # Concurrency settings
    max_concurrent_tasks: int = 5
    task_timeout: int = 300  # seconds
    
    # Retry settings
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    
    # Queue settings
    queue_name: str = 'default'
    queue_priority: int = 1
    
    # Health check settings
    health_check_interval: int = 60  # seconds
    max_memory_percent: float = 80.0
    max_cpu_percent: float = 80.0
    
    # Logging settings
    log_level: str = 'INFO'
    log_format: str = '{time} | {level} | {message}'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the configuration to a dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'WorkerConfig':
        """Create a WorkerConfig instance from a dictionary."""
        return cls(**config_dict)
    
    def validate(self) -> bool:
        """Validate the configuration values."""
        if self.max_concurrent_tasks < 1:
            raise ValueError("max_concurrent_tasks must be at least 1")
        if self.task_timeout < 1:
            raise ValueError("task_timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.retry_delay < 0:
            raise ValueError("retry_delay cannot be negative")
        if self.max_memory_percent <= 0 or self.max_memory_percent > 100:
            raise ValueError("max_memory_percent must be between 0 and 100")
        if self.max_cpu_percent <= 0 or self.max_cpu_percent > 100:
            raise ValueError("max_cpu_percent must be between 0 and 100")
        return True


class TaskQueue:
    """
    A simple in-memory task queue for background processing.
    
    This class provides a basic implementation of a task queue that can be used
    for background job processing. It supports priority-based task scheduling
    and basic task lifecycle management.
    """
    def __init__(self, max_size: int = 1000):
        """Initialize the task queue."""
        self._queue = asyncio.PriorityQueue(maxsize=max_size)
        self._tasks: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._logger = logger.bind(component='TaskQueue')
    
    async def add_task(
        self,
        task_id: str,
        coro: Callable[..., Coroutine],
        *args,
        priority: int = 1,
        **kwargs
    ) -> bool:
        """
        Add a new task to the queue.
        
        Args:
            task_id: Unique identifier for the task
            coro: Coroutine to execute
            priority: Task priority (lower numbers = higher priority)
            *args: Positional arguments to pass to the coroutine
            **kwargs: Keyword arguments to pass to the coroutine
            
        Returns:
            bool: True if the task was added successfully
        """
        if task_id in self._tasks:
            self._logger.warning(f"Task {task_id} already exists")
            return False
            
        async with self._lock:
            if task_id in self._tasks:
                return False
                
            task = asyncio.create_task(coro(*args, **kwargs))
            self._tasks[task_id] = task
            await self._queue.put((priority, task_id, task))
            return True
    
    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """
        Get the result of a completed task.
        
        Args:
            task_id: ID of the task to get the result for
            timeout: Maximum time to wait for the task to complete (in seconds)
            
        Returns:
            The result of the task, or None if the task failed or timed out
            
        Raises:
            asyncio.TimeoutError: If the task times out
            KeyError: If the task ID is not found
        """
        if task_id not in self._tasks:
            raise KeyError(f"Task {task_id} not found")
            
        task = self._tasks[task_id]
        
        try:
            if not task.done():
                await asyncio.wait_for(task, timeout=timeout)
            return task.result()
        except asyncio.CancelledError:
            self._logger.warning(f"Task {task_id} was cancelled")
            return None
        except Exception as e:
            self._logger.error(f"Task {task_id} failed: {str(e)}")
            return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            bool: True if the task was cancelled, False otherwise
        """
        if task_id not in self._tasks:
            return False
            
        task = self._tasks[task_id]
        
        if task.done():
            return False
            
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
            
        return True
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a task.
        
        Args:
            task_id: ID of the task to get the status for
            
        Returns:
            Dict containing task status information, or None if the task is not found
        """
        if task_id not in self._tasks:
            return None
            
        task = self._tasks[task_id]
        
        status = {
            'task_id': task_id,
            'done': task.done(),
            'cancelled': task.cancelled(),
            'exception': str(task.exception()) if task.exception() else None,
        }
        
        return status
    
    async def cleanup(self):
        """Clean up completed tasks."""
        async with self._lock:
            completed = [task_id for task_id, task in self._tasks.items() if task.done()]
            for task_id in completed:
                del self._tasks[task_id]


class HealthMonitor:
    """
    System health monitoring and resource management.
    
    This class provides functionality to monitor system resources (CPU, memory, disk)
    and application-specific health metrics.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the health monitor.
        
        Args:
            config: Configuration dictionary with threshold values
        """
        self.config = config or {}
        self._start_time = time.time()
        self._logger = logger.bind(component='HealthMonitor')
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get current system health metrics.
        
        Returns:
            Dict containing various system health metrics
        """
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'uptime': time.time() - self._start_time,
            'cpu': {
                'percent': cpu_percent,
                'count': psutil.cpu_count(),
                'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else None,
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory.percent,
                'free': memory.free,
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent,
            },
            'process': {
                'pid': os.getpid(),
                'name': psutil.Process().name(),
                'memory_info': dict(psutil.Process().memory_info()._asdict()),
                'cpu_percent': psutil.Process().cpu_percent(interval=0.1),
                'create_time': psutil.Process().create_time(),
                'status': psutil.Process().status(),
            }
        }
    
    def is_healthy(self, metrics: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if the system is healthy based on the provided metrics.
        
        Args:
            metrics: Optional metrics dictionary. If not provided, current metrics will be collected.
            
        Returns:
            bool: True if the system is considered healthy, False otherwise
        """
        if metrics is None:
            metrics = self.get_system_health()
            
        # Check CPU usage
        cpu_threshold = self.config.get('cpu_threshold', 90.0)
        if metrics['cpu']['percent'] > cpu_threshold:
            self._logger.warning(f"CPU usage too high: {metrics['cpu']['percent']}%")
            return False
            
        # Check memory usage
        memory_threshold = self.config.get('memory_threshold', 90.0)
        if metrics['memory']['percent'] > memory_threshold:
            self._logger.warning(f"Memory usage too high: {metrics['memory']['percent']}%")
            return False
            
        # Check disk usage
        disk_threshold = self.config.get('disk_threshold', 90.0)
        if metrics['disk']['percent'] > disk_threshold:
            self._logger.warning(f"Disk usage too high: {metrics['disk']['percent']}%")
            return False
            
        return True
    
    async def start_monitoring(
        self,
        interval: int = 60,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> asyncio.Task:
        """
        Start monitoring system health at regular intervals.
        
        Args:
            interval: Monitoring interval in seconds
            callback: Optional callback function to call with health metrics
            
        Returns:
            asyncio.Task: The background monitoring task
        """
        async def monitor():
            while True:
                try:
                    metrics = self.get_system_health()
                    is_healthy = self.is_healthy(metrics)
                    
                    metrics['is_healthy'] = is_healthy
                    
                    if callback:
                        try:
                            callback(metrics)
                        except Exception as e:
                            self._logger.error(f"Error in health check callback: {e}")
                    
                    if not is_healthy:
                        self._logger.warning("System health check failed")
                    
                except Exception as e:
                    self._logger.error(f"Error in health monitor: {e}")
                
                await asyncio.sleep(interval)
        
        return asyncio.create_task(monitor())


# Export the main classes for easier importing
__all__ = ['WorkerConfig', 'TaskQueue', 'HealthMonitor']
