#!/usr/bin/env python3
"""
generate.py — 自动生成旅行指南 HTML

从 Markdown 笔记自动生成 travel-guide.html。
修改笔记后双击运行即可更新网页。

零依赖：仅使用 Python 标准库。
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════
# 1. 配置
# ═══════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "travel-guide.html"

CITY_CONFIG = {
    "西安": {"name_cn": "西安", "css_class": "city-xian", "icon": "西",
             "dates": "7.15 — 7.17", "subtitle": "华山 · 兵马俑 · 回坊美食",
             "color": "#c44536"},
    "兰州": {"name_cn": "兰州", "css_class": "city-lanzhou", "icon": "兰",
             "dates": "7.18 — 7.20", "subtitle": "牛肉面 · 黄河 · 丹霞",
             "color": "#d4950b"},
    "成都": {"name_cn": "成都", "css_class": "city-chengdu", "icon": "蓉",
             "dates": "7.21 — 7.24", "subtitle": "熊猫 · 三国 · 三星堆",
             "color": "#2e8b57"},
}


# ═══════════════════════════════════════════
# 2. 数据模型
# ═══════════════════════════════════════════

@dataclass
class TimelineItem:
    """时间轴上的单个条目"""
    time: str          # 时间标签，如 "08:00" 或 "08:00~09:00"
    content: str       # 活动描述 HTML


@dataclass
class TimelineSection:
    """时间轴的子段落（如「上午段」「下午主线」）"""
    title: str
    items: list = field(default_factory=list)


@dataclass
class Reminder:
    """提醒框"""
    title: str
    items: list = field(default_factory=list)  # HTML 字符串列表


@dataclass
class DayCard:
    """一天的卡片"""
    day_label: str     # "Day 1 · 7.15"
    title: str         # 卡片标题
    sections: list = field(default_factory=list)      # list of TimelineSection
    reminders: list = field(default_factory=list)     # list of Reminder
    extra_html: str = ""   # 兜底 HTML（无法解析的内容）
    default_open: bool = False


@dataclass
class CityData:
    """城市的所有数据"""
    config: dict
    days: list = field(default_factory=list)
    global_reminders: list = field(default_factory=list)  # 来自 *部分.md


@dataclass
class TripData:
    """整个旅行的数据"""
    departure_items: list = field(default_factory=list)    # TimelineItem
    departure_title: str = "大竹 → 达州 → 西安"
    cities: dict = field(default_factory=dict)             # name → CityData


# ═══════════════════════════════════════════
# 3. 预处理
# ═══════════════════════════════════════════

def preprocess(text: str) -> str:
    """统一规范化文本，消除格式差异"""

    # 移除 Obsidian 图片嵌入
    text = re.sub(r'!\[\[.*?\]\]', '', text)

    # Obsidian 链接 → 如果是指向其他笔记的链接（含日期或"部分"），直接移除
    # 否则提取为纯文本
    def _replace_link(m):
        target = m.group(1)
        # 指向其他笔记的链接 → 移除（避免残留纯文本混入正文）
        if re.search(r'\d+\.\d+', target) or '部分' in target:
            return ''
        return target
    text = re.sub(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', _replace_link, text)

    # ==高亮== → <mark>高亮</mark>
    text = re.sub(r'==(.+?)==', r'<mark>\1</mark>', text)

    # 全角符号 → 半角
    text = text.replace('：', ':')
    text = text.replace('～', '~')
    text = text.replace('（', '(')
    text = text.replace('）', ')')
    # 全角逗号句号保留（中文排版需要）

    # <font color="..."> → <span style="color:...">
    text = re.sub(
        r'<font color="([^"]+)">(.*?)</font>',
        r'<span style="color:\1">\2</span>',
        text
    )

    # 时间分隔符统一：-- → –
    # (保留 ~ 用于后续解析)
    text = re.sub(r'(\d{1,2}:\d{2})\s*--\s*(\d{1,2}:\d{2})', r'\1–\2', text)

    # 移除独立的水平线（但保留上下文）
    text = re.sub(r'\n---\n', '\n', text)

    return text


def strip_markdown_formatting(text: str) -> str:
    """移除行内 Markdown 标记，返回纯文本"""
    # 粗体
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # 斜体
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # 行内代码
    text = re.sub(r'`(.+?)`', r'\1', text)
    return text


# ═══════════════════════════════════════════
# 4. 文件发现
# ═══════════════════════════════════════════

def discover_files() -> dict:
    """
    扫描子文件夹，返回按城市分组的文件列表。
    返回: { "西安": [Path, ...], "兰州": [...], "成都": [...], "departure": Path }
    """
    result = {"departure": None, "西安": [], "兰州": [], "成都": []}

    for city in ["西安", "兰州", "成都"]:
        city_dir = BASE_DIR / city
        if city_dir.is_dir():
            # 获取所有 .md 文件
            md_files = sorted(city_dir.glob("*.md"))
            # 分离 *部分.md 和每日笔记
            overview = [f for f in md_files if "部分" in f.name]
            days = [f for f in md_files if "部分" not in f.name]
            # 按文件名排序以确保日期顺序
            days.sort(key=lambda p: p.name)
            result[city] = {"days": days, "overview": overview[0] if overview else None}

    # 出发日文件
    dep_file = BASE_DIR / "7.14Departure.md"
    if dep_file.exists():
        result["departure"] = dep_file

    return result


# ═══════════════════════════════════════════
# 5. 通用工具
# ═══════════════════════════════════════════

def extract_reminders_from_section(lines: list, start_idx: int) -> tuple:
    """
    从标题行开始提取提醒框内容。
    返回 (Reminder, 结束行索引)
    """
    title_line = lines[start_idx].strip()
    # 提取标题文本（去掉 ## 和 markdown 标记）
    title = re.sub(r'^#+\s*', '', title_line)
    title = strip_markdown_formatting(title)

    items = []
    i = start_idx + 1
    while i < len(lines):
        line = lines[i].strip()
        # 遇到下一个标题或空行后的非列表行则停止
        if line.startswith('#'):
            break
        if re.match(r'^\d+\.\s', line) or line.startswith('- ') or line.startswith('* '):
            # 列表项
            content = re.sub(r'^(\d+\.\s|[-*]\s)', '', line)
            items.append(html_inline(content))
        elif line == '':
            i += 1
            continue
        else:
            # 非列表的普通文本行
            if not items and line:
                items.append(html_inline(line))
            elif line:
                items.append(html_inline(line))
        i += 1

    # 如果 items 只有 1 个长文本，可能是不带列表的提醒
    return Reminder(title=title, items=items), i


def html_inline(text: str) -> str:
    """轻量 Markdown 行内元素 → HTML"""
    # 粗体
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # 斜体
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # 行内代码（保留原样，已经是 HTML 的用 <code>）
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # mark 标签（来自预处理的 == ==）
    # 已经由 preprocess 处理，但以防万一
    text = re.sub(r'==(.+?)==', r'<mark>\1</mark>', text)
    return text


def is_reminder_header(line: str) -> bool:
    """判断是否是提醒框标题"""
    keywords = ['提醒', '⚠️', '前置', '重要', '费用', '装备', '购票', '避坑', '关键']
    return any(kw in line for kw in keywords)


# ═══════════════════════════════════════════
# 6. 出发日解析器
# ═══════════════════════════════════════════

def parse_departure(text: str) -> TripData:
    """解析 7.14Departure.md"""
    trip = TripData()

    # 匹配时间模式
    time_patterns = [
        # 上午/下午/晚上 + 时间
        r'(上午|下午|晚上|约)?(\d{1,2}[:：]\d{2})',
        # 纯时间范围
        r'(\d{1,2}:\d{2})\s*[–~-]+\s*(\d{1,2}:\d{2})',
    ]

    # 转为逐行处理
    lines = text.strip().split('\n')
    current_date = ""
    items = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检测日期标题（如 "7.14", "7.18"）
        date_match = re.match(r'^(\d+\.\d+)\s*$', line)
        if date_match:
            if current_date and items:
                # 保存上一段
                trip.departure_items.extend(items)
                items = []
            current_date = date_match.group(1)
            continue

        # 跳过纯城市名（原 wikilink 如 [[西安部分]] 预处理后的残留）
        if re.match(r'^[一-鿿]{2,4}部分$', line) or line in ('西安', '兰州', '成都'):
            continue

        # 匹配时间模式（优先时间范围，避免 13:16–19:22 被截断为 13:16）
        # 1. 时间范围 13:16–19:22 或 K692 13:16--19:22
        m = re.search(r'(\d{1,2}:\d{2})\s*[–-]+\s*(\d{1,2}:\d{2})', line)
        if m:
            time_str = f"{m.group(1)}–{m.group(2)}"
            # 取整行作为内容（去掉已提取的时间部分重叠）
            content = html_inline(line)
            items.append(TimelineItem(time=time_str, content=content))
            continue

        # 2. 上午/下午/晚上 + 时间
        m = re.search(r'(上午|下午|晚上|约)?\s*(\d{1,2}[:：]\d{2})', line)
        if m:
            period = m.group(1) or ''
            time_str = period + m.group(2)
            content = line[m.end():].strip()
            if not content:
                content = line[:m.start()].strip()
            content = html_inline(content)
            items.append(TimelineItem(time=time_str, content=content))
            continue

        # 3. 其他有意义的内容
        if line and not line.startswith('#'):
            content = html_inline(line)
            items.append(TimelineItem(time="", content=content))

    if items:
        trip.departure_items.extend(items)

    return trip


# ═══════════════════════════════════════════
# 7. 西安解析器（### HH:MM 格式）
# ═══════════════════════════════════════════

def parse_xian(text: str, filename: str) -> DayCard:
    """解析西安风格的笔记（有 ### HH:MM 时间标题）"""
    lines = text.strip().split('\n')
    return _parse_heading_style(lines, filename)


