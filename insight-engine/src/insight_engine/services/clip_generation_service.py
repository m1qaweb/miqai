"""Service for generating video clips."""

import os
import ffmpeg
from pathlib import Path
from typing import List, Tuple


class ClipGenerationError(Exception):
    """Custom exception for clip generation failures."""

    pass


def generate_clips(
    video_path: str, timestamps: List[Tuple[float, float]], output_dir: str = "clips"
) -> List[str]:
    """
    Generates video clips from a source video file based on timestamps.

    Args:
        video_path: The path to the source video file.
        timestamps: A list of tuples, where each tuple contains the
                    start and end time (in seconds) of a clip.
        output_dir: The directory where the generated clips will be saved.

    Returns:
        A list of paths to the generated clips.

    Raises:
        ClipGenerationError: If the video file does not exist or if ffmpeg fails.
    """
    # Sanitize the video path to prevent path traversal attacks
    safe_filename = os.path.basename(video_path)
    video_file = Path(safe_filename)

    if not video_file.exists():
        raise ClipGenerationError(f"Video file not found: {safe_filename}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    base_name = video_file.stem

    for i, (start_time, end_time) in enumerate(timestamps):
        output_filename = f"{base_name}_clip_{i+1}.mp4"
        output_filepath = output_path / output_filename

        try:
            (
                ffmpeg.input(str(video_file), ss=start_time)
                .output(str(output_filepath), to=end_time, c="copy")
                .run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
            )
            clip_paths.append(str(output_filepath))
            print(f"Successfully generated clip: {output_filepath}")
        except ffmpeg.Error as e:
            error_message = e.stderr.decode()
            raise ClipGenerationError(
                f"Failed to generate clip for timestamp {start_time}-{end_time}: {error_message}"
            )

    return clip_paths
