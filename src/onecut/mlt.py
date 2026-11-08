"""Render MLT XML from Clips"""

import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from onecut.clips import *
from yattag import Doc, indent


class MltXml:
    def __init__(self, clip, fps=30, **profile):
        self.clips = {}
        self.clip_id_to_id: dict[str, str] = {}
        self.rendered = set()
        self.doc, self.tag, self.text = Doc().tagtext()
        self.root = clip
        if profile.get("name", "").endswith("60"):
            fps = 60
        self.fps = fps
        self.profile = profile

        def dfs(clip: Clip):
            if clip.id in self.clips:
                return
            self.clips[clip.id] = clip
            for clip in clip.deps():
                dfs(clip)

        return dfs(clip)

    def render(self) -> str:
        with self.tag("mlt"):
            self.doc.stag("profile", **self.profile)
            self.render_clip(self.root)
        return indent(self.doc.getvalue())

    def render_clip(self, clip: Clip):
        if clip.id in self.rendered:
            return
        self.rendered.add(clip.id)

        for dep in clip.deps():
            self.render_clip(dep)

        match clip:
            case Source():
                self.render_source(clip)
            case SubClip():
                self.render_subclip(clip)
            case Concat():
                self.render_concat(clip)
            case Overlay():
                self.render_overlay(clip)
            case _:
                raise ValueError(f"Unknown type {type(clip)}")

    def producer(self, **kwargs):
        return self.tag("producer", **kwargs)

    def entry(self, **kwargs):
        return self.doc.stag("entry", **kwargs)

    def playlist(self, **kwargs):
        return self.tag("playlist", **kwargs)

    def property(self, name, text):
        with self.tag("property", name=name):
            self.text(text)

    def in_out(self, in_, out_):
        if in_ is None or out_ is None:
            return {}
        return {"in": self.ts_in(in_), "out": self.ts_out(out_)}

    def render_source(self, clip: Source):
        with self.producer(id=self.name(clip), **self.in_out(0, clip.len())):
            self.property("resource", clip.filename)
            self.render_filter(clip)

    def render_subclip(self, clip: SubClip):
        with self.playlist(id=self.name(clip)):
            self.entry(
                producer=self.name(clip.source), **self.in_out(clip.start, clip.end)
            )
            self.render_filter(clip)

    def render_tag_effect(self, item: Transition | Filter):
        tag = "filter" if isinstance(item, Filter) else "transition"
        with self.tag(tag, **self.in_out(item.start, item.end)):
            self.property("mlt_service", item.name)
            for k, v in item.args.items():
                self.property(k, v)

    def render_filter(self, clip: Clip):
        for f in clip.filters:
            self.render_tag_effect(f)

    def render_concat(self, clip: Concat):
        with self.playlist(id=self.name(clip)):
            for dep in clip.deps():
                self.doc.stag("entry", producer=self.name(dep))
            self.render_filter(clip)

    def render_overlay(self, clip: Overlay):
        with self.tag("tractor", id=self.name(clip)):
            with self.tag("multitrack"):
                self.doc.stag(
                    "track",
                    producer=self.name(clip.source),
                    **self.in_out(0, clip.len()),
                )
                self.doc.stag(
                    "track",
                    producer=self.name(clip._overlay),
                    **self.in_out(0, clip.len()),
                )
            self.render_filter(clip)
            for t in clip.transitions:
                self.render_tag_effect(t)

    def ts_in(self, time: float) -> int:
        return round(self.fps * time)

    def ts_out(self, time: float) -> int:
        return round(self.fps * time) - 1

    def name(self, clip: Clip):
        if clip.id in self.clip_id_to_id:
            return self.clip_id_to_id[clip.id]

        prefix = ""
        match clip:
            case Source():
                prefix = "source_"
            case SubClip():
                prefix = "subclip_"
            case Concat():
                prefix = "concat_"
            case Overlay():
                prefix = "overlay_"

        id = f"{prefix}{len(self.clip_id_to_id)}"
        self.clip_id_to_id[clip.id] = id
        return id