def _parse_heading_style(lines: list, filename: str) -> DayCard:
    """通用标题层级解析器（西安风）"""
    card = DayCard(day_label="", title="", sections=[], reminders=[])

    # 提取日期信息
    date_match = re.search(r'(\d+\.\d+)', filename)
    date_str = date_match.group(1) if date_match else ""

    # 解析主要标题
    h1_title = ""
    for line in lines:
        if line.strip().startswith('# ') and not line.strip().startswith('## '):
            h1_title = line.strip()[2:].strip()
            h1_title = strip_markdown_formatting(h1_title)
            break

    card.title = h1_title or filename.replace('.md', '')
    card.day_label = date_str

    # 第一遍：找出所有 ## 标题的位置，分割大段
    sections_boundaries = []
    for i, line in enumerate(lines):
        if line.strip().startswith('## ') and not line.strip().startswith('### '):
            sections_boundaries.append(i)

    if not sections_boundaries:
        # 没有 ## 标题，整篇作为一个段落
        sections_boundaries = [0]

    # 第二遍：解析每个 ## 段
    for idx, start in enumerate(sections_boundaries):
        end = sections_boundaries[idx + 1] if idx + 1 < len(sections_boundaries) else len(lines)
        section_lines = lines[start:end]
        section_title = section_lines[0].strip()[3:].strip() if section_lines[0].strip().startswith('##') else ""
        section_title = strip_markdown_formatting(section_title)

        # 判断是否是提醒段
        if is_reminder_header(section_title):
            reminder, _ = extract_reminders_from_section(lines, start)
            card.reminders.append(reminder)
            continue

        # 解析时间线项目
        timeline_items = _parse_timeline_from_section(section_lines, is_xian=True)

        if timeline_items:
            # 提取简短的段落标题
            short_title = _shorten_section_title(section_title)
            card.sections.append(TimelineSection(title=short_title, items=timeline_items))
        elif section_title:
            # 有标题但没有时间线项目，可能包含其他内容
            content_lines = []
            for line in section_lines[1:]:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    content_lines.append(html_inline(stripped))
            if content_lines:
                content = '<br>'.join(content_lines)
                card.sections.append(TimelineSection(
                    title=_shorten_section_title(section_title),
                    items=[TimelineItem(time="", content=content)]
                ))

    return card


