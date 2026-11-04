#!/usr/bin/env python3
"""html-reportのビルドスクリプト。

本文のHTML断片(またはビルド済みのレポート)を検査し、assets/template.htmlへ流し込んで
自己完結型のHTMLレポートを出力する。CSSはテンプレートにだけ存在するため、どのレポートも
同じ見た目になる。外部ライブラリは使わず、Python 3.9以降の標準ライブラリだけで動く。

使い方:
    python3 build.py BODY.html -o REPORT.html
    python3 build.py REPORT.html -o REPORT.html     # ビルド済みレポートを編集した後の再ビルド
    python3 build.py - -o REPORT.html < BODY.html   # 標準入力から読む

検査エラーがある場合はレポートを出力せず、終了コード1を返す。
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = SKILL_DIR / "assets" / "template.html"

BODY_START = "<!-- report:body:start -->"
BODY_END = "<!-- report:body:end -->"
TOC_START = "<!-- report:toc:start -->"
TOC_END = "<!-- report:toc:end -->"

# h2がこの数以上あれば、最初のh2の直前に目次を自動で挿入する
TOC_MIN_H2 = 4

ALLOWED_TAGS = {
    "header", "div", "span", "p", "h1", "h2", "h3",
    "ul", "ol", "li", "dl", "dt", "dd",
    "a", "code", "pre", "kbd", "br", "sup", "sub",
    "table", "thead", "tbody", "tr", "th", "td",
    "blockquote", "details", "summary", "hr",
    "figure", "figcaption", "img",
}
VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
EMPHASIS_TAGS = {
    "strong", "b", "em", "i", "u", "mark", "font", "big", "small", "s", "del", "ins",
}

GLOBAL_ATTRS = {"class", "id"}
TAG_ATTRS = {
    "a": {"href", "target", "rel", "title"},
    "img": {"src", "alt", "width", "height"},
    "pre": {"data-lang"},
    "details": {"open"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
    "ol": {"start"},
}

CALLOUT_VARIANTS = {"info", "success", "warning", "danger"}
TAG_COLORS = {"gray", "brown", "orange", "yellow", "green", "blue", "purple", "pink", "red"}
CLASS_TAGS = {
    "page-header": {"header"},
    "page-icon": {"div"},
    "page-title": {"h1"},
    "props": {"dl"},
    "callout": {"div"},
    "todo": {"ul"},
    "done": {"li"},
    "columns": {"div"},
    "muted": {"span", "p"},
    "sources": {"ol"},
    "cite": {"a"},
    "tag": {"span"},
}
CLASS_TAGS.update({variant: {"div"} for variant in CALLOUT_VARIANTS})
CLASS_TAGS.update({color: {"span"} for color in TAG_COLORS})

TOP_LEVEL_TAGS = {
    "header", "p", "ul", "ol", "pre", "table", "blockquote",
    "details", "figure", "div", "hr", "h2", "h3",
}
BLOCK_TAGS = {"p", "ul", "ol", "pre", "table", "blockquote", "details", "figure", "div", "hr"}
CALLOUT_CHILD_TAGS = {"p", "ul", "ol", "pre", "table", "blockquote", "details"}
ALLOWED_CHILDREN = {
    "ul": {"li"},
    "ol": {"li"},
    "dl": {"dt", "dd"},
    "table": {"thead", "tbody", "tr"},
    "thead": {"tr"},
    "tbody": {"tr"},
    "tr": {"th", "td"},
    "figure": {"img", "figcaption"},
    "pre": {"code"},
}
# 直下にテキストを置けない要素(子要素で囲む必要がある)
NO_DIRECT_TEXT_TAGS = {"ul", "ol", "dl", "table", "thead", "tbody", "tr", "pre", "figure", "header", "details"}

ESCAPE_HINT = "コード中の < > & は &lt; &gt; &amp; にエスケープする"


class Element:
    __slots__ = ("tag", "classes", "line", "parent", "child_tags", "seq")

    def __init__(self, tag: str, classes: set[str], line: int, parent: Element | None, seq: int):
        self.tag = tag
        self.classes = classes
        self.line = line
        self.parent = parent
        self.child_tags: list[str] = []
        self.seq = seq

    def has(self, cls: str) -> bool:
        return cls in self.classes

    def describe(self) -> str:
        if self.classes:
            return f"<{self.tag} class=\"{' '.join(sorted(self.classes))}\">"
        return f"<{self.tag}>"


class Checker(HTMLParser):
    """本文断片がコンポーネントの規約に従っているかを検査する。"""

    def __init__(self, line_map: Callable[[int], int] = lambda line: line):
        super().__init__(convert_charrefs=True)
        self.line_map = line_map
        self.errors: list[tuple[int, str]] = []
        self.warnings: list[tuple[int, str]] = []
        self.stack: list[Element] = []
        self.ids: dict[str, int] = {}
        self.anchors: list[tuple[str, int]] = []
        self.headings: list[dict] = []
        self.h1_texts: list[str] = []
        self.first_h2_pos: tuple[int, int] | None = None
        self.top_count = 0
        self.header_count = 0
        self.seq = 0
        self.last_h2_seq = -1
        self.sources: list[tuple[int, int]] = []  # (seq, line)
        self._captures: list[dict] = []
        self._in_code = False

    # ---- helpers ----
    def _line(self) -> int:
        return self.line_map(self.getpos()[0])

    def error(self, message: str, line: int | None = None) -> None:
        self.errors.append((line if line is not None else self._line(), message))

    def warn(self, message: str, line: int | None = None) -> None:
        self.warnings.append((line if line is not None else self._line(), message))

    # ---- parser callbacks ----
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line = self._line()

        if self._in_code:
            self.error(f"<code>の中にタグ<{tag}>がある。{ESCAPE_HINT}")
            return

        attr_map = {name: (value or "") for name, value in attrs}
        classes = set(attr_map.get("class", "").split())
        parent = self.stack[-1] if self.stack else None
        self.seq += 1

        self._check_tag(tag, line)
        self._check_attrs(tag, attr_map, line)
        self._check_classes(tag, classes, parent, line)
        self._check_placement(tag, classes, parent, line)

        if tag == "a":
            href = attr_map.get("href")
            if href is None or href == "":
                self.error("<a>にhrefがない")
            elif href.startswith("#"):
                self.anchors.append((href[1:], line))
            elif href.lower().startswith("javascript:"):
                self.error("javascript: のリンクは使えない")
        if tag == "img" and not attr_map.get("alt"):
            self.warn("<img>にaltがない")
        if tag == "h2":
            self.last_h2_seq = self.seq
            if self.first_h2_pos is None:
                self.first_h2_pos = self.getpos()
        if tag == "ol" and "sources" in classes:
            self.sources.append((self.seq, line))

        if parent is not None:
            parent.child_tags.append(tag)

        if tag in VOID_TAGS:
            return

        element = Element(tag, classes, line, parent, self.seq)
        self.stack.append(element)
        if tag in ("h1", "h2", "h3"):
            self._captures.append({"level": tag, "id": attr_map.get("id", ""), "parts": [], "line": line})
        if tag == "code":
            self._in_code = True

    def handle_endtag(self, tag: str) -> None:
        if self._in_code and tag != "code":
            return
        if tag in VOID_TAGS:
            return
        if not any(element.tag == tag for element in self.stack):
            self.error(f"対応する開始タグのない</{tag}>がある")
            return
        while self.stack[-1].tag != tag:
            unclosed = self.stack.pop()
            self.error(f"{unclosed.describe()}が閉じられていない", unclosed.line)
            self._finish_element(unclosed)
        self._finish_element(self.stack.pop())

    def handle_data(self, data: str) -> None:
        for capture in self._captures:
            capture["parts"].append(data)
        if self._in_code or not data.strip():
            return
        parent = self.stack[-1] if self.stack else None
        snippet = data.strip()[:20]
        if parent is None:
            self.error(f"トップレベルに裸のテキスト「{snippet}」がある。<p>などで囲む")
        elif parent.tag in NO_DIRECT_TEXT_TAGS:
            self.error(f"{parent.describe()}の直下にテキスト「{snippet}」がある。子要素で囲む")
        elif parent.has("callout") or parent.has("columns"):
            self.error(f"{parent.describe()}の直下にテキスト「{snippet}」がある。<p>で囲む")

    def close(self) -> None:
        super().close()
        while self.stack:
            unclosed = self.stack.pop()
            self.error(f"{unclosed.describe()}が閉じられていない", unclosed.line)
            self._finish_element(unclosed)
        self._finish_document()

    # ---- checks ----
    def _check_tag(self, tag: str, line: int) -> None:
        if tag in EMPHASIS_TAGS:
            self.error(f"強調タグ<{tag}>は使わない。重要な内容はコールアウトや見出しで示す", line)
        elif tag in ("h4", "h5", "h6"):
            self.error(f"<{tag}>は使えない。見出しはh2とh3だけ使う", line)
        elif tag == "nav":
            self.error("<nav>は書かない。目次はbuild.pyが自動で生成する", line)
        elif tag in ("style", "script", "link"):
            self.error(f"<{tag}>は使えない。CSSはテンプレートにだけ存在する", line)
        elif tag not in ALLOWED_TAGS:
            self.error(f"<{tag}>は使えない。references/components.mdのコンポーネントだけを使う", line)

    def _check_attrs(self, tag: str, attr_map: dict[str, str], line: int) -> None:
        allowed = GLOBAL_ATTRS | TAG_ATTRS.get(tag, set())
        for name in attr_map:
            if name == "style":
                self.error("style属性は使わない。見た目はクラスで指定する", line)
            elif name.startswith("on"):
                self.error(f"イベント属性{name}は使えない", line)
            elif name not in allowed and not name.startswith("aria-"):
                self.error(f"<{tag}>に属性{name}は使えない", line)
        element_id = attr_map.get("id")
        if element_id is not None:
            if element_id in self.ids:
                self.error(f"id=\"{element_id}\"が重複している(L{self.ids[element_id]}と同じ)", line)
            else:
                self.ids[element_id] = line

    def _check_classes(self, tag: str, classes: set[str], parent: Element | None, line: int) -> None:
        for cls in sorted(classes):
            if cls not in CLASS_TAGS:
                self.error(f"未定義のclass「{cls}」がある", line)
            elif tag not in CLASS_TAGS[cls]:
                allowed = "、".join(f"<{t}>" for t in sorted(CLASS_TAGS[cls]))
                self.error(f"class「{cls}」は{allowed}にだけ付ける", line)
        variants = classes & CALLOUT_VARIANTS
        if variants and "callout" not in classes:
            self.error(f"class「{' '.join(sorted(variants))}」はcalloutと組み合わせる", line)
        if len(variants) > 1:
            self.error("コールアウトの種類は1つだけ指定する", line)
        colors = classes & TAG_COLORS
        if colors and "tag" not in classes:
            self.error(f"色のclass「{' '.join(sorted(colors))}」はtagと組み合わせる", line)
        if len(colors) > 1:
            self.error("タグの色は1つだけ指定する", line)
        if "done" in classes and not (parent is not None and parent.tag == "ul" and parent.has("todo")):
            self.error("class「done」は<ul class=\"todo\">の<li>にだけ付ける", line)

    def _check_placement(self, tag: str, classes: set[str], parent: Element | None, line: int) -> None:
        # トップレベルの並び
        if parent is None:
            self.top_count += 1
            if tag not in TOP_LEVEL_TAGS and tag in ALLOWED_TAGS:
                self.error(f"<{tag}>はトップレベルに置けない", line)
            if self.top_count == 1 and not (tag == "header" and "page-header" in classes):
                self.error("本文は<header class=\"page-header\">から始める", line)
            if self.top_count == 2 and self.header_count == 1 and "callout" not in classes:
                self.warn("ページヘッダーの直後に要約のコールアウトを置く", line)

        if tag == "header":
            self.header_count += 1
            if parent is not None or "page-header" not in classes:
                self.error("<header>はトップレベルの<header class=\"page-header\">としてだけ使う", line)
            if self.header_count > 1:
                self.error("ページヘッダーは1つだけ置く", line)
        if parent is not None and parent.tag == "header":
            ok = (tag == "div" and "page-icon" in classes) or (tag == "h1") or (tag == "dl" and "props" in classes)
            if not ok:
                self.error(f"ページヘッダーの中には{tag}を置けない。page-icon、page-title、propsだけを置く", line)
        if tag == "h1" and not (parent is not None and parent.tag == "header" and "page-title" in classes):
            self.error("<h1>はページヘッダー内の<h1 class=\"page-title\">としてだけ使う", line)

        if tag == "h2" and parent is not None:
            self.error("<h2>はトップレベルにだけ置く", line)
        if tag == "h3" and parent is not None:
            in_column = parent.tag == "div" and not parent.classes and parent.parent is not None and parent.parent.has("columns")
            if not in_column:
                self.error("<h3>はトップレベルか段組みの列の中にだけ置く", line)

        if tag == "dl" and "props" not in classes:
            self.error("<dl>はページヘッダーのプロパティ(<dl class=\"props\">)にだけ使う", line)
        if tag == "div" and not classes:
            if not (parent is not None and parent.has("columns")):
                self.error("classのない<div>は段組み(<div class=\"columns\">)の列としてだけ使う", line)
        if tag == "div" and classes and not classes & {"callout", "columns", "page-icon"}:
            self.error(f"<div class=\"{' '.join(sorted(classes))}\">は定義されていない", line)
        if tag == "span" and "tag" not in classes and "muted" not in classes:
            self.error("<span>はタグ(class=\"tag\")か補足テキスト(class=\"muted\")としてだけ使う", line)
        if tag == "img" and not (parent is not None and parent.tag == "figure"):
            self.error("<img>は<figure>の中にだけ置く", line)

        if tag in ("li", "dt", "dd", "tr", "th", "td", "thead", "tbody", "summary", "figcaption"):
            expected = {
                "li": ("ul", "ol"), "dt": ("dl",), "dd": ("dl",),
                "tr": ("table", "thead", "tbody"), "th": ("tr",), "td": ("tr",),
                "thead": ("table",), "tbody": ("table",), "summary": ("details",),
                "figcaption": ("figure",),
            }[tag]
            if parent is None or parent.tag not in expected:
                self.error(f"<{tag}>は{'、'.join(f'<{t}>' for t in expected)}の直下にだけ置く", line)

        if parent is None:
            return
        allowed_children = ALLOWED_CHILDREN.get(parent.tag)
        if allowed_children is not None and tag not in allowed_children:
            hint = f"。{ESCAPE_HINT}" if parent.tag == "pre" else ""
            self.error(f"{parent.describe()}の直下に<{tag}>は置けない{hint}", line)
        if parent.tag == "pre" and tag == "code" and "code" in parent.child_tags:
            self.error("<pre>の中の<code>は1つだけにする", line)
        if parent.has("callout") and tag not in CALLOUT_CHILD_TAGS:
            self.error(f"コールアウトの直下に<{tag}>は置けない。<p>やリストで囲む", line)
        if parent.has("columns") and not (tag == "div" and not classes):
            self.error("段組みの直下には列としてclassのない<div>だけを置く", line)
        if parent.tag == "details":
            if not parent.child_tags and tag != "summary":
                self.error("トグル(<details>)の最初の子は<summary>にする", line)
            elif parent.child_tags and tag not in BLOCK_TAGS:
                self.error(f"トグルの中身に<{tag}>を直接置けない。<p>などで囲む", line)

    def _finish_element(self, element: Element) -> None:
        if element.tag == "code":
            self._in_code = False
        if element.tag in ("h1", "h2", "h3") and self._captures:
            capture = self._captures.pop()
            text = re.sub(r"\s+", " ", "".join(capture["parts"])).strip()
            if not text:
                self.error(f"<{element.tag}>が空になっている", element.line)
            if element.tag == "h1":
                self.h1_texts.append(text)
            else:
                self.headings.append({"level": element.tag, "id": capture["id"], "text": text})
        if element.tag == "pre" and "code" not in element.child_tags:
            self.error("<pre>の中身は<code>で囲む", element.line)
        if element.tag == "details" and "summary" not in element.child_tags:
            self.error("トグル(<details>)に<summary>がない", element.line)
        if element.has("columns") and len(element.child_tags) not in (2, 3):
            self.error("段組みの列は2つか3つにする", element.line)
        if element.has("callout") and not element.child_tags:
            self.error("コールアウトの中身を<p>などで書く", element.line)
        if element.tag == "header" and "h1" not in element.child_tags:
            self.error("ページヘッダーに<h1 class=\"page-title\">がない", element.line)

    def _finish_document(self) -> None:
        last_line = self._line()
        if self.header_count == 0:
            self.error("<header class=\"page-header\">がない", self.line_map(1))
        if len(self.h1_texts) != 1 and self.header_count == 1:
            self.error("ページタイトル(<h1 class=\"page-title\">)は1つだけ置く", self.line_map(1))
        for target, line in self.anchors:
            if target not in self.ids:
                self.error(f"リンク先#{target}が存在しない", line)
        if not any(h["level"] == "h2" for h in self.headings):
            self.warn("<h2>のセクションがない", last_line)
        if len(self.sources) > 1:
            self.warn("参考資料のリスト(<ol class=\"sources\">)は1つにまとめる", self.sources[1][1])
        if self.sources and self.sources[-1][0] < self.last_h2_seq:
            self.warn("参考資料は最後のセクションに置く", self.sources[-1][1])


def extract_body(source: str) -> tuple[str, int]:
    """本文断片を取り出す。ビルド済みレポートなら本文マーカーの間だけを返す。"""
    if "__REPORT_BODY__" in source:
        raise ValueError("テンプレート自体が渡された。本文断片を渡す")
    start = source.find(BODY_START)
    end = source.find(BODY_END)
    if start != -1 and end != -1 and start < end:
        body_start = start + len(BODY_START)
        return source[body_start:end], source[:body_start].count("\n")
    if re.search(r"<!doctype|<html[\s>]|<body[\s>]", source, re.I):
        raise ValueError("html-reportでビルドしたレポートではないHTML文書が渡された。本文断片だけを渡す")
    return source, 0


TOC_RE = re.compile(re.escape(TOC_START) + r".*?" + re.escape(TOC_END) + r"\n?", re.S)


def strip_toc(body: str) -> tuple[str, list[tuple[int, int]]]:
    """前回のビルドで挿入した目次を取り除く。

    取り除いた位置(取り除いた後の行番号)と行数の組も返す。検査エラーの行番号を
    入力ファイルの行番号へ戻すために使う。
    """
    parts: list[str] = []
    removed: list[tuple[int, int]] = []
    last = 0
    for match in TOC_RE.finditer(body):
        parts.append(body[last:match.start()])
        removed.append(("".join(parts).count("\n") + 1, match.group(0).count("\n")))
        last = match.end()
    parts.append(body[last:])
    return "".join(parts), removed


ID_ATTR_RE = re.compile(r"(?<![\w-])id\s*=\s*([\"'])(.*?)\1", re.I | re.S)


def add_heading_ids(body: str) -> str:
    """idのないh2とh3に、sec-1から順にidを振る。"""
    used = {m.group(2) for m in ID_ATTR_RE.finditer(body)}
    counter = 0

    def replace(match: re.Match) -> str:
        nonlocal counter
        attrs = match.group(2) or ""
        if ID_ATTR_RE.search(attrs):
            return match.group(0)
        while True:
            counter += 1
            candidate = f"sec-{counter}"
            if candidate not in used:
                used.add(candidate)
                break
        return f"<{match.group(1)} id=\"{candidate}\"{attrs}>"

    return re.sub(r"<(h[23])(\s[^<>]*)?>", replace, body, flags=re.I)


def add_link_targets(body: str) -> str:
    """外部リンクを新しいタブで開くようにする。"""

    def replace(match: re.Match) -> str:
        attrs = match.group(1)
        if not re.search(r"(?<![\w-])href\s*=\s*[\"']https?://", attrs, re.I):
            return match.group(0)
        if re.search(r"(?<![\w-])target\s*=", attrs, re.I):
            return match.group(0)
        return f"<a{attrs.rstrip()} target=\"_blank\" rel=\"noopener noreferrer\">"

    return re.sub(r"<a(\s[^<>]*)>", replace, body, flags=re.I)


def make_toc(headings: list[dict], lang: str) -> str:
    if sum(1 for h in headings if h["level"] == "h2") < TOC_MIN_H2:
        return ""
    label = "目次" if lang.lower().startswith("ja") else "Contents"
    items = [
        f"<li class=\"toc-{h['level']}\"><a href=\"#{html.escape(h['id'])}\">{html.escape(h['text'])}</a></li>"
        for h in headings
    ]
    return "\n".join([
        TOC_START,
        f"<nav class=\"toc\" aria-label=\"{label}\">",
        "<ul>",
        *items,
        "</ul>",
        "</nav>",
        TOC_END,
        "",
    ])


def offset_of(text: str, line: int, column: int) -> int:
    offset = 0
    for _ in range(line - 1):
        offset = text.index("\n", offset) + 1
    return offset + column


def print_messages(label: str, messages: list[tuple[int, str]]) -> None:
    if not messages:
        return
    print(f"{label}: {len(messages)}件", file=sys.stderr)
    for line, message in sorted(messages):
        print(f"  L{line}: {message}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="本文のHTML断片からNotion風のHTMLレポートを生成する")
    parser.add_argument("input", help="本文断片のファイル、ビルド済みレポート、または標準入力を表す -")
    parser.add_argument("-o", "--output", required=True, help="出力するHTMLファイルのパス")
    parser.add_argument("--lang", default="ja", help="html要素のlang属性(既定: ja)")
    args = parser.parse_args()

    try:
        source = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        body, line_offset = extract_body(source)
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 2

    body, removed_toc = strip_toc(body)
    body = add_link_targets(add_heading_ids(body))

    def line_map(line: int) -> int:
        return line + line_offset + sum(count for at, count in removed_toc if line >= at)

    checker = Checker(line_map)
    checker.feed(body)
    checker.close()

    print_messages("警告", checker.warnings)
    if checker.errors:
        print_messages("エラー", checker.errors)
        print("検査エラーがあるため、レポートを出力していない。本文断片を直して再実行する。", file=sys.stderr)
        return 1

    toc = make_toc(checker.headings, args.lang)
    if toc and checker.first_h2_pos is not None:
        position = offset_of(body, *checker.first_h2_pos)
        body = body[:position] + toc + body[position:]

    title = checker.h1_texts[0]
    page = template.replace("__REPORT_LANG__", html.escape(args.lang)).replace("__REPORT_TITLE__", html.escape(title))
    head, marker, tail = page.partition("__REPORT_BODY__")
    if not marker:
        print("エラー: テンプレートに本文の差し込み位置がない", file=sys.stderr)
        return 2

    output = Path(args.output).expanduser().resolve()
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(head + body.strip("\n") + tail, encoding="utf-8")
    except OSError as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 2

    h2_count = sum(1 for h in checker.headings if h["level"] == "h2")
    print(f"出力: {output}")
    print(f"タイトル: {title} / h2: {h2_count}件 / 目次: {'あり' if toc else 'なし'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
