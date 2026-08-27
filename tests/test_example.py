import pytest
from onecut.example import *

movie = Movie("a.mp4")
SUB_1 = movie.clip(0, 1, "Sub1")
SUB_2 = movie.clip(1, 2, "Sub2")
SUB_3 = movie.clip(2, 3, "Sub3")


def test_ffmpeg_filter():
    clips = seq(SUB_1, SUB_3)
    assert (
        ffmpeg_filter(clips)
        == """
movie=filename=a.mp4[v0];
[v0]split=2[split0_v0][split1_v0];
amovie=filename=a.mp4[a0];
[a0]asplit=2[split0_a0][split1_a0];
[split0_v0]trim=0.00:1.00,setpts=PTS-STARTPTS[v1];
[split0_a0]atrim=0.00:1.00,asetpts=PTS-STARTPTS[a1];
[split1_v0]trim=2.00:3.00,setpts=PTS-STARTPTS[v3];
[split1_a0]atrim=2.00:3.00,asetpts=PTS-STARTPTS[a3];
[v1][a1][v3][a3]concat=n=2:v=1:a=1[v4][a4];
""".strip()
    )


def test_subtitle():
    clips = seq(SUB_3, SUB_1)
    assert clips.subtitles == [
        SubTitle(0, 1, "Sub3"),
        SubTitle(1, 2, "Sub1"),
    ]


def test_format_srt():
    assert srt_timestamp(3600 + 23 * 60 + 45 + 0.678) == "01:23:45,678"
    assert srt_timestamp(59.9996) == "00:01:00,000"
