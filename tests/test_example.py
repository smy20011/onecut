import pytest
from onecut.example import *


def test_ffmpeg_filter():
    clips = [SUB_1, SUB_3]
    assert (
        ffmpeg_filter(clips)
        == """
[0:v]trim=0.00:1.00,setpts=PTS-STARTPTS[v0];
[0:a]atrim=0.00:1.00,asetpts=PTS-STARTPTS[a0];
[0:v]trim=2.00:3.00,setpts=PTS-STARTPTS[v1];
[0:a]atrim=2.00:3.00,asetpts=PTS-STARTPTS[a1];
[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]
""".strip()
    )


def test_subtitle():
    clips = [SUB_3, SUB_1]
    assert find_subs(clips) == [
        Subtitle(2, Clip(0, 1), "Sub3"),
        Subtitle(0, Clip(1, 2), "Sub1"),
    ]


def test_subtitle_to():
    assert SUB_1.to(SUB_3) == Clip(0, 3)
    assert SUB_3.to(SUB_1) == Clip(0, 3)


def test_format_srt():
    assert ClipLike.srt_timestamp(3600 + 23 * 60 + 45 + 0.678) == "01:23:45,678"


def test_remove_subs():
    assert remove_subs(movie.all_subtitles, [SUB_2]) == [Clip(0, 1), Clip(2, 3)]
    assert remove_subs(movie.all_subtitles, [SUB_1]) == [Clip(1, 3)]
    assert remove_subs(movie.all_subtitles, [SUB_3]) == [Clip(0, 2)]
