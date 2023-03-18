import argparse
import os
import subprocess
from pathlib import Path
from typing import BinaryIO, Iterator, Tuple, List, cast

import requests
import pysrt

from .utils import get_logger

_logger = get_logger()


def translate(audio_file: BinaryIO, prompt: str, response_format: str = "srt") -> str:
    """Translate audio to text.

    Args:
        audio_file (BinaryIO): The audio file to translate.
        prompt (str): The prompt to use for translation.
        response_format (str, optional): The format of the response. Defaults to "srt".

    Returns:
        str: The translated text.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key is None:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    model = "whisper-1"
    response = requests.post(
        "https://api.openai.com/v1/audio/translations",
        data={
            "model": model,
            "prompt": prompt,
            "response_format": response_format,
        },
        files={"file": audio_file},
        headers={"Authorization": "Bearer " + api_key}
    )
    if response.status_code != 200:
        raise RuntimeError(f"Error translating audio: {response.text}")
    return response.text


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
                  segment_length: int, overlap: int) -> Iterator[Tuple[Path, int, int]]:
    """Segment an audio file into segments of length segment_length with overlap overlap.

    Args:
        audio_path (Path): Path to the audio file to segment.
        segment_length (int): Length of each segment in seconds.
        overlap (int): Length of overlap between segments in seconds.
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

    pysrt.SubRipFile(merged_subtitles_wo_duplicates).save(output_path)


def segment_and_translate(audio_path: Path, main_directory: Path,
                          segment_length: int, overlap: int, prompt: str,
                          delete_duplicates: int, reuse: bool) -> None:
    """Segment an audio file and translate each segment.
    Results are saved in the main_directory.

    Args:
        audio_path (Path): Path to the audio file to segment and translate.
        main_directory (Path): Path to the main directory where results will be saved.
        segment_length (int): Length of each segment in seconds.
        overlap (int): Length of overlap between segments in seconds.
        prompt (str): Prompt to use for translation.
        delete_duplicates (int): Number of consecutive duplicate subtitles to delete.
        reuse (bool): Whether to reuse existing translation files.
    """
    translations: List[Tuple[Path, int, int]] = []
    for segment_path, start, end in segment_audio(audio_path, main_directory, segment_length, overlap):
        translated_path = main_directory / f"{start:05d}-{end:05d}.srt"
        if reuse and translated_path.exists():
            _logger.info("Translation already exists: %s", translated_path)
        else:
            _logger.info("Using whisper to translate %s", segment_path)
            with segment_path.open("rb") as f:
                response = translate(f, prompt)
                translated_path.write_text(response)
                _logger.info("Translation saved: %s", translated_path)
        translations.append((translated_path, start, end))

    merge_path = main_directory / "merged.srt"
    _logger.info("Merging subtitles into %s", merge_path)
    merge_subtitles(translations, merge_path, delete_duplicates)


def main():
    parser = argparse.ArgumentParser("Translate audio to srt subtitles.")
    parser.add_argument("input", type=str, help="Path to audio file to be processed.")
    parser.add_argument("--output", "-o", type=str, default="outputs", help="Path to output directory.")
    parser.add_argument("--prompt", "-p", type=str, default="", help="Prompt to use for translation.")
    parser.add_argument("--segment", "-s", type=int, default=600, help="Length of each segments in seconds.")
    parser.add_argument("--overlap", "-lap", type=int, default=60,
                        help="Length of overlap between segments in seconds.")
    parser.add_argument("--delete-duplicates", type=int, default=3,
                        help="Number of consecutive duplicate subtitles to delete. "
                             "Useful for removing false positive of silence. Setting to 0 to disable.")
    parser.add_argument("--reuse", default=False, action="store_true", help="Whether to reuse existing files.")
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

    main_directory = Path(args.output)
    main_directory.mkdir(parents=True, exist_ok=True)
    segment_and_translate(audio_path, main_directory,
                          args.segment, args.overlap, args.prompt, args.delete_duplicates, args.reuse)


if __name__ == "__main__":
    main()
