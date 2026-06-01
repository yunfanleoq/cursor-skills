#!/usr/bin/env python3
"""Build CPCC-style operation manual PDF: cover, TOC, chapter breaks, one image/page."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore

try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
except ImportError:
    print("Install: py -3.12 -m pip install fpdf2", file=sys.stderr)
    raise

from generate_source_pdf import find_cjk_font  # noqa: E402
from extract_source_pages import load_scope  # noqa: E402

IMG_RE = re.compile(r"^!\[(.*?)\]\((.+?)\)\s*$")
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
STEP_RE = re.compile(r"^\*\*步骤\s*(\d+)\*\*\s*(.*)$", re.I)
INTRO_LABEL_RE = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$")
INTRO_LABEL_ONLY_RE = re.compile(r"^\*\*(.+?)\*\*$")
SKIP_META_PREFIXES = ("著作权人", "文档版本", "编写日期", "文档类型")
FAQ_LABEL_RE = re.compile(
    r"^\*\*(现象|可能原因|原因|处理方法|处理步骤|建设目标|预期结果)\*\*[:：]?\s*(.*)$",
    re.I,
)

# 正文排版（加大行距，页面更饱满）
BODY_SIZE = 10.5
BODY_LINE_H = 7.0
CAPTION_SIZE = 10.0
CAPTION_LINE_H = 6.5
STEP_LINE_H = 7.0
PAGE_FILL_TARGET_Y = 262.0  # 内容尽量铺满（页脚之上）
PAGE_TOP_Y = 24.0
SUBSECTION_LEAD_SP = 3.5  # 小节（h3）标题前空半行
TOC_LINE_H = 7.5
TOC_TITLE_Y = 40.0
TOC_BODY_START_Y = 68.0  # 目录标题 + 间距之后
TOC_CONT_START_Y = 28.0
TOC_MAX_Y = 272.0
MIN_CHAPTER_BREAK_Y = 48.0  # 当前页已有内容超过此高度才在章首页换页

_NBSP = "\u00a0"
# 行首禁则：这些标点不应单独出现在行首（fpdf 无内置禁则，用 NBSP 与前字绑定）
_CJK_LINE_START_FORBIDDEN = frozenset("、。，；：！？）】」》…—·％%")
# 行末禁则：开引/开括号后不断行（在标点后插入 NBSP 与后字绑定）
_CJK_LINE_END_FORBIDDEN = frozenset("（【「《")
# 英文词组、版本号等不在中间断行（普通空格会被 fpdf 作为换行点）
_NO_BREAK_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"IP\s+Agent", re.I), f"IP{_NBSP}Agent"),
    (re.compile(r"Office\s+Action", re.I), f"Office{_NBSP}Action"),
    (re.compile(r"Retrieval-Augmented\s+Generation", re.I), f"Retrieval-Augmented{_NBSP}Generation"),
    (re.compile(r"localhost:\s*5173"), f"localhost:{_NBSP}5173"),
    (re.compile(r"localhost:\s*8000"), f"localhost:{_NBSP}8000"),
    (re.compile(r"（版本\s*(V[\d.]+\s*)）"), rf"（版本{_NBSP}\1）"),
    (re.compile(r"版本\s+(V[\d.]+\s*)"), rf"版本{_NBSP}\1"),
    (re.compile(r"》\s*（版本"), f"》{_NBSP}（版本"),
    (re.compile(r"「([^」]+)」\s*标签\s*："), r"「\1」标签："),
    (re.compile(r"「([^」]+)」\s*"), r"「\1」"),
    (re.compile(r"读\s*→\s*比\s*→\s*写\s*→\s*审"), f"读{_NBSP}→{_NBSP}比{_NBSP}→{_NBSP}写{_NBSP}→{_NBSP}审"),
    (re.compile(r"→\s+"), f"→{_NBSP}"),
    (re.compile(r"\s+→"), f"{_NBSP}→"),
    (re.compile(r"\b(OA|WOA|RAG|AI|PDF|JSON|Word|Agent)\s+(?=[\u4e00-\u9fff（「])"), rf"\1{_NBSP}"),
    (re.compile(r"(?<=[\u4e00-\u9fff])\s+(OA|WOA|D1|D2|AI)\s+"), rf"{_NBSP}\1{_NBSP}"),
    (re.compile(r"D1/D2"), f"D1{_NBSP}/{_NBSP}D2"),
    (re.compile(r"D1\s*/\s*D2"), f"D1{_NBSP}/{_NBSP}D2"),
    (re.compile(r"OA/PDF"), f"OA{_NBSP}/{_NBSP}PDF"),
    (re.compile(r"隐藏\s*\+\s*工作流"), f"隐藏{_NBSP}+{_NBSP}工作流"),
    (re.compile(r"导航\s*/\s*案件信息"), f"导航{_NBSP}/{_NBSP}案件信息"),
    (re.compile(r"案件信息\s*/\s*AI"), f"案件信息{_NBSP}/{_NBSP}AI"),
    (re.compile(r"\b(Reviewer)\s+Agent\b", re.I), f"Reviewer{_NBSP}Agent"),
    (re.compile(r"\b([A-Z][a-zA-Z]{2,14})\s+(Agent)\b"), rf"\1{_NBSP}\2"),
)


def _is_orphan_punct_only(text: str) -> bool:
    bare = text.replace(_NBSP, "").strip()
    return bool(bare) and all(c in _CJK_LINE_START_FORBIDDEN for c in bare)


def _line_starts_with_forbidden(line: str) -> bool:
    s = line.lstrip(_NBSP)
    return bool(s) and s[0] in _CJK_LINE_START_FORBIDDEN


def _merge_orphan_lines(lines: list[str]) -> list[str]:
    """句号/顿号等不得单独成行，也不得出现在行首（并入上一行）。"""
    merged: list[str] = []
    for line in lines:
        if merged and (
            _is_orphan_punct_only(line) or _line_starts_with_forbidden(line)
        ):
            merged[-1] += line
        else:
            merged.append(line)
    return merged


def _is_bad_break(text: str, cut: int) -> bool:
    if cut <= 0 or cut >= len(text):
        return False
    ch = text[cut]
    if ch in _CJK_LINE_START_FORBIDDEN or ch == _NBSP:
        return True
    if text[cut - 1] in _CJK_LINE_END_FORBIDDEN:
        return True
    return False


def wrap_text_kinsoku(pdf, text: str, first_w: float, rest_w: float | None = None) -> list[str]:
    """按宽度换行并遵守禁则；若剩余仅为句号等标点则并入当前行。"""
    if not text:
        return []
    rest_w = first_w if rest_w is None else rest_w
    lines: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        w = first_w if not lines else rest_w
        j = i + 1
        best = i
        while j <= n:
            seg = text[i:j]
            if pdf.get_string_width(seg) <= w + 0.05:
                best = j
                j += 1
            else:
                break
        if best <= i:
            best = min(i + 1, n)
        cut = best
        while cut > i + 1 and _is_bad_break(text, cut):
            cut -= 1
        if cut <= i:
            cut = best
        if cut < n and _is_orphan_punct_only(text[cut:]):
            cut = n
        lines.append(text[i:cut])
        i = cut
        while i < n and text[i] == _NBSP:
            i += 1
    return _merge_orphan_lines(lines)


_INLINE_INTRO_PARTS = re.compile(r"\*\*(.+?)\*\*\s*((?:(?!\*\*).)*)", re.DOTALL)


def _split_inline_intro_line(line: str) -> list[str]:
    """将同一行多个 **标签** 段落拆为独立 intro 块。"""
    if not line.strip().startswith("**"):
        return []
    parts: list[str] = []
    for m in _INLINE_INTRO_PARTS.finditer(line):
        label = _strip_md(m.group(1))
        rest = _strip_md(m.group(2).strip())
        parts.append(f"{label}：{rest}" if rest else f"{label}：")
    return parts


def _append_intro(sec: Section, block: str) -> None:
    block = block.strip()
    if not block:
        return
    sec.intro += ("\n\n" if sec.intro else "") + block


def _append_post_image(sec: Section, block: str) -> None:
    block = block.strip()
    if not block:
        return
    sec.post_image += ("\n\n" if sec.post_image else "") + block


def _append_section_prose(sec: Section, block: str) -> None:
    """已有截图时，后续导语写入图下说明；否则写入节首 intro。"""
    if sec.image:
        _append_post_image(sec, block)
    else:
        _append_intro(sec, block)


def _protect_cjk_kinsoku(text: str) -> str:
    """中文禁则：避免顿号/句号等标点被 fpdf 挤到下一行行首。"""
    if not text:
        return text
    out: list[str] = []
    for i, ch in enumerate(text):
        if ch in _CJK_LINE_START_FORBIDDEN:
            out.append(_NBSP)
        out.append(ch)
        if ch in _CJK_LINE_END_FORBIDDEN and i + 1 < len(text):
            out.append(_NBSP)
    return "".join(out)


def _protect_phrase_breaks(text: str) -> str:
    """避免中英文混排、符号链在空格处被 fpdf 拆到两行。"""
    out = text
    for pattern, replacement in _NO_BREAK_PHRASES:
        out = pattern.sub(replacement, out)
    # 拉丁字母/数字 + 空格 + 中文
    out = re.sub(r"([A-Za-z0-9]{2,12})\s+(?=[\u4e00-\u9fff（「])", rf"\1{_NBSP}", out)
    # 中文/闭括号 + 空格 + 拉丁或数字或斜杠
    out = re.sub(r"([\u4e00-\u9fff）」])\s+(?=[A-Za-z0-9「（/])", rf"\1{_NBSP}", out)
    # 斜杠、间隔号、加号两侧
    out = re.sub(r"\s+/\s+", f"{_NBSP}/{_NBSP}", out)
    out = re.sub(r"\s+·\s+", f"{_NBSP}·{_NBSP}", out)
    out = re.sub(r"\s+\+\s+", f"{_NBSP}+{_NBSP}", out)
    # 常见键名、单位、图号
    out = re.sub(r"\bEnter\s+键", f"Enter{_NBSP}键", out, flags=re.I)
    out = re.sub(r"(\d+)\s+GB\b", rf"\1{_NBSP}GB", out)
    out = re.sub(r"图\s+(\d[\d.\-]*)", rf"图{_NBSP}\1", out)
    out = re.sub(r"\bvs\s+", f"vs{_NBSP}", out, flags=re.I)
    out = re.sub(r"\s+vs\b", f"{_NBSP}vs", out, flags=re.I)
    # 括号内首尾空格
    out = re.sub(r"（\s+", "（", out)
    out = re.sub(r"\s+）", "）", out)
    # 数字 + 量词
    out = re.sub(r"(\d+)\s+([条项个步页])", rf"\1{_NBSP}\2", out)
    return _protect_cjk_kinsoku(out)


@dataclass
class TocEntry:
    level: int
    title: str
    page: int = 0


@dataclass
class Section:
    title: str
    intro: str = ""
    image: str | None = None
    caption: str = ""
    steps: list[str] = field(default_factory=list)
    expected: str = ""
    table_rows: list[list[str]] = field(default_factory=list)
    extra_tables: list[list[list[str]]] = field(default_factory=list)
    post_image: str = ""


@dataclass
class Block:
    kind: str
    text: str = ""
    rows: list[list[str]] = field(default_factory=list)
    section: Section | None = None


# 页末填充说明（按章节，用于填满页面）
CHAPTER_FILLERS: dict[str, list[str]] = {
    "第 1 章": [
        "阅读本手册前，请确认已获取合法授权账号，并知悉系统仅用于知识产权代理业务场景。",
        "手册中界面截图以当前版本为准；若与您处部署的菜单名称略有差异，请以实际系统为准。",
        "下列术语与缩略语适用于本系统全部功能模块；遇有歧义时以专利法及审查实践通行含义为准。",
        "WOA 模块面向审查意见通知书答复场景；知识库模块用于法条、指南与案例检索。",
    ],
    "第 2 章": [
        "建议在部署前核对服务器时区、磁盘空间与数据库连接字符串，避免影响期限计算与文档存储。",
        "生产环境请关闭调试日志级别，并定期备份数据库与上传文档目录。",
    ],
    "第 3 章": [
        "安装完成后请访问健康检查接口确认后端正常，再打开前端页面，可减少登录失败排查时间。",
        "演示环境可使用 seed 脚本导入样例案件，便于对照本手册第五章截图进行操作。",
    ],
    "第 4 章": [
        "首次登录建议修改默认密码；若忘记密码，请联系系统管理员在「用户管理」中重置。",
        "登录失败时请先确认 Caps Lock 与输入法状态，并检查账号是否被停用。",
    ],
    "第 5 章": [
        "工作台操作建议先上传齐全申请文件与 OA 文本，再运行智能体流水线，以提高答复质量。",
        "知识库检索支持组合关键词；AI 问答引用来源可在结果卡片中点击查看原文。",
        "进行答复编辑时请及时保存草稿；导出 Word 前可在预览页核对格式与引用段落。",
    ],
    "第 6 章": [
        "若问题仍未解决，请记录浏览器版本、操作步骤与报错截图，提交给技术支持人员。",
    ],
}

DEFAULT_FILLERS = [
    "本系统界面支持主流分辨率；建议使用 1920×1080 及以上显示器以获得最佳阅读体验。",
    "操作过程中如遇加载缓慢，请检查网络连接或联系管理员查看服务运行状态。",
]

# 渲染时补充的功能说明（扩充步骤与页面描述）
SECTION_EXTRAS: dict[str, dict[str, str | list[str]]] = {
    "4.4 登录界面示意": {
        "steps_extra": [
            "若账号或密码为空，系统提示「请输入账号和密码」；凭证错误时在页面顶部弹出错误提示。",
            "建议使用 Chrome、Edge 等现代浏览器访问，分辨率 1920×1080 及以上可获得最佳显示效果。",
        ],
    },
    "5.1 案件列表管理": {
        "page_desc": "案件列表页包含搜索框、状态筛选、案件表格与「进入工作台」操作列，是进入个案办理的主入口。",
        "config": "可按案件标题、申请号、客户名称检索；状态列展示 OA 待答复、撰写中等业务阶段。",
        "steps_extra": [
            "如需新建案件，可点击右上角「新建案件」，填写标题、申请号与客户信息后保存。",
            "列表中的期限列用于提示法定期限，红色或临近到期条目应优先处理。",
        ],
    },
    "5.2 答复工作台总览": {
        "page_desc": "工作台分为左侧案件信息区、中间文档阅读区、右侧 AI 工作流区，支持三栏宽度拖拽调整。",
        "config": "左栏可折叠；右栏「AI 工作流」面板可展开查看流水线步骤与策略审查结果。",
        "steps_extra": [
            "在左侧文档树中点击不同文档，可在中间区域切换查看对应 PDF 或结构化内容。",
            "若右栏未显示，可点击顶部「AI 工作流」开关重新展开面板。",
        ],
    },
    "5.3 工作台布局与面板控制": {
        "page_desc": "标签栏左侧「案件信息」与右上角「AI 工作流」分别控制左栏、右栏显隐；分隔条可拖拽调宽。",
        "config": "布局偏好写入浏览器 localStorage，刷新或下次进入同案时自动恢复。",
        "steps_extra": ["专注阅读 OA 时可暂时隐藏右栏流水线，需要运行智能体时再展开。"],
    },
    "5.4 审查意见通知书阅读": {
        "page_desc": "中间「审查意见通知书」标签页以 PDF 或结构化视图展示 OA 正文，支持滚动、选中文本。",
        "config": "划词后可唤起提问、解释、摘要等快捷菜单；PDF 区支持页目录缩略图。",
        "steps_extra": ["对比左侧文档树中的 OA 轮次，确认当前阅读的是最新一轮审查意见。"],
    },
    "5.7 知识库检索": {
        "page_desc": "知识库检索页提供关键词输入、分类筛选与结果列表，支持打开原文片段。",
        "config": "可按文档类型（法规、指南、案例等）筛选；结果卡片展示标题、摘要与相关度。",
        "steps_extra": ["组合多个关键词可缩小检索范围；点击引用来源可跳转至知识库详情。"],
    },
    "5.10 系统用户管理": {
        "page_desc": "用户管理页列出系统账号、所属部门与角色，管理员可新建、编辑与停用账号。",
        "config": "角色决定菜单可见范围；部门用于组织架构与案件归属统计。",
        "steps_extra": ["编辑用户时可分配多个角色；停用后该账号无法登录但历史数据保留。"],
    },
    "5.15 全局 AI 助手": {
        "page_desc": "助手面板含对话、快捷功能、笔记三标签；自动读取当前页面文档与选中文字作为上下文。",
        "config": "划词菜单支持提问、解释、摘要、翻译、注释；笔记可与案件上下文关联保存。",
        "steps_extra": ["在工作台阅读 OA 时，快捷功能会推荐总结审查意见、分析创造性缺陷等模板提问。"],
    },
}


class ManualPDF(FPDF):
    STYLES = {
        1: {"size": 22, "h": 12, "gap": 6},
        2: {"size": 16, "h": 10, "gap": 5},
        3: {"size": 14, "h": 8.5, "gap": 4},
        4: {"size": 12, "h": 7.5, "gap": 3},
    }

    def __init__(self, header_left: str, footer_center: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.header_left = header_left
        self.footer_center = footer_center
        self.cjk = "CJK"
        self.set_auto_page_break(auto=False)
        self.alias_nb_pages()
        self._suppress_hf = False
        self._filler_idx: dict[str, int] = {}
        self._fig_counters: dict[str, int] = {}

    def write_figure_caption(self, text: str) -> None:
        """图注居中显示。"""
        if not text.strip():
            return
        self.reset_x()
        self.set_font(self.cjk, size=CAPTION_SIZE)
        self.set_text_color(80, 80, 80)
        self.write_wrapped_lines(text.strip(), self.epw, CAPTION_LINE_H, align="C")
        self.set_text_color(0, 0, 0)
        self.ln(2)
        self.reset_x()

    def alloc_figure_caption(self, chapter_key: str, section: Section) -> str:
        """按章编号：图4-1、图5-2 …"""
        prefix = _chapter_figure_prefix(chapter_key)
        n = self._fig_counters.get(chapter_key, 0) + 1
        self._fig_counters[chapter_key] = n
        desc = _figure_desc(section)
        return f"图{prefix}-{n}  {desc}"

    def set_suppress_header_footer(self, on: bool) -> None:
        self._suppress_hf = on

    def reset_x(self) -> None:
        self.set_x(self.l_margin)

    def header(self) -> None:
        if self._suppress_hf:
            return
        self.set_font(self.cjk, size=8)
        y0 = 8
        self.set_xy(self.l_margin, y0)
        self.cell(self.epw * 0.62, 5, self.header_left, align="L")
        self.set_xy(self.l_margin + self.epw * 0.38, y0)
        self.cell(self.epw * 0.62, 5, f"第 {self.page_no()} 页 共 {{nb}} 页", align="R")
        self.reset_x()
        self.set_y(22)

    def footer(self) -> None:
        if self._suppress_hf:
            return
        self.set_y(-14)
        self.reset_x()
        self.set_font(self.cjk, size=8)
        self.cell(self.epw, 8, self.footer_center, align="C")
        self.reset_x()

    def new_content_page(self) -> None:
        self.add_page()
        self.reset_x()
        self.set_y(PAGE_TOP_Y)

    def remaining_y(self) -> float:
        return PAGE_FILL_TARGET_Y - self.get_y()

    def page_fill_ratio(self) -> float:
        span = PAGE_FILL_TARGET_Y - PAGE_TOP_Y
        return (self.get_y() - PAGE_TOP_Y) / span if span > 0 else 1.0

    def break_page_if_needed(self, chapter_key: str, min_remaining: float) -> None:
        """空间不足时先填满当前页再换页。"""
        if self.remaining_y() < min_remaining:
            if self.get_y() > MIN_CHAPTER_BREAK_Y:
                self.pad_page(chapter_key, aggressive=True)
            self.new_content_page()

    def start_chapter(self, title: str, chapter_key: str) -> None:
        """章标题：仅当本页已有较多内容时才换页；不在章标题后立即填充半页空白。"""
        if self.get_y() > MIN_CHAPTER_BREAK_Y:
            self.pad_page(chapter_key, aggressive=True)
            self.new_content_page()
        elif self.page_no() == 0:
            self.new_content_page()
        self.write_heading(2, title)

    def write_wrapped_lines(
        self,
        text: str,
        first_w: float,
        line_h: float,
        *,
        rest_w: float | None = None,
        x_first: float | None = None,
        x_rest: float | None = None,
        align: str = "L",
    ) -> None:
        """禁则换行输出；支持首行/续行不同宽度与起始 x（步骤悬挂缩进）。"""
        rest_w = first_w if rest_w is None else rest_w
        x_rest = self.l_margin if x_rest is None else x_rest
        lines = wrap_text_kinsoku(self, _protect_phrase_breaks(text), first_w, rest_w)
        for idx, line in enumerate(lines):
            w = first_w if idx == 0 else rest_w
            x = x_first if idx == 0 and x_first is not None else x_rest
            self.set_x(x)
            if align == "C":
                tw = self.get_string_width(line)
                self.set_x(x + max(0.0, (w - tw) / 2))
                self.cell(tw, line_h, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                self.cell(w, line_h, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def write_heading(self, level: int, text: str) -> None:
        level = min(max(level, 1), 4)
        st = self.STYLES[level]
        self.reset_x()
        if level == 3 and self.get_y() > PAGE_TOP_Y + 1:
            self.ln(SUBSECTION_LEAD_SP)
        self.set_font(self.cjk, size=st["size"])
        self.write_wrapped_lines(text, self.epw, st["h"])
        self.ln(st["gap"])
        self.reset_x()

    def write_body(self, text: str, indent_mm: float = 0, line_h: float = BODY_LINE_H) -> None:
        if not text.strip():
            return
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]
        w = self.epw - indent_mm
        x = self.l_margin + indent_mm
        for pi, para in enumerate(paragraphs):
            if pi > 0:
                self.ln(1)
            self.reset_x()
            self.set_font(self.cjk, size=BODY_SIZE)
            self.write_wrapped_lines(para, w, line_h, x_first=x, x_rest=x)
        self.ln(2)
        self.reset_x()

    def write_step(self, num: str, text: str) -> None:
        """步骤编号与正文同一行起始，后续换行悬挂于正文下方。"""
        indent_mm = 5.0
        line_h = STEP_LINE_H
        self.reset_x()
        self.set_font(self.cjk, size=BODY_SIZE)
        label = _protect_phrase_breaks(f"步骤 {num}  ")
        body = text.strip()
        label_w = self.get_string_width(label)
        base_x = self.l_margin + indent_mm
        content_w = self.epw - indent_mm - label_w
        full_w = self.epw - indent_mm
        if content_w < 24:
            self.set_x(base_x)
            self.cell(label_w, line_h, label, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.write_wrapped_lines(body, full_w, line_h, x_first=base_x, x_rest=base_x)
        else:
            self.set_x(base_x)
            self.cell(label_w, line_h, label, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.write_wrapped_lines(
                body,
                content_w,
                line_h,
                rest_w=full_w,
                x_first=self.get_x(),
                x_rest=base_x,
            )
        self.ln(2)
        self.reset_x()

    def _table_col_widths(self, ncols: int) -> list[float]:
        epw = self.epw
        if ncols == 2:
            return [42.0, epw - 42.0]
        if ncols == 3:
            w1, w2 = 34.0, 58.0
            return [w1, w2, epw - w1 - w2]
        if ncols == 4:
            # WOA Agent 顺序表等：步骤窄、阶段与 Agent 适中、说明列最宽
            ratios = [0.08, 0.22, 0.24, 0.46]
            widths = [epw * r for r in ratios]
            widths[-1] = epw - sum(widths[:-1])
            return widths
        if ncols == 8:
            # 字典权限对照表：首列较宽，中间列紧凑
            ratios = [0.15, 0.13, 0.09, 0.09, 0.11, 0.11, 0.13, 0.19]
            widths = [epw * r for r in ratios]
            widths[-1] = epw - sum(widths[:-1])
            return widths
        return [epw / ncols] * ncols

    def write_table(self, rows: list[list[str]]) -> None:
        if not rows:
            return
        self.reset_x()
        self.set_font(self.cjk, size=BODY_SIZE)
        ncols = max(len(r) for r in rows)
        widths = self._table_col_widths(ncols)
        lh = 6.0 if ncols >= 4 else (6.5 if ncols >= 6 else 7.0)
        pad = 1.8
        for row in rows:
            self.reset_x()
            cells = [
                _protect_phrase_breaks(_strip_md(c))
                for c in row + [""] * (ncols - len(row))
            ]
            y0 = self.get_y()
            x0 = self.l_margin
            inner_ws = [max(8.0, widths[ci] - 2 * pad) for ci in range(ncols)]

            cell_lines: list[list[str]] = []
            max_h = lh + 2 * pad
            for ci, cell in enumerate(cells[:ncols]):
                lines = wrap_text_kinsoku(self, cell or " ", inner_ws[ci], inner_ws[ci])
                cell_lines.append(lines if lines else [" "])
                max_h = max(max_h, lh * len(cell_lines[-1]) + 2 * pad)

            x = x0
            for ci in range(ncols):
                self.rect(x, y0, widths[ci], max_h)
                x += widths[ci]

            x = x0
            for ci, lines in enumerate(cell_lines):
                for li, line in enumerate(lines):
                    self.set_xy(x + pad, y0 + pad + li * lh)
                    self.cell(
                        inner_ws[ci],
                        lh,
                        line,
                        new_x=XPos.RIGHT,
                        new_y=YPos.TOP,
                    )
                x += widths[ci]

            self.set_y(y0 + max_h)
            self.reset_x()
        self.ln(4)

    def pad_page(self, chapter_key: str = "", *, aggressive: bool = False) -> None:
        fillers = CHAPTER_FILLERS.get(chapter_key, []) + DEFAULT_FILLERS
        idx = self._filler_idx.get(chapter_key, 0)
        threshold = PAGE_FILL_TARGET_Y - (6 if aggressive else 18)
        while self.get_y() < threshold and idx < len(fillers):
            self.write_body(fillers[idx], line_h=BODY_LINE_H)
            idx += 1
        self._filler_idx[chapter_key] = idx

    def estimate_table_height(self, rows: list[list[str]]) -> float:
        return 8.0 + len(rows) * 8.0

    def write_text_section(self, sec: Section, chapter_key: str) -> None:
        """无图小节：标题+正文+表格+步骤，尽量接在前文同页。"""
        need = 20.0
        if sec.intro:
            need += 18.0
        if sec.table_rows:
            need += self.estimate_table_height(sec.table_rows)
        need += len(sec.steps) * 9.0 + (12.0 if sec.expected else 0.0)
        self.break_page_if_needed(chapter_key, need)

        self.write_heading(3, sec.title)
        if sec.intro:
            self.write_body(sec.intro)
        if sec.table_rows:
            self.write_table(sec.table_rows)
        for extra_tbl in sec.extra_tables:
            self.write_table(extra_tbl)
        for i, step in enumerate(sec.steps, 1):
            if self.remaining_y() < 12:
                self.pad_page(chapter_key, aggressive=True)
                self.new_content_page()
                self.write_heading(4, f"{sec.title}（续）")
            self.write_step(str(i), step)
        if sec.expected:
            self.write_body(f"预期结果：{sec.expected}")

    def write_faq_section(self, sec: Section, chapter_key: str) -> None:
        """常见问题：分段展示现象、原因与处理方法，不使用表格。"""
        need = 24.0 + len(sec.steps) * 12.0 + (14.0 if sec.intro else 0.0)
        self.break_page_if_needed(chapter_key, need)
        self.write_heading(3, sec.title)
        if sec.intro:
            self.write_body(sec.intro)
        for item in sec.steps:
            if self.remaining_y() < 14:
                self.new_content_page()
                self.write_heading(4, f"{sec.title}（续）")
            self.write_body(item)
        self.ln(2)
        if self.page_fill_ratio() < 0.6:
            self.pad_page(chapter_key, aggressive=True)

    def image_size_for_box(self, img_path: Path, max_w: float, max_h: float) -> tuple[float, float]:
        if Image is not None:
            with Image.open(img_path) as im:
                w_px, h_px = im.size
        else:
            w_px, h_px = 1440, 900
        ratio = min(max_w / max(w_px, 1), max_h / max(h_px, 1))
        return w_px * ratio, h_px * ratio

    def write_image_page(self, section: Section, base: Path, chapter_key: str) -> None:
        """每页最多一张图；同页排版优先，图片等比缩放不拉伸。"""
        extras = SECTION_EXTRAS.get(section.title.split("（")[0], {})
        tbl_h = 0.0
        if section.table_rows:
            tbl_h += self.estimate_table_height(section.table_rows)
        for extra_tbl in section.extra_tables:
            tbl_h += self.estimate_table_height(extra_tbl)
        need_h = 28 + tbl_h + 70
        if self.get_y() > MIN_CHAPTER_BREAK_Y + 8:
            self.pad_page(chapter_key, aggressive=True)
            self.new_content_page()
        elif self.remaining_y() < need_h and self.get_y() > PAGE_TOP_Y + 20:
            self.new_content_page()

        self.write_heading(3, section.title)
        intro = section.intro
        if extras.get("intro_extra"):
            intro = (intro + " " if intro else "") + extras["intro_extra"]
        if intro:
            self.write_body(intro)
        if section.table_rows:
            if self.remaining_y() < self.estimate_table_height(section.table_rows) + 10:
                self.new_content_page()
                self.write_heading(4, f"{section.title}（续）")
            self.write_table(section.table_rows)
        for extra_tbl in section.extra_tables:
            if self.remaining_y() < self.estimate_table_height(extra_tbl) + 10:
                self.new_content_page()
                self.write_heading(4, f"{section.title}（续）")
            self.write_table(extra_tbl)
        if extras.get("page_desc"):
            self.write_body(f"页面说明：{extras['page_desc']}")
        if extras.get("config"):
            self.write_body(f"页面配置：{extras['config']}")

        img_path = (base / section.image.replace("\\", "/")).resolve() if section.image else None
        min_img_h = 95.0
        caption_h = 14.0 if section.image else 0.0
        # 仅判断「当前页能否放下截图+图注」，步骤/预期结果可续页
        if img_path and self.remaining_y() < min_img_h + caption_h + 8:
            self.new_content_page()
            self.write_heading(4, f"{section.title}（续）")
        max_img_h = max(min_img_h, min(155.0, self.remaining_y() - caption_h - 10))

        if img_path and img_path.is_file():
            try:
                self.reset_x()
                img_w, img_h = self.image_size_for_box(img_path, self.epw, max_img_h)
                x = self.l_margin + (self.epw - img_w) / 2
                self.image(str(img_path), x=x, w=img_w, h=img_h)
                self.ln(3)
            except Exception as e:
                self.write_body(f"[图片加载失败: {e}]")
        elif section.image:
            self.write_body(f"【缺少截图: {section.image}】")

        if section.image:
            self.write_figure_caption(self.alloc_figure_caption(chapter_key, section))

        if section.post_image:
            self.write_body(section.post_image)

        all_steps = list(section.steps)
        for extra in extras.get("steps_extra", []):
            all_steps.append(extra)
        for i, step in enumerate(all_steps, 1):
            if self.remaining_y() < 14:
                self.new_content_page()
                self.write_heading(4, f"{section.title}（续）")
            self.write_step(str(i), step)

        if section.expected:
            if self.remaining_y() < 12:
                self.new_content_page()
            self.write_body(f"预期结果：{section.expected}")

        if self.page_fill_ratio() < 0.55:
            self.pad_page(chapter_key, aggressive=True)


def _strip_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    return re.sub(r"`(.+?)`", r"\1", text).strip()


def _chapter_figure_prefix(chapter_key: str) -> str:
    m = re.search(r"第\s*(\d+)\s*章", chapter_key)
    if m:
        return m.group(1)
    m = re.search(r"附录\s*([A-Za-z])", chapter_key)
    if m:
        return m.group(1)
    return "0"


def _figure_desc(section: Section) -> str:
    if section.caption.strip():
        return section.caption.strip()
    title = re.sub(r"^\d+(?:\.\d+)*\s*", "", section.title)
    title = re.sub(r"（\d+）|（续）", "", title).strip()
    return title or "界面截图"


def _parse_table_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_markdown(md: str, base: Path) -> tuple[list[Block], list[TocEntry]]:
    """Parse MD into blocks; TOC titles collected separately."""
    lines = md.splitlines()
    blocks: list[Block] = []
    toc_titles: list[TocEntry] = []
    i = 0
    _guard = 0
    _max_guard = len(lines) * 5 + 100

    while i < len(lines):
        _guard += 1
        if _guard > _max_guard:
            raise RuntimeError(f"parse_markdown stuck at line {i}: {lines[i]!r}")
        s = lines[i].strip()
        if not s or s == "---":
            i += 1
            continue
        if s.startswith("**著作权人") or s.startswith("**文档") or s.startswith("**编写"):
            i += 1
            continue
        if s == "## 目录":
            i += 1
            while i < len(lines):
                ls = lines[i].strip()
                if HEADING_RE.match(ls) and "第" in ls and "章" in ls:
                    break
                i += 1
            continue
        if re.match(r"^\d+\.\s", s) and "章" not in s:
            i += 1
            continue

        hm = HEADING_RE.match(s)
        if hm:
            level = len(hm.group(1))
            title = _strip_md(hm.group(2))
            if level == 1 and "操作手册" in title:
                i += 1
                continue
            if level == 2 and (("第" in title and "章" in title) or title.startswith("附录")):
                toc_titles.append(TocEntry(2, title))
                blocks.append(Block(kind="h2", text=title))
                i += 1
                continue
            if level >= 3:
                toc_titles.append(TocEntry(3, title))
                sec = Section(title=title)
                i += 1
                part = 0
                while i < len(lines):
                    ls = lines[i].strip()
                    if not ls or ls == "---":
                        i += 1
                        continue
                    if HEADING_RE.match(ls):
                        break
                    if IMG_RE.match(ls):
                        if sec.image:
                            blocks.append(Block(kind="section", section=sec))
                            part += 1
                            suffix = f"（{part}）" if part > 0 else "（续）"
                            sec = Section(title=title + suffix, intro="")
                        m = IMG_RE.match(ls)
                        sec.caption = m.group(1)
                        sec.image = m.group(2)
                        i += 1
                        continue
                    sm = STEP_RE.match(ls)
                    if sm:
                        sec.steps.append(_strip_md(sm.group(2)))
                        i += 1
                        continue
                    if ls.startswith("**预期结果**"):
                        sec.expected = _strip_md(ls.replace("**预期结果**", "").strip())
                        i += 1
                        continue
                    faq_m = FAQ_LABEL_RE.match(ls)
                    if faq_m:
                        label, text = faq_m.group(1), _strip_md(faq_m.group(2))
                        if label == "预期结果":
                            sec.expected = text
                        elif label == "建设目标":
                            sec.intro += (" " if sec.intro else "") + text
                        else:
                            sec.steps.append(f"{label}：{text}")
                        i += 1
                        continue
                    if ls.startswith("|"):
                        tbl: list[list[str]] = []
                        while i < len(lines) and lines[i].strip().startswith("|"):
                            row = lines[i].strip()
                            i += 1
                            if re.match(r"^\|[-:\s|]+\|$", row):
                                continue
                            tbl.append(_parse_table_row(row))
                        if sec.table_rows:
                            sec.extra_tables.append(tbl)
                        else:
                            sec.table_rows = tbl
                        continue
                    if any(ls.startswith(f"**{p}") for p in SKIP_META_PREFIXES):
                        i += 1
                        continue
                    if INTRO_LABEL_ONLY_RE.match(ls):
                        m = INTRO_LABEL_ONLY_RE.match(ls)
                        label = _strip_md(m.group(1)) if m else ls
                        _append_section_prose(sec, f"{label}：")
                        i += 1
                        continue
                    ilm = INTRO_LABEL_RE.match(ls)
                    if ilm and not STEP_RE.match(ls) and not FAQ_LABEL_RE.match(ls):
                        inline_parts = _split_inline_intro_line(ls)
                        if len(inline_parts) > 1:
                            for part in inline_parts:
                                _append_section_prose(sec, part)
                        else:
                            label = _strip_md(ilm.group(1))
                            rest = _strip_md(ilm.group(2))
                            if rest:
                                _append_section_prose(sec, f"{label}：{rest}")
                            else:
                                _append_section_prose(sec, f"{label}：")
                        i += 1
                        continue
                    _append_section_prose(sec, _strip_md(ls))
                    i += 1
                blocks.append(Block(kind="section", section=sec))
                continue
            i += 1
            continue

        if s.startswith("|") and i + 1 < len(lines) and "|" in lines[i + 1]:
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                i += 1
                if re.match(r"^\|[-:\s|]+\|$", row):
                    continue
                rows.append(_parse_table_row(row))
            blocks.append(Block(kind="table", rows=rows))
            continue

        para: list[str] = []
        while i < len(lines):
            ls = lines[i].strip()
            if not ls or ls == "---" or HEADING_RE.match(ls) or ls.startswith("|"):
                break
            if IMG_RE.match(ls):
                break
            para.append(_strip_md(ls))
            i += 1
        if para:
            blocks.append(Block(kind="para", text=" ".join(para)))
        else:
            i += 1
        continue

    return blocks, toc_titles


def _render_body(
    pdf: ManualPDF,
    blocks: list[Block],
    base: Path,
    *,
    record_toc: list[TocEntry] | None = None,
    toc_offset: int = 0,
) -> None:
    chapter_key = ""
    content_started = False

    for bi, block in enumerate(blocks):
        if block.kind == "h2":
            ch_m = re.search(r"第\s*\d+\s*章", block.text)
            chapter_key = ch_m.group(0) if ch_m else block.text
            pdf._filler_idx[chapter_key] = 0
            pdf._fig_counters[chapter_key] = 0
            if record_toc is not None:
                for t in record_toc:
                    if t.title == block.text and t.level == 2:
                        t.page = pdf.page_no() + toc_offset
            if block.text.startswith("附录") and content_started:
                pdf.pad_page(chapter_key, aggressive=True)
                pdf.new_content_page()
                pdf.write_heading(2, block.text)
            elif not content_started:
                pdf.new_content_page()
                content_started = True
                pdf.write_heading(2, block.text)
            else:
                pdf.start_chapter(block.text, chapter_key)
            continue

        if not content_started:
            pdf.new_content_page()
            content_started = True

        if block.kind == "para":
            pdf.break_page_if_needed(chapter_key, 25)
            pdf.write_body(block.text)

        elif block.kind == "table":
            h = pdf.estimate_table_height(block.rows)
            pdf.break_page_if_needed(chapter_key, h + 10)
            pdf.write_table(block.rows)

        elif block.kind == "section" and block.section:
            sec = block.section
            if record_toc is not None:
                for t in record_toc:
                    if t.title == sec.title and t.level == 3:
                        t.page = pdf.page_no() + toc_offset
            if chapter_key == "第 6 章" and not sec.image:
                pdf.write_faq_section(sec, chapter_key)
            elif sec.image:
                pdf.write_image_page(sec, base, chapter_key)
            else:
                pdf.write_text_section(sec, chapter_key)

        # 章末：下一 block 是新章且本页尚空，则填充
        next_is_h2 = bi + 1 < len(blocks) and blocks[bi + 1].kind == "h2"
        if next_is_h2 and pdf.page_fill_ratio() < 0.72:
            pdf.pad_page(chapter_key, aggressive=True)


def _write_cover(
    pdf: ManualPDF,
    full_name: str,
    version: str,
    applicant: str,
    doc_date: str,
) -> None:
    pdf.set_suppress_header_footer(True)
    pdf.add_page()
    pdf.reset_x()
    pdf.set_y(78)
    pdf.set_font(pdf.cjk, size=22)
    pdf.multi_cell(pdf.epw, 14, full_name, align="C")
    pdf.ln(8)
    pdf.set_font(pdf.cjk, size=18)
    pdf.multi_cell(pdf.epw, 10, f"{version}  用户操作手册", align="C")
    pdf.set_y(218)
    pdf.set_font(pdf.cjk, size=12)
    pdf.multi_cell(pdf.epw, 8, applicant, align="C")
    pdf.ln(8)
    pdf.multi_cell(pdf.epw, 8, f"编写日期：{doc_date}", align="C")
    pdf.set_suppress_header_footer(False)


def _count_toc_pages(entries: list[TocEntry]) -> int:
    """与 _write_toc_pages 使用相同换页规则，供 pass1 计算正文页码偏移。"""
    valid = sum(1 for e in entries if e.page > 0)
    if valid == 0:
        return 1
    y = TOC_BODY_START_Y
    pages = 1
    for _ in range(valid):
        if y + TOC_LINE_H > TOC_MAX_Y:
            pages += 1
            y = TOC_CONT_START_Y
        y += TOC_LINE_H
    return pages


def _write_toc_entry(pdf: ManualPDF, entry: TocEntry) -> None:
    if entry.page <= 0:
        return
    indent = 12 if entry.level >= 3 else 0
    x0 = pdf.l_margin + indent
    y0 = pdf.get_y()
    page_str = str(entry.page)
    page_w = max(14.0, pdf.get_string_width(page_str) + 2)
    title = _protect_phrase_breaks(entry.title)
    title_w = pdf.get_string_width(title)
    x_page = pdf.l_margin + pdf.epw - page_w
    x_dots_start = x0 + title_w + 3
    dots_width = max(0.0, x_page - x_dots_start - 2)
    dot_w = pdf.get_string_width(".") or 1.0
    ndots = max(3, int(dots_width / dot_w))

    pdf.set_xy(x0, y0)
    pdf.cell(title_w, TOC_LINE_H, title, align="L")
    if dots_width > 4:
        pdf.set_xy(x_dots_start, y0)
        pdf.cell(dots_width, TOC_LINE_H, "." * ndots, align="L")
    pdf.set_xy(x_page, y0)
    pdf.cell(page_w, TOC_LINE_H, page_str, align="R")
    pdf.set_y(y0 + TOC_LINE_H)


def _write_toc_pages(pdf: ManualPDF, entries: list[TocEntry]) -> int:
    """写入目录（支持虚线引导符与多页续排），返回目录占用页数。"""
    pdf.set_suppress_header_footer(True)
    start_page = pdf.page_no()
    pdf.add_page()
    pdf.reset_x()
    pdf.set_y(TOC_TITLE_Y)
    pdf.set_font(pdf.cjk, size=20)
    pdf.multi_cell(pdf.epw, 12, "目  录", align="C")
    pdf.ln(16)
    pdf.set_font(pdf.cjk, size=11)

    continued = False
    for entry in entries:
        if pdf.get_y() + TOC_LINE_H > TOC_MAX_Y:
            pdf.add_page()
            pdf.reset_x()
            pdf.set_y(TOC_CONT_START_Y)
            if not continued:
                pdf.set_font(pdf.cjk, size=14)
                pdf.cell(pdf.epw, 10, "目录（续）", align="C")
                pdf.ln(10)
                pdf.set_font(pdf.cjk, size=11)
                continued = True
        _write_toc_entry(pdf, entry)

    pdf.set_suppress_header_footer(False)
    return pdf.page_no() - start_page


def render_manual_pdf(
    manual_path: Path,
    out_path: Path,
    header: str,
    footer: str,
    cjk_font: Path,
    meta: dict,
) -> int:
    md = manual_path.read_text(encoding="utf-8")
    base = manual_path.parent
    blocks, toc_titles = parse_markdown(md, base)

    # —— Pass 1：仅正文，记录目录页码 ——
    pdf1 = ManualPDF(header, footer)
    pdf1.add_font("CJK", "", str(cjk_font))
    pdf1.set_margins(18, 24, 18)
    pdf1.new_content_page()
    toc1 = [TocEntry(e.level, e.title) for e in toc_titles]
    _render_body(pdf1, blocks, base, record_toc=toc1, toc_offset=0)

    toc_page_count = _count_toc_pages(toc1)
    content_offset = 1 + toc_page_count  # 封面 + 目录页数
    for e in toc1:
        if e.page > 0:
            e.page += content_offset

    # —— Pass 2：封面 + 目录 + 正文 ——
    pdf = ManualPDF(header, footer)
    pdf.add_font("CJK", "", str(cjk_font))
    pdf.set_margins(18, 24, 18)

    full_name = meta.get("full_name", "")
    version = meta.get("version", "")
    applicant = meta.get("applicant", footer)
    doc_date = meta.get("date", "")

    _write_cover(pdf, full_name, version, applicant, doc_date)
    written_toc_pages = _write_toc_pages(pdf, toc1)
    if written_toc_pages != toc_page_count:
        print(
            f"warn: toc pages estimate={toc_page_count} actual={written_toc_pages}",
            file=sys.stderr,
        )
    _render_body(pdf, blocks, base, record_toc=None, toc_offset=0)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return pdf.page_no()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--scope", type=Path, default=None)
    parser.add_argument("--manual", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = args.project_root.resolve()
    scope_path = args.scope
    if scope_path and not scope_path.is_absolute():
        scope_path = root / scope_path
    scope = load_scope(scope_path) if scope_path and scope_path.is_file() else {}
    sw = scope.get("software", {})
    ap = scope.get("applicant", {})
    pdf_cfg = scope.get("pdf", {})
    out_cfg = scope.get("output", {})

    full_name = sw.get("full_name", "软件全称")
    version = sw.get("version", "V1.0")
    applicant_name = ap.get("name", "著作权人")
    header = pdf_cfg.get("manual_header", f"{full_name} {version} 操作手册")

    manual_path = args.manual or (root / "soft-copyright" / "manual" / "操作说明书.md")
    if not manual_path.is_file():
        print(f"Manual not found: {manual_path}", file=sys.stderr)
        return 1

    cjk_path = pdf_cfg.get("cjk_font_path") or ""
    cjk = Path(cjk_path) if cjk_path and Path(cjk_path).exists() else find_cjk_font()
    if not cjk:
        print("CJK font not found", file=sys.stderr)
        return 1

    out_dir = args.output or Path(out_cfg.get("dir", "soft-copyright/output"))
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_name = pdf_cfg.get("manual_filename", f"{full_name}{version}-操作手册.pdf")
    for ch in '<>:"/\\|?*':
        out_name = out_name.replace(ch, "_")
    out_path = out_dir / out_name

    from datetime import date

    pages = render_manual_pdf(
        manual_path,
        out_path,
        header,
        applicant_name,
        cjk,
        meta={
            "full_name": full_name,
            "version": version,
            "applicant": applicant_name,
            "date": date.today().isoformat(),
        },
    )
    result = {
        "path": str(out_path),
        "pages": pages,
        "header": header,
        "footer": applicant_name,
        "layout": "cover+toc+chapters, one image per page, padded body",
    }
    (out_dir / "manual_pdf_meta.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
