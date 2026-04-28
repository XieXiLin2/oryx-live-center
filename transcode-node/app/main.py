"""Transcode node main application."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.monitor import ResourceMonitor
from app.worker import TranscodeWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load configuration
with open("config.yaml") as f:
    config = yaml.safe_load(f)

app = FastAPI(title="Transcode Node")
monitor = ResourceMonitor()
worker = TranscodeWorker(config)


class TaskStartRequest(BaseModel):
    task_id: int
    source_protocol: str
    source_url: str
    outputs: list


class TaskStopRequest(BaseModel):
    task_id: int


@app.on_event("startup")
async def startup():
    """Register node with manager and start heartbeat."""
    logger.info(f"Starting transcode node: {config['node']['id']}")

    # Register with manager
    try:
        await register_node()
        logger.info("Registered with manager")
    except Exception as e:
        logger.error(f"Failed to register with manager: {e}")

    # Start heartbeat task
    asyncio.create_task(heartbeat_loop())


async def register_node():
    """Register this node with the manager."""
    manager_url = config["manager"]["url"]
    api_key = config["manager"].get("api_key")

    node_data = {
        "id": config["node"]["id"],
        "name": config["node"]["name"],
        "region": config["node"]["region"],
        "max_tasks": config["node"]["max_tasks"],
        "capabilities": {
            "protocols": ["rtmp", "srt", "whip"],
            "codecs": ["h264"],
            "gpu": config["ffmpeg"].get("gpu_acceleration", False),
        },
    }

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{manager_url}/api/admin/transcode/nodes/register",
            json=node_data,
            headers=headers,
            timeout=10.0,
        )
        response.raise_for_status()


async def heartbeat_loop():
    """Send periodic heartbeat to manager."""
    manager_url = config["manager"]["url"]
    node_id = config["node"]["id"]
    interval = config["manager"]["heartbeat_interval"]

    while True:
        try:
            await asyncio.sleep(interval)

            metrics = monitor.get_metrics()
            heartbeat_data = {
                "cpu_usage": metrics["cpu_usage"],
                "memory_usage": metrics["memory_usage"],
                "gpu_usage": metrics["gpu_usage"],
                "current_tasks": len(worker.tasks),
                "network_latency": None,  # TODO: measure latency to SRS
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{manager_url}/api/admin/transcode/nodes/{node_id}/heartbeat",
                    json=heartbeat_data,
                    timeout=10.0,
                )
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "node_id": config["node"]["id"]}


@app.post("/tasks/start")
async def start_task(request: TaskStartRequest):
    """Start a transcoding task."""
    task_config = {
        "source_protocol": request.source_protocol,
        "source_url": request.source_url,
        "outputs": request.outputs,
    }

    result = await worker.start_task(request.task_id, task_config)
    return result


@app.post("/tasks/stop")
async def stop_task(request: TaskStopRequest):
    """Stop a transcoding task."""
    result = await worker.stop_task(request.task_id)
    return result


@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: int):
    """Get task status."""
    status = worker.get_task_status(task_id)
    return status


@app.get("/metrics")
async def get_metrics():
    """Get node metrics."""
    metrics = monitor.get_metrics()
    metrics["current_tasks"] = len(worker.tasks)
    metrics["max_tasks"] = config["node"]["max_tasks"]
    return metrics


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