def _parse_timeline_from_section(section_lines: list, is_xian: bool = False) -> list:
    """
    从段落中提取时间线项目。
    西安格式：### HH:MM 标题 + #### 子标题
    """
    items = []
    i = 0

    # 跳过段标题行
    if section_lines and section_lines[0].strip().startswith('##'):
        i = 1

    current_subtitle = ""
    while i < len(section_lines):
        line = section_lines[i].strip()

        # ### HH:MM 格式的时间条目
        m = re.match(r'^###\s+(\d{1,2}:\d{2})', line)
        if m:
            time_str = m.group(1)
            # 标题的其余部分作为内容
            rest = line[m.end():].strip()
            rest = re.sub(r'^[–\-—~]\s*', '', rest)  # 去掉开头的破折号
            # 收集该条目下的所有内容
            content_parts = []
            if rest:
                content_parts.append(html_inline(rest))

            i += 1
            while i < len(section_lines):
                sub = section_lines[i].strip()
                # 遇到任何 #/##/###/#### 标题就断开，各自成为独立时间线条目
                if re.match(r'^#{1,4}\s', sub):
                    break
                elif sub and sub != '---':
                    content_parts.append(html_inline(sub))
                i += 1

            content = '<br>'.join(content_parts) if content_parts else ""
            items.append(TimelineItem(time=time_str, content=content))
            continue

        # 段落内部的各种子标题（# / ## / #### / 非时间的 ###）
        if re.match(r'^#{1,4}\s', line) and not re.match(r'^###\s+\d{1,2}:\d{2}', line):
            sub_title = re.sub(r'^#+\s*', '', line)
            # 尝试从子标题中提取时间
            tm = re.match(r'(\d{1,2}:\d{2}\s*[~–-]\s*\d{1,2}:\d{2})', sub_title)
            if tm:
                time_str = tm.group(1)
                rest = sub_title[tm.end():].strip()
                rest = re.sub(r'^[–\-—~]\s*', '', rest)
                content = f'<strong>{html_inline(rest)}</strong>' if rest else html_inline(sub_title)
            else:
                # 检查是否有单个时间
                tm2 = re.match(r'(\d{1,2}:\d{2})', sub_title)
                if tm2:
                    time_str = tm2.group(1)
                    rest = sub_title[tm2.end():].strip()
                    rest = re.sub(r'^[–\-—~]\s*', '', rest)
                    content = f'<strong>{html_inline(rest)}</strong>' if rest else html_inline(sub_title)
                else:
                    time_str = ""
                    content = f'<strong>{html_inline(sub_title)}</strong>'
            items.append(TimelineItem(time=time_str, content=content))
            i += 1
            continue

        # 普通文本或空行
        if line and not line.startswith('#') and line != '---':
            # 尝试提取行内时间
            time_match = re.search(r'(\d{1,2}:\d{2})', line)
            if time_match and not any(line.startswith(p) for p in ['- ', '* ', '1.', '2.', '3.']):
                time_str = time_match.group(1)
                content = html_inline(line)
                items.append(TimelineItem(time=time_str, content=content))
            elif line.startswith('- ') or line.startswith('* ') or re.match(r'^\d+\.\s', line):
                # 列表项，尝试解析时间
                content = re.sub(r'^(\d+\.\s|[-*]\s)', '', line)
                tm = re.search(r'(\d{1,2}:\d{2})', content)
                if tm:
                    time_str = tm.group(1)
                    items.append(TimelineItem(time=time_str, content=html_inline(content)))
                else:
                    items.append(TimelineItem(time="", content=html_inline(content)))
        i += 1

    return items


def _shorten_section_title(title: str) -> str:
    """缩短段落标题，去掉冗余前缀"""
    # 去掉常见前缀词
    title = re.sub(r'^[一二三四五六七八九十]+[、，,.]?\s*', '', title)
    title = re.sub(r'^第[一二三四五六七八九十]+[段步].*?[:：]?\s*', '', title)
    return title


# ═══════════════════════════════════════════
# 8. 兰州解析器（Markdown 表格格式）
# ═══════════════════════════════════════════

