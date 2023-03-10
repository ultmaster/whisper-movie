# Whipser Movie

Generate subtitles for long movies / podcasts with OpenAI Whisper API.

This tool is built upon [OpenAI Whisper](https://platform.openai.com/docs/guides/speech-to-text) (official documentation by OpenAI is [here](https://platform.openai.com/docs/guides/speech-to-text)). Although Whisper is a powerful speech-to-text / translation tool, it lacks support for long videos, which is a problem for transcription of movies, podcasts, meeting records, TV shows, and anything longer than a couple of minutes.

This repository has only supported basic translation of long media files (either video or audio). More features and performance enhancements are still under development. Due to the limitation of API provided by OpenAI, English is the only supported language to translate to.

## Features and TODOs

- [x] Support translating very long / large media files.
- [ ] Support both pure transcription (without translation).
- [ ] Auto-translate to other languages with Google translate.
- [ ] Detect split point on silence.
- [ ] Use prompt to enrich context information.
- [ ] Detect vocals for movies with music / sound effects.

## Prerequisite

* OpenAI account
* Python >= 3.7
* ffmpeg
* ffprobe

## Install

Clone this repository and run:

```bash
pip install -e .
```

## Quickstart

```bash
export OPENAI_API_KEY=sk-xxx
python -m whispermovie.translate /path/to/long_audio.mp3
```

See `python -m whispermovie.translate -h` for more command line options.

This tool invokes OpenAI API and the requirements for local computing resources is minumum (you don't need a GPU!). The price of OpenAI API is currently [$0.006 per minute](https://openai.com/pricing), which sums up to about 0.72 dollar for a 2-hour movie.

## Example

I downloaded [this video](https://www.youtube.com/watch?v=kFtrvdriLU8), and transcribed it. The results look like this:

```
1
00:00:00,000 --> 00:00:04,800
We use a new voice recognition system called Whisper

2
00:00:04,800 --> 00:00:06,600
Because Whisper is a free software

3
00:00:06,600 --> 00:00:09,680
It is a completely free and authorized

4
00:00:09,680 --> 00:00:12,680
Everyone can download it and run it by themselves

5
00:00:12,680 --> 00:00:15,180
If you haven't used Whisper, you must try it

6
00:00:15,180 --> 00:00:16,480
《Walk & Fish》

7
00:00:17,280 --> 00:00:19,120
Hello everyone, this is Walk & Fish

8
00:00:19,120 --> 00:00:22,180
This video should be released on the first day of the new year

9
00:00:22,180 --> 00:00:23,920
So here is a New Year's greeting to everyone

10
00:00:23,920 --> 00:00:25,360
Happy New Year

11
00:00:25,360 --> 00:00:29,300
In the next year, we will discover more fun and practical computer knowledge

12
00:00:29,300 --> 00:00:30,360
Back to the topic

13
00:00:30,360 --> 00:00:32,200
As you can see at the beginning of the video

14
00:00:32,200 --> 00:00:34,800
Last week in a podcast I often listen to

15
00:00:34,800 --> 00:00:36,800
Nice Lemon

16
00:00:36,800 --> 00:00:40,840
I learned that OpenAI actually released an AI technology last year

17
00:00:40,840 --> 00:00:43,440
Just compared to ChatGPT, Dolly2, etc.

18
00:00:43,440 --> 00:00:44,480
The attention is lower

19
00:00:44,480 --> 00:00:47,680
It's the voice recognition AI called Whisper

20
00:00:47,680 --> 00:00:51,680
Whisper is quite good in the data provided by OpenAI

4
00:00:51,600 --> 00:00:55,000
Spanish and English mispronunciation rates are lower than 5%

5
00:00:55,000 --> 00:00:58,840
Basically, the ability to recognize humans has reached a similar level

6
00:00:58,840 --> 00:01:03,080
Although the mispronunciation rate of Chinese is close to 15%, it looks quite high

7
00:01:03,080 --> 00:01:07,000
But considering that Chinese is a bunch of the same words, the feeling should be fine

8
00:01:07,000 --> 00:01:10,080
At present, I tested that the recognition effect is quite good

9
00:01:10,080 --> 00:01:14,160
Even better than the subtitle editing software that many people use to upload subtitles

10
00:01:14,160 --> 00:01:16,800
The correctness rate of the subtitles obtained is even higher

11
00:01:16,800 --> 00:01:20,840
This point will be provided in the following video

12
00:01:20,840 --> 00:01:25,160
And more importantly, Whisper is an open-source voice recognition system

13
00:01:25,160 --> 00:01:27,720
What is in its program? Everyone can see

14
00:01:27,720 --> 00:01:30,720
And Whisper can run completely on your own computer

...
```
