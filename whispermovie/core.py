import argparse
import subprocess
import shutil
from pathlib import Path
from typing import Iterator, Tuple, List, Optional, cast

import pysrt

from .openai import openai_audio
from .utils import get_logger

_logger = get_logger()


def get_duration(media_path: Path) -> float:
    """Get the duration of a media file.

    Args:
        media_path (Path): Path to the media file.

    Returns:
        float: The duration of the media file in seconds.
    """
    _logger.info("Getting duration of media file %s", media_path)
    result = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                      "format=duration", "-of",
                                      "default=noprint_wrappers=1:nokey=1", str(media_path)])
    return float(result.decode())


def clip_audio(audio_path: Path, start: int, end: int, output_path: Path) -> None:
    """Clip an audio file.

    Args:
        audio_path (Path): Path to the audio file to clip.
        start (int): Start time in seconds.
        end (int): End time in seconds.
        output_path (Path): Path to the output file.
    """
    _logger.info("Clipping audio file %s from %d to %d and saving to %s",
                 audio_path, start, end, output_path)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(audio_path), "-ss", str(start), "-to",
                    str(end), "-ab", "192k", "-f", "mp3", str(output_path)], check=True)
    _logger.info("Audio segment saved: %s", output_path)


def segment_audio(audio_path: Path, output_directory: Path,
                  segment_length: int, overlap: int, reuse: bool) -> Iterator[Tuple[Path, int, int]]:
    """Segment an audio file into segments of length segment_length with overlap overlap.

    Args:
        audio_path (Path): Path to the audio file to segment.
        segment_length (int): Length of each segment in seconds.
        overlap (int): Length of overlap between segments in seconds.
        reuse (bool): Whether to reuse existing segments.
    """
    _logger.info("Segmenting audio file %s into segments of length %d with overlap %d",
                 audio_path, segment_length, overlap)

    duration = get_duration(audio_path)
    _logger.info("Duration of audio file: %f seconds", duration)
    start = 0
    while start < duration:
        end = start + segment_length
        if end + 1 > duration:
            # Last 1 second.
            end = int(duration + 1)  # Add 1 to be safe.
        output_path = output_directory / f"{start:05d}-{end:05d}.mp3"
        if reuse and output_path.exists():
            _logger.info('Reuse generated audio: %s', output_path)
        else:
            clip_audio(audio_path, start, end, output_path)
        yield output_path, start, end
        if end >= duration:
            break
        start += segment_length - overlap


def merge_subtitles(subtitle_segments: List[Tuple[Path, int, int]], output_path: Path, delete_duplicates: int) -> None:
    """Merge subtitles into a single file.

    Args:
        subtitle_segments (List[Tuple[Path, int, int]]): List of subtitle files to merge.
        output_path (Path): Path to the output file.
        delete_duplicates (int): Number of consecutive duplicate subtitles to delete.
    """
    merged_subtitles: List[pysrt.SubRipItem] = []

    # The real split position is the middle of current segment end and next segment start.
    real_segments: List[Tuple[int, int]] = []
    for i in range(len(subtitle_segments)):
        if i + 1 == len(subtitle_segments):
            segment_end = subtitle_segments[i][2]
        else:
            segment_end = (subtitle_segments[i][2] + subtitle_segments[i + 1][1]) // 2

        if i == 0:
            segment_start = subtitle_segments[i][1]
        else:
            segment_start = (subtitle_segments[i][1] + subtitle_segments[i - 1][2]) // 2

        real_segments.append((segment_start, segment_end))

    for (subtitle_path, segment_start, segment_end), (valid_start, valid_end) in zip(subtitle_segments, real_segments):
        _logger.info("Merging subtitle %s into %s, used segment: %d - %d",
                     subtitle_path, output_path, valid_start, valid_end)
        subtitle = pysrt.open(subtitle_path)
        for sub in subtitle:
            sub = cast(pysrt.SubRipItem, sub)
            start_in_seconds = sub.start.ordinal / 1000 + segment_start
            if not valid_start <= start_in_seconds < valid_end:
                continue
            sub.shift(seconds=segment_start)
            merged_subtitles.append(sub)

    # Delete consecutive duplicate subtitles.
    merged_subtitles_wo_duplicates: List[pysrt.SubRipItem] = []
    i, j = 0, 0
    while i < len(merged_subtitles):
        j = i + 1
        while j < len(merged_subtitles) and merged_subtitles[i].text == merged_subtitles[j].text:
            j += 1

        if j - i >= delete_duplicates:
            # More than delete_duplicates subtitles are same. Something must be wrong.
            # Throw away all of them.
            _logger.info("%d subtitles are same. Deleted: %s", j - i, merged_subtitles[i].text)
        else:
            merged_subtitles_wo_duplicates.extend(merged_subtitles[i:j])

        i = j

    _logger.info("Writing final results to: %s", output_path)
    pysrt.SubRipFile(merged_subtitles_wo_duplicates).save(output_path)


