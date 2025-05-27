"""System resource monitoring for long-running audio recordings."""

import psutil
import logging
from typing import Dict, Any
import asyncio
import time

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Monitor system resources during long recordings."""
    
    def __init__(self, log_interval: int = 300):  # Log every 5 minutes
        self.log_interval = log_interval
        self.monitoring = False
        self._start_memory = None
        self._start_time = None
        
    async def start_monitoring(self):
        """Start system monitoring in background."""
        self.monitoring = True
        self._start_time = time.time()
        self._start_memory = psutil.virtual_memory().used
        
        # Start monitoring task
        asyncio.create_task(self._monitor_loop())
        logger.info("System monitoring started")
        
    async def stop_monitoring(self):
        """Stop system monitoring."""
        self.monitoring = False
        
        if self._start_memory and self._start_time:
            elapsed = time.time() - self._start_time
            current_memory = psutil.virtual_memory().used
            memory_delta = current_memory - self._start_memory
            
            logger.info(f"Recording session ended:")
            logger.info(f"  Duration: {elapsed/3600:.2f} hours")
            logger.info(f"  Memory delta: {memory_delta/1024/1024:.1f} MB")
            
    async def _monitor_loop(self):
        """Background monitoring loop."""
        while self.monitoring:
            try:
                stats = self.get_system_stats()
                
                # Log if memory usage is concerning
                if stats['memory_percent'] > 80:
                    logger.warning(f"High memory usage: {stats['memory_percent']:.1f}%")
                
                if stats['disk_percent'] > 90:
                    logger.warning(f"Low disk space: {stats['disk_percent']:.1f}% used")
                
                # Periodic info logging
                if int(time.time()) % self.log_interval == 0:
                    self._log_stats(stats)
                    
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                await asyncio.sleep(60)
                
    def get_system_stats(self) -> Dict[str, Any]:
        """Get current system statistics."""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        stats = {
            'memory_percent': memory.percent,
            'memory_available_mb': memory.available / 1024 / 1024,
            'memory_used_mb': memory.used / 1024 / 1024,
            'disk_percent': disk.percent,
            'disk_free_gb': disk.free / 1024 / 1024 / 1024,
            'cpu_percent': psutil.cpu_percent(interval=1),
            'timestamp': time.time()
        }
        
        # Add recording session info if available
        if self._start_time:
            stats['session_duration_hours'] = (time.time() - self._start_time) / 3600
            
        if self._start_memory:
            stats['memory_delta_mb'] = (memory.used - self._start_memory) / 1024 / 1024
            
        return stats
        
    def _log_stats(self, stats: Dict[str, Any]):
        """Log system statistics."""
        logger.info(f"System stats: "
                   f"RAM {stats['memory_percent']:.1f}% "
                   f"({stats['memory_available_mb']:.0f}MB free), "
                   f"Disk {stats['disk_percent']:.1f}% "
                   f"({stats['disk_free_gb']:.1f}GB free), "
                   f"CPU {stats['cpu_percent']:.1f}%")
        
        if 'session_duration_hours' in stats:
            logger.info(f"Recording session: {stats['session_duration_hours']:.2f}h, "
                       f"memory delta: {stats.get('memory_delta_mb', 0):.1f}MB")
        
    def check_available_space(self, estimated_hours: float, samplerate: int, 
                            channels: int, dtype: str = 'float32') -> Dict[str, Any]:
        """Check if enough disk space is available for estimated recording duration."""
        # Calculate bytes per second
        bytes_per_sample = 4 if dtype == 'float32' else 2  # float32 or int16
        bytes_per_second = samplerate * channels * bytes_per_sample
        
        # Estimate total size
        estimated_bytes = bytes_per_second * estimated_hours * 3600
        estimated_gb = estimated_bytes / 1024 / 1024 / 1024
        
        # Get available space
        disk = psutil.disk_usage('/')
        available_gb = disk.free / 1024 / 1024 / 1024
        
        result = {
            'estimated_size_gb': estimated_gb,
            'available_gb': available_gb,
            'sufficient_space': available_gb > (estimated_gb * 1.1),  # 10% buffer
            'estimated_duration_hours': estimated_hours,
            'max_duration_hours': (available_gb * 0.9) / (estimated_gb / estimated_hours)
        }
        
        return result