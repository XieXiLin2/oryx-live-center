"""Transcode worker - executes transcoding tasks."""

import asyncio
import subprocess
from typing import Dict, Optional, Any
from datetime import datetime

from app.protocols import ProtocolConverter


class TranscodeWorker:
    """Worker that executes transcoding tasks."""

    def __init__(self, config: dict):
        self.config = config
        self.tasks: Dict[int, subprocess.Popen] = {}
        self.use_gpu = config.get("ffmpeg", {}).get("gpu_acceleration", False)

    async def start_task(self, task_id: int, task_config: dict):
        """Start a transcoding task."""
        try:
            # Build FFmpeg command
            cmd = self._build_ffmpeg_command(task_config)

            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.tasks[task_id] = process

            # Monitor process output
            asyncio.create_task(self._monitor_process(task_id, process))

            return {"status": "started", "task_id": task_id}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def stop_task(self, task_id: int):
        """Stop a transcoding task."""
        if task_id not in self.tasks:
            return {"status": "not_found"}

        process = self.tasks[task_id]
        process.terminate()

        await asyncio.sleep(2)

        if process.poll() is None:
            process.kill()

        del self.tasks[task_id]
        return {"status": "stopped"}

    def get_task_status(self, task_id: int) -> dict:
        """Get task status."""
        if task_id not in self.tasks:
            return {"status": "not_found"}

        process = self.tasks[task_id]
        if process.poll() is None:
            return {"status": "running"}
        else:
            return {"status": "stopped", "exit_code": process.returncode}

    def _build_ffmpeg_command(self, task_config: dict) -> list:
        """Build FFmpeg command from task configuration."""
        source_protocol = task_config["source_protocol"]
        source_url = task_config["source_url"]
        outputs = task_config["outputs"]

        # For multiple outputs, we need to use FFmpeg's tee muxer or multiple output syntax
        if len(outputs) == 1:
            output = outputs[0]
            return self._build_single_output_command(
                source_protocol, source_url, output
            )
        else:
            return self._build_multi_output_command(
                source_protocol, source_url, outputs
            )

    def _build_single_output_command(
        self, source_protocol: str, source_url: str, output: dict
    ) -> list:
        """Build command for single output."""
        output_protocol = output["protocol"]
        output_url = output["url"]
        resolution = output.get("resolution", "1920x1080")
        bitrate = output.get("bitrate", "6000k")
        fps = output.get("fps", 30)

        if source_protocol == "rtmp" and output_protocol == "webrtc":
            return ProtocolConverter.rtmp_to_webrtc(
                source_url, output_url, resolution, bitrate, fps, self.use_gpu
            )
        elif source_protocol == "srt" and output_protocol == "rtmp":
            return ProtocolConverter.srt_to_rtmp(source_url, output_url)
        elif source_protocol == "whip" and output_protocol == "rtmp":
            return ProtocolConverter.whip_to_rtmp(
                source_url, output_url, resolution, bitrate, fps, self.use_gpu
            )
        elif source_protocol == "rtmp" and output_protocol == "flv":
            return ProtocolConverter.rtmp_to_flv(
                source_url, output_url, resolution, bitrate, fps, self.use_gpu
            )
        else:
            raise ValueError(f"Unsupported conversion: {source_protocol} -> {output_protocol}")

    def _build_multi_output_command(
        self, source_protocol: str, source_url: str, outputs: list
    ) -> list:
        """Build command for multiple outputs."""
        cmd = [
            "ffmpeg",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-i", source_url,
        ]

        # Add each output
        for output in outputs:
            resolution = output.get("resolution", "1920x1080")
            bitrate = output.get("bitrate", "6000k")
            fps = output.get("fps", 30)
            output_url = output["url"]

            if self.use_gpu:
                cmd.extend([
                    "-c:v", "h264_nvenc",
                    "-preset", "p1",
                    "-tune", "ll",
                    "-zerolatency", "1",
                ])
            else:
                cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-tune", "zerolatency",
                ])

            cmd.extend([
                "-g", str(fps),
                "-sc_threshold", "0",
                "-bf", "0",
                "-b:v", bitrate,
                "-maxrate", bitrate,
                "-bufsize", f"{int(bitrate.rstrip('k')) * 2}k",
                "-s", resolution,
                "-r", str(fps),
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "48000",
                "-f", "rtmp",
                output_url,
            ])

        return cmd

    async def _monitor_process(self, task_id: int, process: subprocess.Popen):
        """Monitor process output and status."""
        while True:
            if process.poll() is not None:
                break

            await asyncio.sleep(1)

        # Process has exited
        if task_id in self.tasks:
            del self.tasks[task_id]