def parse_lanzhou(text: str, filename: str) -> DayCard:
    """解析兰州风格的笔记（含 Markdown 表格）"""
    lines = text.strip().split('\n')
    card = DayCard(day_label="", title="", sections=[], reminders=[])

    date_match = re.search(r'(\d+\.\d+)', filename)
    date_str = date_match.group(1) if date_match else ""
    card.day_label = date_str

    # 提取第一个 ## 标题作为卡片标题
    for line in lines:
        if line.strip().startswith('## '):
            title = line.strip()[3:].strip()
            card.title = strip_markdown_formatting(title)
            break

    if not card.title:
        card.title = filename.replace('.md', '')

    # 1. 提取 Markdown 表格
    table_items = _extract_markdown_table(lines)
    if table_items:
        card.sections.append(TimelineSection(title="行程时间表", items=table_items))

    # 2. 解析表格之外的段落
    # 找到表格结束后的内容
    table_end = 0
    in_table = False
    for i, line in enumerate(lines):
        if line.strip().startswith('|') and '---' not in line:
            if not in_table:
                in_table = True
        elif in_table and not line.strip().startswith('|'):
            table_end = i
            break
        elif in_table:
            table_end = i + 1

    remaining_lines = lines[table_end:]

    # 3. 解析剩余内容：标题 + 内容
    _parse_remaining_sections(remaining_lines, card)

    return card


def _extract_markdown_table(lines: list) -> list:
    """从文本中提取 Markdown 表格并转为 TimelineItem 列表"""
    items = []
    in_table = False
    header_columns = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith('|') and not re.match(r'^\|[\s\-:]+\|', stripped):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if not in_table:
                # 表头
                header_columns = cells
                in_table = True
            else:
                # 数据行
                if len(cells) >= 2:
                    time_str = cells[0]
                    activity = cells[1] if len(cells) > 1 else ""
                    note = cells[2] if len(cells) > 2 else ""

                    content_parts = [html_inline(activity)]
                    if note:
                        content_parts.append(f' <span style="color:#888;font-size:0.85rem;">({html_inline(note)})</span>')

                    items.append(TimelineItem(
                        time=time_str,
                        content=''.join(content_parts)
                    ))
        elif in_table and not stripped.startswith('|'):
            # 表格结束
            break

    return items


def _parse_remaining_sections(lines: list, card: DayCard):
    """解析表格外的剩余内容（包括标题和纯文本）"""
    i = 0

    # 先收集第一个标题之前的纯文本
    preamble_lines = []
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#'):
            break
        if line and line != '---':
            preamble_lines.append(html_inline(line))
        i += 1

    if preamble_lines:
        # 将前导文本添加为无标题段落
        for item_text in preamble_lines:
            # 尝试将破折号列表项解析为独立的时间线条目
            if item_text.startswith('【') and '】' in item_text:
                card.sections.append(TimelineSection(
                    title=item_text.strip('【】'),
                    items=[]
                ))
            else:
                card.sections.append(TimelineSection(
                    title="",
                    items=[TimelineItem(time="", content=item_text)]
                ))

    # 然后解析标题结构
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith('#'):
            level = len(re.match(r'^#+', line).group())
            title = line[level:].strip()
            title = strip_markdown_formatting(title)

            if is_reminder_header(title):
                reminder, end_i = extract_reminders_from_section(lines, i)
                card.reminders.append(reminder)
                i = end_i
                continue
            elif level <= 3:
                # 收集该标题下的内容
                content_lines = []
                j = i + 1
                while j < len(lines):
                    sub = lines[j].strip()
                    if sub.startswith('#'):
                        break
                    if sub and sub != '---':
                        content_lines.append(html_inline(sub))
                    j += 1

                if content_lines:
                    card.sections.append(TimelineSection(
                        title=title,
                        items=[TimelineItem(time="", content='<br>'.join(content_lines))]
                    ))
                i = j
                continue

        i += 1


# ═══════════════════════════════════════════
# 9. 成都解析器（- **HH:MM~HH:MM** 格式）
# ═══════════════════════════════════════════

def parse_chengdu(text: str, filename: str) -> DayCard:
    """解析成都风格的笔记（含 - **时间** 列表项）"""
    lines = text.strip().split('\n')
    card = DayCard(day_label="", title="", sections=[], reminders=[])

    date_match = re.search(r'(\d+\.\d+)', filename)
    date_str = date_match.group(1) if date_match else ""
    card.day_label = date_str

    # 提取第一个 ## 标题作为卡片标题
    for line in lines:
        if line.strip().startswith('## '):
            title = line.strip()[3:].strip()
            card.title = strip_markdown_formatting(title)
            break

    if not card.title:
        card.title = filename.replace('.md', '')

    # 分段解析
    current_section_title = ""
    current_items = []
    pending_reminder = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 标题行
        if line.startswith('#'):
            # 保存之前的段落
            if current_items:
                card.sections.append(TimelineSection(
                    title=current_section_title,
                    items=current_items
                ))
                current_items = []

            level = len(re.match(r'^#+', line).group())
            title = line[level:].strip()
            title = strip_markdown_formatting(title)

            if is_reminder_header(title) and level >= 2:
                # 提醒框
                reminder, end_i = extract_reminders_from_section(lines, i)
                card.reminders.append(reminder)
                i = end_i
                continue
            else:
                current_section_title = title

        # 列表项 - **HH:MM~HH:MM** 格式
        elif re.match(r'^[-*]\s+\*\*', line):
            item = _parse_chengdu_list_item(line)
            if item:
                current_items.append(item)

        # 普通列表项
        elif re.match(r'^[-*]\s+', line) or re.match(r'^\d+\.\s', line):
            content = re.sub(r'^(\d+\.\s|[-*]\s)', '', line)
            content = html_inline(content)
            # 尝试从内容中提取时间
            tm = re.search(r'\*?\*?(\d{1,2}:\d{2})\*?\*?', content)
            time_str = tm.group(1) if tm else ""
            current_items.append(TimelineItem(time=time_str, content=content))

        # 普通文本（非空非标题）
        elif line and line != '---':
            content = html_inline(line)
            # 尝试匹配时间
            tm = re.search(r'(\d{1,2}:\d{2})', content)
            time_str = tm.group(1) if tm else ""
            current_items.append(TimelineItem(time=time_str, content=content))

        i += 1

    # 保存最后一段
    if current_items:
        card.sections.append(TimelineSection(
            title=current_section_title,
            items=current_items
        ))

    return card


