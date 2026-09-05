"""Self-contained GitHub README graphic primitives."""
from __future__ import annotations

import base64
import hashlib
import html
import math
import re
from pathlib import Path
from xml.etree import ElementTree

ASSET = Path(__file__).resolve().parents[1] / "assets" / "github-v3" / "source-matter.png"
XRAY_ASSET = ASSET.with_name("source-xray.png")
PNG_PREFIX = "data:image/png;base64,"


def _png_data_uri(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"GitHub v3 artwork is missing: {path}")
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"GitHub v3 artwork is not PNG: {path}")
    return PNG_PREFIX + base64.b64encode(data).decode("ascii")


def source_matter_data_uri() -> str:
    return _png_data_uri(ASSET)


def source_matter_digest() -> str:
    paths = (ASSET, XRAY_ASSET)
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"GitHub v3 artwork is missing: {path}")
    return hashlib.sha256(b"".join(path.read_bytes() for path in paths)).hexdigest()


def hero_svg(animated: bool) -> str:
    base = source_matter_data_uri()
    xray = _png_data_uri(XRAY_ASSET) if animated else ""
    motion = ""
    reveal = ""
    if animated:
        motion = '<style>.xray{clip-path:polygon(0 0,0 0,0 100%,0 100%)}@media(prefers-reduced-motion:no-preference){.xray{animation:reveal 14s cubic-bezier(.55,0,.2,1) infinite}@keyframes reveal{0%,14%{clip-path:polygon(0 0,0 0,0 100%,0 100%)}44%,62%{clip-path:polygon(0 0,100% 0,100% 100%,0 100%)}92%,100%{clip-path:polygon(100% 0,100% 0,100% 100%,100% 100%)}}}</style>'
        reveal = f'<image class="xray" href="{xray}" width="1400" height="933" preserveAspectRatio="xMidYMid slice" clip-path="url(#art)"/>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="933" viewBox="0 0 1400 933" role="img" aria-labelledby="title description"><title id="title">Source into Form</title><desc id="description">An original architectural letter A sculpture made from metallic filaments and ceramic surfaces.</desc>{motion}<defs><clipPath id="art"><rect width="1400" height="933"/></clipPath></defs><rect width="1400" height="933" fill="#080c12"/><image href="{base}" width="1400" height="933" preserveAspectRatio="xMidYMid slice" clip-path="url(#art)"/>{reveal}</svg>'''


def _waves() -> str:
    paths = "".join(f'<path d="M990 {60+i*2:.1f} C1080 {60+i*2+math.sin(i*.15)*35:.1f} 1260 {70+i*2-math.sin(i*.15)*35:.1f} 1345 {70+i*2:.1f}" fill="none" stroke="#e8ebf0" stroke-width=".65" opacity=".45"/>' for i in range(48))
    return f'<g class="motion">{paths}</g>'


def _mesh() -> str:
    paths = []
    for i in range(48):
        angle = i * math.pi / 48
        paths.append(f'<ellipse cx="1168" cy="{124 + math.sin(angle)*5:.1f}" rx="{115-abs(math.sin(angle))*16:.1f}" ry="{55-abs(math.cos(angle))*10:.1f}" fill="none" stroke="#e8ebf0" stroke-width=".65" opacity=".45" transform="rotate({i*3.75:.1f} 1168 124)"/>')
    return f'<g class="motion">{"".join(paths)}<ellipse cx="1168" cy="124" rx="88" ry="42" fill="none" stroke="#ff7254" stroke-width="1.2"/></g>'


def _contours() -> str:
    paths = []
    for i in range(48):
        y = 80 + i * 2
        points = " ".join(f"{x} {y + 25*math.sin((x-990)/360*math.pi*2+i*.04):.1f}" for x in range(990, 1346, 30))
        paths.append(f'<path d="M{points}" fill="none" stroke="#e8ebf0" stroke-width=".65" opacity=".45"/>')
    accents = ''.join(f'<path d="M{x} 48 C{x-18} 112 {x+18} 160 {x} 210" fill="none" stroke="#ff7254" stroke-width="1.1"/>' for x in (1060, 1170, 1280))
    return f'<g class="motion">{"".join(paths)}{accents}</g>'


