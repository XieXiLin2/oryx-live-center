"""Resource monitoring for transcode node."""

import asyncio
import psutil
from typing import Dict, Any


class ResourceMonitor:
    """Monitor system resources (CPU, memory, GPU)."""

    def __init__(self):
        self.gpu_available = self._check_gpu()

    def _check_gpu(self) -> bool:
        """Check if NVIDIA GPU is available."""
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get current resource metrics."""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        metrics = {
            "cpu_usage": cpu_percent,
            "memory_usage": memory_percent,
            "gpu_usage": None,
        }

        if self.gpu_available:
            try:
                import subprocess
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    metrics["gpu_usage"] = float(result.stdout.strip())
            except Exception:
                pass

        return metrics