def _parse_chengdu_list_item(line: str) -> Optional[TimelineItem]:
    """解析成都格式的列表项: - **HH:MM~HH:MM** 描述 或 - **标签**：描述"""
    # 去掉开头的 - 或 *
    content = re.sub(r'^[-*]\s+', '', line)

    # 提取粗体文本
    m = re.match(r'\*\*(.+?)\*\*\s*(.*)', content)
    if not m:
        return None

    bold_text = m.group(1).strip()
    desc = m.group(2).strip()

    # 判断粗体文本是否像时间（HH:MM 或 HH:MM~HH:MM）
    is_time = bool(re.match(
        r'^(\d{1,2}:\d{2})(\s*[~–-]\s*(\d{1,2}:\d{2}))?$',
        bold_text
    ))

    if is_time:
        # 纯时间 — 用作时间标签
        full_content = html_inline(desc) if desc else ""
        return TimelineItem(time=bold_text, content=full_content)

    # 时间可能包含附加信息，如 "15:00~15:30 动车到成都东站，..."
    # 如果时间很长（超过20字符），可能描述混在里面了
    if len(bold_text) > 30:
        # 长文本，可能时间+描述混在一起
        tm = re.match(r'(\d{1,2}:\d{2}\s*[~–-]\s*\d{1,2}:\d{2})', bold_text)
        if tm:
            pure_time = tm.group(1)
            rest = bold_text[tm.end():].strip() + ' ' + desc
            return TimelineItem(time=pure_time, content=html_inline(rest))
        else:
            return TimelineItem(time="", content=html_inline(bold_text + ' ' + desc))
    else:
        # 不是时间（如 "成都出发"、"抵达打卡"）— 作为加粗标签内嵌
        full_content = f'<strong>{html_inline(bold_text)}</strong>'
        if desc:
            full_content += f' {html_inline(desc)}'
        return TimelineItem(time="", content=full_content)


# ═══════════════════════════════════════════
# 10. 城市总览解析器
# ═══════════════════════════════════════════

def parse_city_overview(text: str) -> list:
    """从 *部分.md 中提取全局提醒"""
    reminders = []
    lines = text.strip().split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('##') and is_reminder_header(line):
            reminder, end_i = extract_reminders_from_section(lines, i)
            reminders.append(reminder)
            i = end_i
            continue
        i += 1

    return reminders


# ═══════════════════════════════════════════
# 11. HTML 渲染
# ═══════════════════════════════════════════

