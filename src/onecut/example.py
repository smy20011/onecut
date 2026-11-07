from onecut.clips import *

def timeline():
    movie = Movie("test.mov", 1000, {Cap.AUDIO, Cap.VIDEO})
    section_1 = SubClip.combine(
        movie.sub(1, 2, "Sub_A"),
        movie.sub(2, 3, "Sub_B")
    )
    section_2 = SubClip.combine(
        movie.sub(3, 4, "Sub_A"),
        movie.sub(4, 5, "Sub_B")
    )
    return Concat([section_1, section_2])


if __name__ == "__main__":
    print(timeline())
