# One Cut - Edit Video by Editing Code

One Cut will transcribe your video using [fast-whisper](https://github.com/SYSTRAN/faster-whisper) and 
generate a python code like [example.py](http://link). The code contains all the subtitles from ASR and
allows you modify the video by changing the code.

Run onecut to transcribe your video:

```bash
uv run onecut path/to/your/video.mp4
```

The OneCut cli will generate code like this. You can easily fix ASR error by changing the text.

```python
movie = Movie("a.txt", [])
SUB_1 = sub("Sub1", 0, 1)
SUB_2 = sub("Sub2", 1, 2)
SUB_3 = sub("Sub3", 2, 3)

FINAL_CLIPS = [SUB_1.to(SUB_3)]
```

You can cut one section of your video (Like SUB_2) by doing this.

```python
FINAL_CLIPS = [SUB_1, SUB_3]
```

Or use helper function to cut it, the function is super useful if you only want to remove a portion of it.

```python
remove_subs(movie.all_subtitles, [SUB_2])
```

After finish cutting & fixing, just run `python {generated_file}.py` to generate the final video and subtitile(.srt) file.


## Dependency

1. Python 3
2. ffmpeg

The generated file is self-contained, it does not depend on the onecut pacakge, the only dependency is ffmpeg.

## Why?

I want to share some of my videos but the only computer I have is a steamdeak. Running any modern video editors will
kill my steamdeak and It's super laggy as well. There are some online services like [descript](https://www.descript.com/)
but I don't want to upload the video over my slow interenet and pay 12$ per month.

Also, the coding agent is very good at spotting ASR errors and I want to generate something for them to work on. All the
existing tools are based on text but I think using code as intermediate representation is much better for coding agent.

## Agent Edit

Most of the time, I just ask agent to fix the ASR error in `generated.py` and It will think for a long time and fix most of the
ASR issues. You can ask agent to do additional things like:

1. Burn-in the subtitles.
2. Remove part of video.
3. Only export part of the video.

Basically, the angents can do anything that supported by [ffmpeg filter](https://ffmpeg.org/ffmpeg-filters.html).

Using Deepseek-V4 Flash, fixing all the ASR errors cost about 0.1 dollar in API pricing.

## Future Plans

1. Support Word Level Editing: I don't know what's the best way to support that since I don't want to put a lot of timestamps in the code.
2. Bugfix

## LLM Usage

This project is written in the old-fashion way, LLM is used for data collection and some debugging.