def get_css() -> str:
    """返回完整的 CSS 样式表"""
    return '''  :root {
    --xian: #c44536;
    --xian-light: #fdf0ed;
    --xian-bg: #fef9f7;
    --lanzhou: #d4950b;
    --lanzhou-light: #fef9ed;
    --lanzhou-bg: #fffdf7;
    --chengdu: #2e8b57;
    --chengdu-light: #edf7f1;
    --chengdu-bg: #f7fcf9;
    --text: #2c3e50;
    --text-muted: #6b7280;
    --bg: #f8f9fb;
    --card-bg: #fff;
    --border: #e5e7eb;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.7;
  }

  /* ── Hero ── */
  .hero {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 40%, #0f3460 100%);
    color: #fff;
    text-align: center;
    padding: 80px 24px 64px;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(ellipse at 30% 30%, rgba(196,69,54,0.15) 0%, transparent 50%),
                radial-gradient(ellipse at 65% 40%, rgba(212,149,11,0.12) 0%, transparent 45%),
                radial-gradient(ellipse at 50% 60%, rgba(46,139,87,0.10) 0%, transparent 50%);
    animation: heroFloat 20s ease-in-out infinite;
  }
  @keyframes heroFloat {
    0%, 100% { transform: translate(0, 0) scale(1); }
    33% { transform: translate(1%, -1%) scale(1.02); }
    66% { transform: translate(-1%, 1%) scale(1.01); }
  }
  .hero h1 {
    font-size: clamp(1.8rem, 5vw, 3rem);
    font-weight: 800;
    letter-spacing: 0.04em;
    position: relative;
    z-index: 1;
  }
  .hero .subtitle {
    margin-top: 12px;
    font-size: clamp(1rem, 2.5vw, 1.25rem);
    color: rgba(255,255,255,0.7);
    position: relative;
    z-index: 1;
  }
  .hero .route {
    margin-top: 24px;
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    position: relative;
    z-index: 1;
  }
  .hero .route .city-tag {
    padding: 8px 24px;
    border-radius: 50px;
    font-weight: 700;
    font-size: 0.95rem;
    letter-spacing: 0.05em;
  }
  .route .city-tag:nth-child(1) { background: var(--xian); }
  .route .city-tag:nth-child(3) { background: var(--lanzhou); }
  .route .city-tag:nth-child(5) { background: var(--chengdu); }
  .route .arrow { font-size: 1.3rem; opacity: 0.5; }

  /* ── Overview Bar ── */
  .overview {
    max-width: 1000px;
    margin: -28px auto 0;
    padding: 0 20px;
    position: relative;
    z-index: 2;
  }
  .overview-inner {
    background: var(--card-bg);
    border-radius: 16px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.07);
    padding: 24px 32px;
    display: flex;
    justify-content: space-around;
    flex-wrap: wrap;
    gap: 16px;
    text-align: center;
  }
  .overview-inner .stat b {
    display: block;
    font-size: 1.5rem;
    font-weight: 800;
  }
  .overview-inner .stat span {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  /* ── Section ── */
  .container { max-width: 1000px; margin: 0 auto; padding: 0 20px; }

  .city-section { margin: 48px 0; }

  .city-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 24px;
  }
  .city-header .icon {
    width: 48px; height: 48px;
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem;
    color: #fff;
    font-weight: 800;
    flex-shrink: 0;
  }
  .city-xian .icon { background: var(--xian); }
  .city-lanzhou .icon { background: var(--lanzhou); }
  .city-chengdu .icon { background: var(--chengdu); }

  .city-header h2 {
    font-size: 1.5rem;
    font-weight: 700;
  }
  .city-header .dates {
    font-size: 0.9rem;
    color: var(--text-muted);
  }
  .city-xian h2 { color: var(--xian); }
  .city-lanzhou h2 { color: var(--lanzhou); }
  .city-chengdu h2 { color: var(--chengdu); }

  /* ── Day Cards ── */
  .day-card {
    background: var(--card-bg);
    border-radius: 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    margin-bottom: 18px;
    overflow: hidden;
    border-left: 4px solid transparent;
    transition: box-shadow 0.2s, transform 0.2s;
  }
  .day-card:hover {
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    transform: translateY(-1px);
  }
  .city-xian .day-card { border-left-color: var(--xian); }
  .city-lanzhou .day-card { border-left-color: var(--lanzhou); }
  .city-chengdu .day-card { border-left-color: var(--chengdu); }

  .day-card-header {
    padding: 18px 22px;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    user-select: none;
  }
  .day-card-header:hover { background: rgba(0,0,0,0.01); }
  .day-card-header h3 {
    font-size: 1.05rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .day-label {
    font-size: 0.8rem;
    padding: 3px 10px;
    border-radius: 20px;
    font-weight: 600;
  }
  .city-xian .day-label { background: var(--xian-light); color: var(--xian); }
  .city-lanzhou .day-label { background: var(--lanzhou-light); color: var(--lanzhou); }
  .city-chengdu .day-label { background: var(--chengdu-light); color: var(--chengdu); }

  .day-card-header .toggle {
    font-size: 0.8rem;
    color: var(--text-muted);
    transition: transform 0.3s;
  }
  .day-card.open .day-card-header .toggle { transform: rotate(180deg); }

  .day-card-body {
    display: none;
  }
  .day-card.open .day-card-body {
    display: block;
  }
  .day-card-body-inner {
    padding: 0 22px 20px;
    border-top: 1px solid var(--border);
    padding-top: 16px;
    margin: 0 22px;
  }

  /* ── Timeline Items ── */
  .timeline { list-style: none; }
  .timeline li {
    display: flex;
    gap: 14px;
    padding: 10px 0;
    border-bottom: 1px dashed #f0f0f0;
    font-size: 0.93rem;
    align-items: flex-start;
  }
  .timeline li:last-child { border-bottom: none; }
  .timeline .time {
    min-width: 80px;
    font-weight: 600;
    font-size: 0.82rem;
    color: var(--text-muted);
    padding-top: 1px;
    flex-shrink: 0;
  }
  .city-xian .timeline .time { color: var(--xian); }
  .city-lanzhou .timeline .time { color: var(--lanzhou); }
  .city-chengdu .timeline .time { color: var(--chengdu); }

  /* ── Reminder Box ── */
  .reminder {
    border-radius: 10px;
    padding: 16px 20px;
    margin: 20px 0 8px;
    font-size: 0.9rem;
  }
  .reminder strong { display: block; margin-bottom: 6px; }
  .city-xian .reminder { background: var(--xian-light); border: 1px solid #f5c6bc; }
  .city-lanzhou .reminder { background: var(--lanzhou-light); border: 1px solid #fbe5a0; }
  .city-chengdu .reminder { background: var(--chengdu-light); border: 1px solid #b7dcc8; }
  .reminder ul { margin: 6px 0 0 18px; }
  .reminder li { margin: 2px 0; }

  /* ── Section subtitle ── */
  .section-subtitle {
    font-weight: 700;
    margin: 14px 0 8px;
    font-size: 0.95rem;
  }
  .city-xian .section-subtitle { color: var(--xian); }
  .city-lanzhou .section-subtitle { color: var(--lanzhou); }
  .city-chengdu .section-subtitle { color: var(--chengdu); }

  /* ── Highlight Tag ── */
  .highlight {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-left: 6px;
  }
  .hl-red { background: #fdecea; color: #c0392b; }
  .hl-yellow { background: #fef5e7; color: #b8860b; }
  .hl-green { background: #eafaf1; color: #1e8449; }
  .hl-blue { background: #eaf2f8; color: #2471a3; }

  /* ── Section Divider ── */
  .divider {
    display: flex; align-items: center; gap: 16px;
    margin: 52px 0 36px; color: var(--text-muted);
    font-size: 0.85rem; font-weight: 600; letter-spacing: 0.08em;
  }
  .divider::before, .divider::after {
    content: ''; flex: 1; height: 1px;
    background: var(--border);
  }

  /* ── Transit card ── */
  .transit-card {
    border-left-color: #888 !important;
  }

  /* ── Footer ── */
  footer {
    text-align: center;
    padding: 48px 20px 36px;
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  /* ── Responsive ── */
  @media (max-width: 640px) {
    .hero { padding: 56px 16px 44px; }
    .hero h1 { font-size: 1.5rem; }
    .overview-inner { padding: 16px 20px; }
    .overview-inner .stat b { font-size: 1.2rem; }
    .day-card-header { padding: 14px 16px; }
    .day-card-header h3 { font-size: 0.95rem; }
    .day-card-body-inner { padding: 0 12px 14px; margin: 0 16px; padding-top: 12px; overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .timeline .time { min-width: 68px; font-size: 0.75rem; }
    .route { gap: 8px; }
    .route .city-tag { padding: 6px 16px; font-size: 0.85rem; }
  }

  @media print {
    body { background: #fff; }
    .hero { background: #1a1a2e !important; -webkit-print-color-adjust: exact; }
    .day-card { break-inside: avoid; box-shadow: none; border: 1px solid #ddd; }
    .day-card-body { display: block !important; }
    .day-card-header .toggle { display: none; }
    .day-card-header { cursor: default; }
  }'''