def _gate_paths() -> str:
    frames = "".join(
        f'<rect x="{1010 + index * 96}" y="{64 + index * 10}" width="58" height="112" rx="29" fill="none" stroke="#e8ebf0" stroke-width="1" opacity=".{5 + index}"/>'
        for index in range(3)
    )
    paths = "".join(
        f'<path d="M992 {82 + index * 24} H1045 C1080 {82 + index * 24} 1080 {166 - index * 18} 1122 {166 - index * 18} H1348" fill="none" stroke="#e8ebf0" stroke-width=".8" opacity=".52"/>'
        for index in range(4)
    )
    return frames + f'<g class="motion"><path d="M994 124H1350" stroke="#ff7254" stroke-width="1.4" stroke-dasharray="12 18"/><circle cx="1190" cy="124" r="6" fill="#ff7254"/></g>{paths}'


def _signal_tiles() -> str:
    tiles = "".join(
        f'<rect x="{1004 + column * 82}" y="{58 + row * 52}" width="62" height="34" rx="4" fill="none" stroke="#e8ebf0" stroke-width=".8" opacity=".5"/>'
        for row in range(3) for column in range(4)
    )
    signals = "".join(
        f'<rect x="{1016 + (index % 4) * 82}" y="{72 + (index // 4) * 52}" width="38" height="5" rx="2.5" fill="#ff7254" opacity=".{4 + index % 3}"/>'
        for index in range(8)
    )
    return tiles + f'<g class="motion">{signals}</g><path d="M990 188H1350" stroke="#e8ebf0" opacity=".3"/>'


def _paired_contours() -> str:
    curves = []
    for index in range(12):
        y = 64 + index * 10
        curves.append(f'<path d="M996 {y} C1050 {y-24} 1104 {y+24} 1168 {y} S1284 {y-24} 1348 {y}" fill="none" stroke="#e8ebf0" stroke-width=".75" opacity=".48"/>')
    mirror = "".join(
        f'<path d="M1168 {62 + index * 12} C1124 {84 + index * 12} 1080 {40 + index * 12} 1030 {62 + index * 12}" fill="none" stroke="#ff7254" stroke-width=".8" opacity=".7"/>'
        for index in range(8)
    )
    return "".join(curves) + f'<g class="motion">{mirror}<g transform="translate(2336 0) scale(-1 1)">{mirror}</g></g>'


def _focus_rings() -> str:
    rings = "".join(
        f'<rect x="{1052 + index * 42}" y="{62 + index * 10}" width="{196 - index * 28}" height="{126 - index * 20}" rx="{18 - index * 2}" fill="none" stroke="#e8ebf0" stroke-width=".8" opacity=".{7 - index}"/>'
        for index in range(5)
    )
    return rings + '<g class="motion"><rect x="1110" y="88" width="118" height="74" rx="10" fill="none" stroke="#ff7254" stroke-width="2"/><circle cx="1169" cy="125" r="4" fill="#ff7254"/></g>'


