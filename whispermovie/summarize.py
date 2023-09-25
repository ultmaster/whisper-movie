import argparse
import os
from typing import cast, List, NamedTuple

import pysrt

from .openai import openai_chat
from .utils import get_logger

_logger = get_logger()


class SegmentSummary(NamedTuple):
    start: int
    end: int
    summary: str


def segment_summarize(
    start: int,
    end: int,
    transcription: str,
    prev_summaries: List[SegmentSummary],
    prompt: str,
    prompt_prev: str,
    prompt_current: str,
    timeout: float,
    max_retries: int,
) -> str:
    user_messages = [prompt_prev.format(s.start, s.end, s.summary) for s in prev_summaries] + [
        prompt_current.format(start, end, transcription)
    ]
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": "\n\n\n".join(user_messages)}]

    summarization = openai_chat(messages, timeout=timeout, max_retries=max_retries)
    _logger.info("Summarization (%d - %d): %s", start, end, summarization)
    return summarization


def map_summarize(
    subtitles: pysrt.SubRipFile,
    segment: int,
    overlap: int,
    prompt: str,
    prompt_prev: str,
    prompt_current: str,
    timeout: float,
    max_retries: int,
) -> List[SegmentSummary]:
    duration = int(subtitles[-1].end.ordinal / 1000) + 1
    current_start = 0
    summaries: List[SegmentSummary] = []
    while current_start < duration:
        current_end = min(current_start + segment, duration)
        subtitles_segment = subtitles.slice(
            starts_after={"seconds": current_start}, ends_before={"seconds": current_end}
        )
        transcription = subtitles_segment.text
        summary = segment_summarize(
            start=current_start,
            end=current_end,
            transcription=transcription,
            prev_summaries=summaries,
            prompt=prompt,
            prompt_prev=prompt_prev,
            prompt_current=prompt_current,
            timeout=timeout,
            max_retries=max_retries,
        )
        summaries.append(SegmentSummary(start=current_start, end=current_end, summary=summary))
        current_start += segment - overlap
    return summaries


def reduce_summarize(
    summaries: List[SegmentSummary],
    prompt_prev: str,
    prompt_reduce: str,
    timeout: float,
    max_retries: int,
) -> str:
    user_messages = [prompt_prev.format(s.start, s.end, s.summary) for s in summaries]
    messages = [{"role": "system", "content": prompt_reduce}, {"role": "user", "content": "\n\n\n".join(user_messages)}]

    summarization = openai_chat(messages, timeout=timeout, max_retries=max_retries)
    _logger.info("Summarization (reduce): %s", summarization)
    return summarization


def main():
    parser = argparse.ArgumentParser("Summarize a subtitle file")

    parser.add_argument("input_file", type=str, help="The input subtitle file")
    parser.add_argument(
        "--prompt",
        type=str,
        help="Prompt for writing summaries. You can put the description of the subtitle / video here.",
        default="Your task is to write a summary of a video. A transcription of the video will be given by the user.",
    )
    parser.add_argument(
        "--prompt-prev",
        type=str,
        help="Prompt for previous summary.",
        default="Here is the summary of the video from {} seconds to {} seconds:\n\n{}",
    )
    parser.add_argument(
        "--prompt-current",
        type=str,
        help="Prompt for next summary.",
        default="Here is the transcription of the video from {} seconds to {} seconds. Please write a summary of this clip:\n\n{}",
    )
    parser.add_argument(
        "--prompt-reduce",
        type=str,
        help="Prompt for summary of summary. Only used when the video is too long and divided into multiple summaries.",
        default="Please write a summary of the full video.",
    )
    parser.add_argument(
        "--segment", "-s", type=int, default=600, help="The segment to summarize. Defaults to 600 seconds."
    )
    parser.add_argument(
        "--overlap", "-lap", type=int, default=60, help="Length of overlap between segments in seconds."
    )
    parser.add_argument("--timeout", default=60.0, type=float, help="Timeout of OpenAI requests.")
    parser.add_argument("--max-retries", default=0, type=int, help="Max retries of OpenAI requests.")

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        raise RuntimeError(f"File {args.input_file} does not exist.")

    subtitle = pysrt.open(args.input_file)
    summaries = map_summarize(
        subtitle,
        args.segment,
        args.overlap,
        args.prompt,
        args.prompt_prev,
        args.prompt_current,
        args.timeout,
        args.max_retries,
    )
    if len(summaries) == 1:
        final_summary = summaries[0].summary
    else:
        final_summary = reduce_summarize(
            summaries, args.prompt_prev, args.prompt_reduce, args.timeout, args.max_retries
        )

    print("Summary:")
    print(final_summary)


if __name__ == "__main__":
    main()