def render_html(trip: TripData) -> str:
    """将 TripData 渲染为完整 HTML"""
    css = get_css()
    parts = []

    # ── HTML 头部 ──
    parts.append('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>西安 → 兰州 → 成都 · 十日旅行指南</title>
<style>
''')
    parts.append(css)
    parts.append('''</style>
</head>
<body>
''')

    # ── Hero ──
    parts.append('''<!-- ═══════════ HERO ═══════════ -->
<header class="hero">
  <h1>西安 → 兰州 → 成都</h1>
  <p class="subtitle">十日三城 · 穿越千年丝路与巴蜀</p>
  <div class="route">
    <span class="city-tag">🏯 西安</span>
    <span class="arrow">→</span>
    <span class="city-tag">🌊 兰州</span>
    <span class="arrow">→</span>
    <span class="city-tag">🐼 成都</span>
  </div>
</header>
''')

    # ── Overview Bar ──
    total_days = sum(len(c.days) for c in trip.cities.values())
    parts.append('''<!-- ═══════════ OVERVIEW ═══════════ -->
<div class="overview">
  <div class="overview-inner">
    <div class="stat"><b>7.14 – 7.24</b><span>旅行日期</span></div>
    <div class="stat"><b>3 座城市</b><span>西安 · 兰州 · 成都</span></div>
    <div class="stat"><b>10 天行程</b><span>3 + 3 + 4 天</span></div>
    <div class="stat"><b>4 人出行</b><span>好友同游</span></div>
  </div>
</div>

<div class="container">
''')

    # ── 出发日 ──
    parts.append('<!-- ═══════════ 出发日 ═══════════ -->')
    parts.append('<div class="divider">🚂 出发日 · 7月14日</div>')
    parts.append(render_departure_card(trip))

    # ── 各城市 ──
    for city_name in ["西安", "兰州", "成都"]:
        if city_name in trip.cities:
            parts.append(render_city_section(trip.cities[city_name], trip))

    # ── 结束 ──
    parts.append('''</div><!-- .container -->

<!-- ═══════════ FOOTER ═══════════ -->
<footer>
  <p>🗺️ 西安 → 兰州 → 成都 · 2025年7月14日—24日 · 十日三城</p>
  <p style="margin-top:6px; opacity:0.6;">Generated from Obsidian Travel Guide · 祝旅途愉快 ✈️</p>
</footer>

<script>
// Open the first card of each city by default
document.querySelectorAll('.city-section .day-card:first-child').forEach(c => c.classList.add('open'));
</script>

</body>
</html>''')

    return '\n'.join(parts)


def render_departure_card(trip: TripData) -> str:
    """渲染出发日卡片"""
    parts = []
    parts.append('<div class="day-card open">')
    parts.append('  <div class="day-card-header" onclick="this.parentElement.classList.toggle(\'open\')">')
    parts.append(f'    <h3>📦 {trip.departure_title}</h3>')
    parts.append('    <span class="toggle">▼</span>')
    parts.append('  </div>')
    parts.append('  <div class="day-card-body">')
    parts.append('    <div class="day-card-body-inner">')
    parts.append('      <ul class="timeline">')

    for item in trip.departure_items:
        time_display = item.time if item.time else ""
        content = item.content if item.content else ""
        # 跳过纯 wikilink 行
        if not content.strip() and not time_display:
            continue
        parts.append(f'        <li><span class="time">{time_display}</span>{content}</li>')

    parts.append('      </ul>')
    parts.append('    </div>')
    parts.append('  </div>')
    parts.append('</div>')
    return '\n'.join(parts)


def render_city_section(city: CityData, trip: TripData) -> str:
    """渲染一个城市的完整区块"""
    cfg = city.config
    css_class = cfg["css_class"]
    parts = []

    parts.append(f'<!-- ═══════════ {cfg["name_cn"]} ═══════════ -->')
    parts.append(f'<div class="city-section {css_class}">')
    parts.append('  <div class="city-header">')
    parts.append(f'    <div class="icon">{cfg["icon"]}</div>')
    parts.append('    <div>')
    parts.append(f'      <h2>{cfg["name_cn"]} · {cfg["subtitle"].split("·")[0].strip()}</h2>')
    parts.append(f'      <div class="dates">{cfg["dates"]} | {cfg["subtitle"].split("·", 1)[1].strip() if "·" in cfg["subtitle"] else cfg["subtitle"]}</div>')
    parts.append('    </div>')
    parts.append('  </div>')

    # 全局提醒（来自 *部分.md）
    for reminder in city.global_reminders:
        parts.append(render_reminder(reminder))

    # 各日卡片
    for i, day in enumerate(city.days):
        open_class = ' open' if (i == 0 or day.default_open) else ''
        parts.append(f'  <div class="day-card{open_class}">')
        parts.append('    <div class="day-card-header" onclick="this.parentElement.classList.toggle(\'open\')">')
        parts.append('      <h3>')
        parts.append(f'        <span class="day-label">Day {i+1} · {day.day_label}</span>')
        parts.append(f'        {day.title}')
        parts.append('      </h3>')
        parts.append('      <span class="toggle">▼</span>')
        parts.append('    </div>')
        parts.append('    <div class="day-card-body">')
        parts.append('      <div class="day-card-body-inner">')

        # 该日的提醒
        for reminder in day.reminders:
            parts.append(render_reminder(reminder))

        # 各时间段
        for section in day.sections:
            if section.title and section.title not in ("行程时间表", ""):
                color_var = f"var(--{cfg['css_class'].split('-')[1]})" if '-' in cfg['css_class'] else cfg['color']
                parts.append(f'        <p class="section-subtitle">{section.title}</p>')
            if section.items:
                parts.append('        <ul class="timeline">')
                for item in section.items:
                    time_display = item.time if item.time else ""
                    content = item.content if item.content else ""
                    parts.append(f'          <li><span class="time">{time_display}</span>{content}</li>')
                parts.append('        </ul>')

        # 兜底 HTML
        if day.extra_html:
            parts.append(day.extra_html)

        parts.append('      </div>')
        parts.append('    </div>')
        parts.append('  </div>')

    parts.append('</div>')
    return '\n'.join(parts)


def render_reminder(reminder: Reminder) -> str:
    """渲染单个提醒框"""
    parts = []
    parts.append('        <div class="reminder">')
    parts.append(f'          <strong>{reminder.title}</strong>')
    if reminder.items:
        parts.append('          <ul>')
        for item in reminder.items:
            parts.append(f'            <li>{item}</li>')
        parts.append('          </ul>')
    parts.append('        </div>')
    return '\n'.join(parts)


# ═══════════════════════════════════════════
# 12. 格式检测
# ═══════════════════════════════════════════

def detect_format(text: str, filename: str) -> str:
    """检测笔记格式类型"""
    # 出发日
    if "Departure" in filename or "departure" in filename.lower():
        return "departure"

    # 兰州风：含 Markdown 表格
    if re.search(r'^\|.+\|$', text, re.MULTILINE):
        return "lanzhou"

    # 西安风：含 ### HH:MM 标题
    if re.search(r'^###\s+\d{1,2}:\d{2}', text, re.MULTILINE):
        return "xian"

    # 成都风：含 - **HH:MM~HH:MM** 模式
    if re.search(r'[-*]\s+\*\*\d{1,2}:\d{2}', text):
        return "chengdu"

    # 默认：成都风（最通用）
    return "chengdu"


# ═══════════════════════════════════════════
# 13. 主流程
# ═══════════════════════════════════════════

def main():
    """主入口"""
    print("🔍 正在扫描笔记文件...")
    files = discover_files()

    trip = TripData()

    # ── 解析出发日 ──
    if files["departure"]:
        print(f"  📅 解析出发日: {files['departure'].name}")
        text = preprocess(files["departure"].read_text(encoding="utf-8"))
        trip = parse_departure(text)

    # ── 解析各城市 ──
    for city_name in ["西安", "兰州", "成都"]:
        if city_name not in files or not files[city_name]:
            continue

        city_info = files[city_name]
        cfg = CITY_CONFIG[city_name]
        city_data = CityData(config=cfg)

        # 先解析总览（全局提醒）
        if city_info.get("overview"):
            print(f"  📋 解析 {city_name} 总览: {city_info['overview'].name}")
            overview_text = preprocess(city_info["overview"].read_text(encoding="utf-8"))
            city_data.global_reminders = parse_city_overview(overview_text)

        # 解析每日笔记
        for day_file in city_info.get("days", []):
            print(f"  📝 解析: {city_name}/{day_file.name}")
            raw_text = day_file.read_text(encoding="utf-8")
            text = preprocess(raw_text)
            fmt = detect_format(text, day_file.name)

            if fmt == "xian":
                card = parse_xian(text, day_file.name)
            elif fmt == "lanzhou":
                card = parse_lanzhou(text, day_file.name)
            elif fmt == "chengdu":
                card = parse_chengdu(text, day_file.name)
            else:
                card = parse_chengdu(text, day_file.name)  # fallback

            city_data.days.append(card)

        trip.cities[city_name] = city_data

    # ── 生成 HTML ──
    print("\n🎨 正在生成 HTML...")
    html = render_html(trip)

    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"✅ 已生成: {OUTPUT_FILE}")
    print(f"   文件大小: {OUTPUT_FILE.stat().st_size:,} 字节")
    print(f"   用浏览器打开 {OUTPUT_FILE.name} 即可查看")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
