"""Text extraction and chunking for the search index."""
from __future__ import annotations

import email
import email.policy
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from .util import HEADING_RE, parse_frontmatter, read_text

SUPPORTED = {".md", ".markdown", ".txt", ".vtt", ".srt", ".eml", ".html", ".htm", ".docx", ".pdf", ".pptx"}


class MissingExtra(Exception):
    pass


@dataclass
class Unit:
    text: str
    kind: str = "line"  # line | page | slide
    loc: int = 1  # page/slide number, or line offset for kind=line


@dataclass
class Extracted:
    title: str
    units: list


@dataclass
class Chunk:
    heading: str
    body: str
    loc: str  # "L12", "p3", "s4"


def _first_heading_title(text: str, default: str) -> str:
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) == 1:
            return m.group(2)
    return default


def _markdown(path: Path) -> Extracted:
    text = read_text(path)
    meta, consumed = parse_frontmatter(text)
    body = "\n".join(text.splitlines()[consumed:])
    title = (meta or {}).get("title") if meta else None
    if not isinstance(title, str) or not title:
        title = _first_heading_title(body, path.stem)
    return Extracted(title, [Unit(body, "line", consumed)])


def _plain(path: Path) -> Extracted:
    return Extracted(path.stem, [Unit(read_text(path), "line", 0)])


_TS_RE = re.compile(r"^\s*(\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{1,3}\s*-->\s*.*$")


def _subtitles(path: Path) -> Extracted:
    out = []
    for line in read_text(path).splitlines():
        s = line.strip()
        if not s or s.upper().startswith("WEBVTT") or s.isdigit() or _TS_RE.match(line):
            if not s:
                out.append("")
            continue
        if s.startswith(("NOTE", "STYLE", "Kind:", "Language:")):
            continue
        out.append(re.sub(r"</?[^>]+>", "", s))
    return Extracted(path.stem, [Unit("\n".join(out), "line", 0)])


def _eml(path: Path) -> Extracted:
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    subject = str(msg.get("subject") or path.stem)
    header = "\n".join(f"{k}: {msg.get(k)}" for k in ("from", "to", "date") if msg.get(k))
    body_part = msg.get_body(preferencelist=("plain", "html"))
    body = ""
    if body_part is not None:
        body = body_part.get_content()
        if body_part.get_content_type() == "text/html":
            body = _html_to_text(body)[1]
    return Extracted(subject, [Unit(f"{header}\n\n{body}", "line", 0)])


class _HTMLText(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "section", "article", "ul", "ol", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.title, self._skip, self._in_title, self._head = [], "", 0, False, None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif re.fullmatch(r"h[1-6]", tag):
            self._head = int(tag[1])
            self.parts.append("\n\n" + "#" * self._head + " ")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif re.fullmatch(r"h[1-6]", tag):
            self._head = None
            self.parts.append("\n\n")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        else:
            self.parts.append(data)


def _html_to_text(html: str):
    p = _HTMLText()
    p.feed(html)
    text = re.sub(r"\n{3,}", "\n\n", "".join(p.parts))
    return p.title.strip(), text.strip()


def _html(path: Path) -> Extracted:
    title, text = _html_to_text(read_text(path))
    return Extracted(title or path.stem, [Unit(text, "line", 0)])


def _need(module: str, extra: str):
    try:
        return __import__(module, fromlist=["*"])
    except ImportError:
        raise MissingExtra(f"{extra} not installed (pip install llm-wiki-toolkit[docs])")


def _docx(path: Path) -> Extracted:
    docx = _need("docx", "python-docx")
    d = docx.Document(str(path))
    lines = []
    for p in d.paragraphs:
        style = (p.style.name or "") if p.style is not None else ""
        m = re.match(r"Heading (\d)", style)
        lines.append(("#" * int(m.group(1)) + " " if m else "") + p.text)
    for t in d.tables:
        for row in t.rows:
            lines.append(" | ".join(c.text for c in row.cells))
    title = d.core_properties.title or path.stem
    return Extracted(title, [Unit("\n\n".join(l for l in lines if l.strip()), "line", 0)])


def _pdf(path: Path) -> Extracted:
    pypdf = _need("pypdf", "pypdf")
    r = pypdf.PdfReader(str(path))
    units = [Unit(pg.extract_text() or "", "page", i + 1) for i, pg in enumerate(r.pages)]
    title = path.stem
    try:
        if r.metadata and r.metadata.title:
            title = str(r.metadata.title)
    except Exception:
        pass
    return Extracted(title, units)


def _pptx(path: Path) -> Extracted:
    pptx = _need("pptx", "python-pptx")
    prs = pptx.Presentation(str(path))
    units = []
    for i, slide in enumerate(prs.slides, 1):
        texts = [sh.text_frame.text for sh in slide.shapes if getattr(sh, "has_text_frame", False)
                 and sh.text_frame.text.strip()]
        units.append(Unit("\n\n".join(texts), "slide", i))
    return Extracted(path.stem, units)


_EXTRACTORS = {".md": _markdown, ".markdown": _markdown, ".txt": _plain, ".vtt": _subtitles,
               ".srt": _subtitles, ".eml": _eml, ".html": _html, ".htm": _html, ".docx": _docx,
               ".pdf": _pdf, ".pptx": _pptx}


def extract(path: Path) -> Extracted:
    return _EXTRACTORS[path.suffix.lower()](path)


def _split_long(text: str, maxc: int) -> list:
    out, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+", text):
        while len(sent) > maxc:
            cut = sent.rfind(" ", 0, maxc)
            cut = cut if cut > 0 else maxc
            if cur:
                out.append(cur)
                cur = ""
            out.append(sent[:cut])
            sent = sent[cut:].lstrip()
        if cur and len(cur) + 1 + len(sent) > maxc:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_unit(unit: Unit, minc: int, maxc: int) -> list:
    """Chunk by paragraphs/headings into ~minc..maxc character pieces."""
    blocks, heading, para, para_start = [], "", [], 0
    cur_head_for_block = ""

    def end_para():
        nonlocal para
        if para:
            blocks.append((para_start, "\n".join(para), cur_head_for_block, False))
            para = []

    for i, line in enumerate(unit.text.split("\n")):
        m = HEADING_RE.match(line)
        if m:
            end_para()
            heading = m.group(2)
            blocks.append((i, line, heading, True))
        elif not line.strip():
            end_para()
        else:
            if not para:
                para_start, cur_head_for_block = i, heading
            para.append(line)
    end_para()

    chunks, cur, cur_len, cur_start, cur_head = [], [], 0, 0, ""

    def loc(line_idx):
        if unit.kind == "page":
            return f"p{unit.loc}"
        if unit.kind == "slide":
            return f"s{unit.loc}"
        return f"L{unit.loc + line_idx + 1}"

    def flush():
        nonlocal cur, cur_len
        body = "\n\n".join(cur).strip()
        if body:
            chunks.append(Chunk(cur_head, body, loc(cur_start)))
        cur, cur_len = [], 0

    for start, text, head, is_head in blocks:
        if is_head and cur_len >= minc // 2:
            flush()
        for piece in (_split_long(text, maxc) if len(text) > maxc else [text]):
            if cur and cur_len + len(piece) + 2 > maxc:
                flush()
            if not cur:
                cur_start, cur_head = start, head
            cur.append(piece)
            cur_len += len(piece) + 2
            if cur_len >= minc:
                flush()
    flush()
    return chunks