def segment_and_process(mode: str, audio_path: Path, progress_directory: Path, output_path: Path,
                        segment_length: int, overlap: int, prompt: str,
                        delete_duplicates: int, reuse: bool,
                        timeout: float, max_retries: int,
                        language: Optional[str] = None) -> None:
    """Segment an audio file and process each segment.
    Results are saved in the progress_directory.

    Args:
        mode (str): The mode of the request. Can be "translations" or "transcriptions".
        audio_path (Path): Path to the audio file to segment and process.
        progress_directory (Path): Path to the main directory where results will be saved.
        output_path (Path): Path to the output file.
        segment_length (int): Length of each segment in seconds.
        overlap (int): Length of overlap between segments in seconds.
        prompt (str): Prompt to use for translation / transcription.
        delete_duplicates (int): Number of consecutive duplicate subtitles to delete.
        reuse (bool): Whether to reuse existing subtitle files.
        timeout (float): The timeout for OpenAI requests.
        max_retries (int): The maximum number of OpenAI request retries.
        language (str, optional): The language of the transcription. Defaults to None. Only useful when mode is "transcriptions".
    """
    if mode not in ["translations", "transcriptions"]:
        raise ValueError(f"Invalid mode: {mode}, should be one of 'translations', 'transcriptions'")

    _logger.info("Mode: %s", mode)

    subtitles: List[Tuple[Path, int, int]] = []
    for segment_path, start, end in segment_audio(audio_path, progress_directory, segment_length, overlap, reuse):
        subtitle_path = progress_directory / f"{start:05d}-{end:05d}.srt"
        if reuse and subtitle_path.exists():
            _logger.info("Subtitle already exists: %s", subtitle_path)
        else:
            _logger.info("Using whisper to translate / transcribe %s", segment_path)
            with segment_path.open("rb") as f:
                response = openai_audio(f, prompt, mode=mode, timeout=timeout, max_retries=max_retries)
                subtitle_path.write_text(response, encoding="utf-8", errors="replace")
                _logger.info("Subtitle saved: %s", subtitle_path)
        subtitles.append((subtitle_path, start, end))

    _logger.info("Merging subtitles into %s", output_path)
    merge_subtitles(subtitles, output_path, delete_duplicates)


def main(mode: str):
    parser = argparse.ArgumentParser("Translate / transcribe audio to srt subtitles.")
    parser.add_argument("input", type=str, help="Path to audio file to be processed.")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Path to output. A *.progress directory and a *.srt file will be created. By default, it's same as input.")
    parser.add_argument("--keep-progress", default=False, action="store_true",
                        help="Whether to keep the progress directory at the end.")
    parser.add_argument("--prompt", "-p", type=str, default="", help="Prompt to use for translation / transcription.")
    parser.add_argument("--segment", "-s", type=int, default=600, help="Length of each segments in seconds.")
    parser.add_argument("--overlap", "-lap", type=int, default=60,
                        help="Length of overlap between segments in seconds.")
    parser.add_argument("--delete-duplicates", type=int, default=3,
                        help="Number of consecutive duplicate subtitles to delete. "
                             "Useful for removing false positive of silence. Setting to 0 to disable.")
    parser.add_argument("--reuse", default=False, action="store_true", help="Whether to reuse existing files.")
    parser.add_argument("--timeout", default=60., type=float, help="Timeout of OpenAI requests.")
    parser.add_argument("--max-retries", default=0, type=int, help="Max retries of OpenAI requests.")
    parser.add_argument("--language", type=str, default=None, help="Language of the transcription, in ISO 639-1 format.")
    args = parser.parse_args()

    audio_path = Path(args.input)
    if not audio_path.exists():
        raise ValueError(f"Input file {audio_path} does not exist.")
    if args.segment < 10:
        raise ValueError("segment must be at least 10 seconds.")
    if args.overlap < 0 or args.overlap >= args.segment:
        raise ValueError("overlap must be at least 0 and less than segment.")
    if args.delete_duplicates <= 1:
        raise ValueError("delete_duplicates must be at least 2 or zero.")

    if args.output is None:
        args.output = Path(args.input)

    progress_directory = Path(args.output).parent / (Path(args.output).stem + ".progress")
    output_path = Path(args.output).parent / (Path(args.output).stem + ".srt")
    progress_directory.mkdir(parents=True, exist_ok=True)
    segment_and_process(mode, audio_path, progress_directory, output_path,
                        args.segment, args.overlap, args.prompt, args.delete_duplicates, args.reuse,
                        args.timeout, args.max_retries, args.language)
    if not args.keep_progress:
        shutil.rmtree(progress_directory)