def _plate_motion(project_id: str) -> str:
    rules = {
        "polyai-dotnet": ("polyai-travel 14s ease-in-out infinite", "@keyframes polyai-travel{0%,100%{transform:translateX(-18px)}50%{transform:translateX(18px)}}"),
        "credscan": ("credscan-orbit 16s linear infinite", "@keyframes credscan-orbit{to{transform:rotate(360deg)}}"),
        "freshcart-backend": ("backend-flow 12s ease-in-out infinite", "@keyframes backend-flow{0%,100%{transform:translateY(-8px)}50%{transform:translateY(8px)}}"),
        "centaurloop-agent-governor": ("centaur-scan 10s ease-in-out infinite", "@keyframes centaur-scan{0%,100%{transform:translateX(-21px)}50%{transform:translateX(21px)}}"),
        "freshcart-web": ("web-signals 9s ease-in-out infinite", "@keyframes web-signals{0%,100%{transform:translateY(-5px);opacity:.45}50%{transform:translateY(5px);opacity:1}}"),
        "dupesweep": ("dupe-shift 15s ease-in-out infinite", "@keyframes dupe-shift{0%,100%{transform:translateX(-12px)}50%{transform:translateX(12px)}}"),
        "a11y-scope": ("a11y-focus 11s ease-in-out infinite", "@keyframes a11y-focus{0%,100%{transform:scale(.88);opacity:.55}50%{transform:scale(1.08);opacity:1}}"),
    }
    animation, keyframes = rules[project_id]
    return f'<style>@media (prefers-reduced-motion: no-preference){{.motif-{project_id} .motion{{animation:{animation};transform-box:fill-box;transform-origin:center}}{keyframes}}}</style>'


def plate_svg(project_id: str, title: str, category: str, number: int, animated: bool = True) -> str:
    motifs = {
        "polyai-dotnet": _waves(),
        "credscan": _mesh(),
        "freshcart-backend": _contours(),
        "centaurloop-agent-governor": _gate_paths(),
        "freshcart-web": _signal_tiles(),
        "dupesweep": _paired_contours(),
        "a11y-scope": _focus_rings(),
    }
    if project_id not in motifs:
        raise ValueError(f"unsupported project plate: {project_id}")
    title, category = html.escape(title, quote=True), html.escape(category, quote=True)
    motion = _plate_motion(project_id) if animated else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="250" viewBox="0 0 1400 250" role="img" aria-label="{title} project plate">{motion}<defs><clipPath id="motif"><rect x="980" y="38" width="376" height="172"/></clipPath></defs><rect width="1400" height="250" fill="#0b1019"/><path d="M44 36h1312M44 214h1312" stroke="#e8ebf0" opacity=".2"/><g class="labels"><text x="46" y="84" fill="#ff7254" font-family="monospace" font-size="16">0{number} / SOURCE STUDY</text><text x="46" y="154" fill="#f4f4ee" font-family="Arial,Helvetica,sans-serif" font-size="44" font-weight="800">{title}</text><text x="48" y="190" fill="#bfc5d0" font-family="Arial,Helvetica,sans-serif" font-size="20">{category}</text></g><g class="motif motif-{project_id}" clip-path="url(#motif)">{motifs[project_id]}</g></svg>'''


def validate_svg(svg: str) -> None:
    root = ElementTree.fromstring(svg)
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("invalid SVG root")
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag in {"script", "foreignobject"}:
            raise ValueError("unsafe SVG element")
        for name, value in element.attrib.items():
            local = name.rsplit("}", 1)[-1].lower()
            if local.startswith("on"):
                raise ValueError("unsafe SVG event handler")
            if local == "href":
                if value.startswith(PNG_PREFIX):
                    try:
                        if not base64.b64decode(value[len(PNG_PREFIX):], validate=True).startswith(b"\x89PNG\r\n\x1a\n"):
                            raise ValueError("unsafe raster")
                    except ValueError as exc:
                        raise ValueError("unsafe raster") from exc
                elif not value.startswith("#"):
                    raise ValueError("unsafe SVG reference")
            if local == "style":
                for ref in re.findall(r"url\(\s*['\"]?([^'\"\s)]+)", value, re.I):
                    if not ref.startswith("#"):
                        raise ValueError("unsafe CSS URL")
    lowered = svg.lower()
    refs = re.findall(r"url\(\s*([^)]*?)\s*\)", lowered, re.I)
    if "@import" in lowered or any(ref.strip().strip("'\"") and not ref.strip().strip("'\"").startswith("#") for ref in refs):
        raise ValueError("unsafe SVG CSS")
