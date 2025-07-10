import asyncio
import ffmpeg


class ClipGenerator:
    """A service for generating video clips using ffmpeg-python."""

    async def generate_clip(
        self, video_uri: str, start_time: float, end_time: float, output_path: str
    ) -> None:
        """Generates a video clip from a source video file.

        Args:
            video_uri: The URI of the source video.
            start_time: The start time of the clip in seconds.
            end_time: The end time of the clip in seconds.
            output_path: The path where the generated clip will be saved.

        Raises:
            ValueError: If there is an error during clip generation.
        """
        try:
            duration = end_time - start_time
            stream = ffmpeg.input(video_uri)
            stream = ffmpeg.output(
                stream, output_path, ss=start_time, t=duration, c="copy"
            )

            process = await asyncio.create_subprocess_exec(
                *ffmpeg.compile(stream, overwrite_output=True),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise ffmpeg.Error("ffmpeg", stdout, stderr)

        except ffmpeg.Error as e:
            raise ValueError(f"Error generating clip: {e.stderr.decode()}") from e