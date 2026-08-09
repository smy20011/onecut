# One Cut - Edit Video by Editing Code

One Cut will transcribe your video using [fast-whisper](https://github.com/SYSTRAN/faster-whisper) and 
generate Python code like [example.py](https://github.com/smy20011/onecut/blob/main/src/onecut/example.py). 
The code contains all the subtitles from ASR and allows you to modify the video by changing the code.

Run onecut to transcribe your video:

```bash
uvx onecut path/to/your/video.mp4
```

The OneCut CLI will generate code like this. You can easily fix ASR errors by changing the text.

```python
movie = Movie("a.txt", [])
SUB_1 = sub("Sub1", 0, 1)
SUB_2 = sub("Sub2", 1, 2)
SUB_3 = sub("Sub3", 2, 3)

FINAL_CLIPS = [SUB_1.to(SUB_3)]
```

You can cut one section of your video (like SUB_2) by doing this.

```python
FINAL_CLIPS = [SUB_1, SUB_3]
```

Or use the helper function to cut it, the function is super useful if you only want to remove a small portion of clips.

```python
FINAL_CLIPS = remove_subs(movie.all_subtitles, [SUB_2])
```

After finishing cutting & fixing, just run `python {generated_file}.py` to generate the final video and subtitle(.srt) file.


## Dependencies

1. Python 3
2. FFmpeg

The generated file is self-contained. It does not depend on the onecut package. The only dependency is ffmpeg.

## Why?

I want to share some of my videos but the only computer I have is a Steamdeak. Running any modern video editors will
kill my Steamdeak and it's super laggy as well. There are some online services like the [Descript](https://www.descript.com/)
but I don't want to upload the video over my slow internet and pay $12 per month.

Also, the coding agent is very good at spotting ASR errors and I want to generate something for them to work on. All the
existing tools are based on text but I think using code as intermediate representation is much better for coding agents.

## Agent Edit

Most of the time, I just ask the agent to fix the ASR errors in `generated.py` and it will think for a long time and fix most of the
ASR issues. You can ask the agent to do additional things like:

1. Burn-in the subtitles.
2. Remove part of video.
3. Only export part of the video.

Basically, the agents can do anything supported by the [FFmpeg filter](https://ffmpeg.org/ffmpeg-filters.html).

Using Deepseek-V4 Flash, fixing all the ASR errors costs about $0.1 in API pricing.

## Future Plans

1. Support Word Level Editing: I don't know what's the best way to support that since I don't want to put a lot of timestamps in the code.
2. Bugfix

## LLM Usage

This project is written in the old-fashioned way. LLM is used for data collection and some debugging.
