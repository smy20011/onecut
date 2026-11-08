"""Render MLT XML from Clips"""

import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from onecut.clips import *
from yattag import Doc


class MltXml:
    def __init__(self, clip, fps=30, **profile):
        self.clips = {}
        self.clip_id_to_id: dict[str, str] = {}
        self.rendered = set()
        self.xmls: list[str] = []
        self.root = clip
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
        profile_args = " ".join([f'{k}="{escape(str(v))}"' for k, v in self.profile.items()])
        self.render_clip(self.root)
        result = f"""
        <mlt>
          <profile frame_rate_num="{self.fps}" frame_rate_den="1" {profile_args}/>
          {"".join(self.xmls)}
        </mlt>
        """
        tree = ET.fromstring(result)
        ET.indent(tree)
        return ET.tostring(tree, encoding="unicode")

    def render_clip(self, clip: Clip):
        if clip.id in self.rendered:
            return
        self.rendered.add(clip.id)

        for dep in clip.deps():
            self.render_clip(dep)

        result = ""
        match clip:
            case Source():
                result = self.render_source(clip)
            case SubClip():
                result = self.render_subclip(clip)
            case Concat():
                result = self.render_concat(clip)
            case Overlay():
                result = self.render_overlay(clip)
            case _:
                raise ValueError(f"Unknown type {type(clip)}")

        self.xmls.append(result)
        return result

    def render_source(self, clip: Source) -> str:
        return f"""
            <producer id="{self.name(clip)}" in="0" out="{self.ts_in(clip.len())}">
                <property name="resource">{clip.filename}</property>
                {self.render_filter(clip)}
            </producer>
        """

    def render_subclip(self, clip: SubClip) -> str:
        return f"""
             <playlist id="{self.name(clip)}">
                 <entry producer="{self.name(clip.source)}" in="{self.ts_in(clip.start)}" out="{self.ts_out(clip.end)}" />
                 {self.render_filter(clip)}
             </playlist>
        """

    def render_tag_effect(self, item: Transition | Filter):
        tag = "filter" if isinstance(item, Filter) else "transition"
        result = ""
        if item.start is not None and item.end is not None:
            result += (
                f"""<{tag} in="{self.ts_in(item.start)}" out="{self.ts_out(item.end)}">"""
            )
        else:
            result += f"<{tag}>"
        result += f"""<property name="mlt_service">{item.name}</property>"""
        for k, v in item.args.items():
            result += f"""
                <property name="{k}">{escape(v)}</property>
            """
        result += f"</{tag}>"
        return result

    def render_filter(self, clip: Clip) -> str:
        return "".join([self.render_tag_effect(f) for f in clip.filters])

    def render_concat(self, clip: Concat):
        producers = ""
        for dep in clip.deps():
            producers += f'<entry producer="{self.name(dep)}" />'
        return f"""
             <playlist id="{self.name(clip)}">
             {producers}
             {self.render_filter(clip)}
             </playlist>
        """

    def render_overlay(self, clip: Overlay):
        transtitions = "".join([self.render_tag_effect(t) for t in clip.transitions])
        clip_len = self.ts_out(clip.len())
        return f"""
              <tractor id="{self.name(clip)}">
                <multitrack>
                  <track producer="{self.name(clip.source)}" in="0" out="{clip_len}"/>
                  <track producer="{self.name(clip._overlay)}" in="0" out="{clip_len}"/>
                </multitrack>
                {self.render_filter(clip)}
                {transtitions}
              </tractor>
            """

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
