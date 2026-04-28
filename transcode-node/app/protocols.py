"""Protocol conversion logic for transcoding."""

from typing import List


class ProtocolConverter:
    """Protocol converter for different streaming protocols."""

    @staticmethod
    def rtmp_to_webrtc(
        input_url: str,
        output_url: str,
        resolution: str,
        bitrate: str,
        fps: int = 30,
        use_gpu: bool = False,
    ) -> List[str]:
        """Convert RTMP to WebRTC (using Opus audio)."""
        cmd = [
            "ffmpeg",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-i", input_url,
        ]

        if use_gpu:
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
            "-g", str(fps * 2),
            "-sc_threshold", "0",
            "-bf", "0",
            "-b:v", bitrate,
            "-maxrate", bitrate,
            "-bufsize", f"{int(bitrate.rstrip('k')) * 2}k",
            "-s", resolution,
            "-r", str(fps),
            "-c:a", "libopus",
            "-b:a", "128k",
            "-ar", "48000",
            "-f", "rtmp",
            output_url,
        ])

        return cmd

    @staticmethod
    def srt_to_rtmp(input_url: str, output_url: str) -> List[str]:
        """Convert SRT to RTMP (copy codec, no transcoding)."""
        return [
            "ffmpeg",
            "-fflags", "nobuffer",
            "-i", input_url,
            "-c", "copy",
            "-f", "rtmp",
            output_url,
        ]

    @staticmethod
    def whip_to_rtmp(
        input_url: str,
        output_url: str,
        resolution: str,
        bitrate: str,
        fps: int = 30,
        use_gpu: bool = False,
    ) -> List[str]:
        """Convert WebRTC (WHIP) to RTMP."""
        cmd = [
            "ffmpeg",
            "-protocol_whitelist", "file,udp,rtp",
            "-i", input_url,
        ]

        if use_gpu:
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
            "-s", resolution,
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "48000",
            "-f", "rtmp",
            output_url,
        ])

        return cmd

    @staticmethod
    def rtmp_to_flv(
        input_url: str,
        output_url: str,
        resolution: str,
        bitrate: str,
        fps: int = 30,
        use_gpu: bool = False,
    ) -> List[str]:
        """Convert RTMP to HTTP-FLV."""
        cmd = [
            "ffmpeg",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-i", input_url,
        ]

        if use_gpu:
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
