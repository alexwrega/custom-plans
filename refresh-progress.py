#!/usr/bin/env python3
"""Refresh per-student MobyMax mastery snapshot for the custom reading plans.

Idempotently transforms each `<slug>/reading-plan-report.html` from its
HEAD-state baseline (with the legacy Import-Scores + localStorage progress
tracking) to its new state (read-only MASTERY_SNAPSHOT + red%/blue-days
display) using the activity records cached at /tmp/activity_records.json.

Usage:
  1. Ensure HTML files are at HEAD baseline (or already at the new state —
     this script is idempotent).
  2. Run the rpt2_activity_log SQL (see end of file) and save its `data`
     array to /tmp/activity_records.json.
  3. python3 refresh-progress.py
"""
from __future__ import annotations
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ACTIVITY_FILE = Path("/tmp/activity_records.json")

PLAN_DATES = {
    "ada":          "2026-05-04",
    "eddie":        "2026-03-27",
    "edgar-shinar": "2026-04-13",
    "elena":        "2026-05-04",
    "emma":         "2026-04-29",
    "jacob":        "2026-05-04",
    "jaya":         "2026-03-26",
    "keaton":       "2026-04-29",
    "lily":         "2026-05-04",
    "marcus":       "2026-04-29",
    "teddy":        "2026-05-07",
}

NON_LESSON_PREFIXES = (
    "alpha standardized reading",
    "assignment complete:",
)


# ---------------------------------------------------------------------------
# Lesson-name normalisation
# ---------------------------------------------------------------------------

def normalize(name: str) -> tuple[str, int | None]:
    s = name.strip()
    s = re.sub(r"^\s*\[Mobymax\]\s*-\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*-\s*Attempt\s+\d+\s*$", "", s, flags=re.IGNORECASE)
    m = re.search(r"\s*\(grade\s*(\d+)\)\s*$", s, flags=re.IGNORECASE)
    grade = None
    if m:
        grade = int(m.group(1))
        s = s[: m.start()]
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower(), grade


def grade_from_course(course_name: str) -> int | None:
    m = re.search(r"\[Mobymax\]\s+Reading\s+G(\d+)\s+hole-filling", course_name, re.I)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Plan parsing
# ---------------------------------------------------------------------------

LESSONS_RE = re.compile(r"const lessons\s*=\s*\[(.*?)\];", re.DOTALL)
LESSON_OBJ_RE = re.compile(r"\{([^{}]*?)\}")


def parse_lessons(html: str) -> list[dict]:
    m = LESSONS_RE.search(html)
    if not m:
        raise RuntimeError("lessons array not found")
    body = m.group(1)
    out = []
    for obj in LESSON_OBJ_RE.finditer(body):
        text = obj.group(1)
        d = {}
        for kv in re.finditer(
            r'(\w+)\s*:\s*(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|([0-9]+))',
            text,
        ):
            key = kv.group(1)
            if kv.group(2) is not None:
                val: object = kv.group(2)
            elif kv.group(3) is not None:
                val = kv.group(3)
            else:
                val = int(kv.group(4))
            if isinstance(val, str):
                val = (
                    val.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")
                )
            d[key] = val
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Snapshot building
# ---------------------------------------------------------------------------

def build_snapshot(activity_records: list[dict]) -> dict[str, dict]:
    by_slug: dict[str, list[dict]] = defaultdict(list)
    for r in activity_records:
        by_slug[r["slug"]].append(r)

    out: dict[str, dict] = {}
    for slug, records in by_slug.items():
        best: dict[str, dict] = {}
        school_dates: set[str] = set()
        for r in records:
            name = r["activity_name"]
            n_lower = name.lower().lstrip()
            if any(n_lower.startswith(p) for p in NON_LESSON_PREFIXES):
                continue
            tot = r.get("total_questions")
            cor = r.get("correct_questions")
            date = r["d"][:10]
            if r.get("is_school_day"):
                school_dates.add(date)
            if not tot or cor is None:
                continue
            try:
                score = round(100 * float(cor) / float(tot))
            except (TypeError, ZeroDivisionError):
                continue
            norm_name, name_grade = normalize(name)
            grade = (
                name_grade
                if name_grade is not None
                else grade_from_course(r["course_name"])
            )
            if grade is None:
                continue
            key = f"{grade}|{norm_name}"
            cur = best.get(key)
            if cur is None or score > cur["score"]:
                best[key] = {"score": score, "date": date}
            elif score == cur["score"] and date < cur["date"]:
                best[key]["date"] = date
        mastery = {k: v for k, v in best.items() if v["score"] >= 80}
        out[slug] = {"mastery": mastery, "school_days": len(school_dates)}

    for slug in PLAN_DATES:
        out.setdefault(slug, {"mastery": {}, "school_days": 0})
    return out


def render_summary(snapshot: dict, plan_lessons: list[dict]) -> dict:
    lookup = snapshot["mastery"]
    matched = []
    for i, lesson in enumerate(plan_lessons):
        gr = lesson.get("gr")
        name = lesson.get("lesson")
        if gr is None or not name:
            continue
        norm = re.sub(r"\s+", " ", name).strip().lower()
        rec = lookup.get(f"{gr}|{norm}")
        if rec:
            matched.append({"i": i, "score": rec["score"], "date": rec["date"]})
    return {
        "matched": matched,
        "total": len(plan_lessons),
        "school_days": snapshot["school_days"],
    }


# ---------------------------------------------------------------------------
# HTML transformations
# ---------------------------------------------------------------------------

# Step 1: Remove Import Scores button + modal + 3 JS functions, and replace
# the `<button onclick="showImportModal()">…</button>` line with the new
# right-side red%/blue-days panel.

OLD_IMPORT_BUTTON = (
    '      <button onclick="showImportModal()" style="padding:5px 14px;'
    'border-radius:6px;border:1px solid var(--border);background:white;'
    'cursor:pointer;font-size:12px;font-weight:600;">&#8679; Import Scores'
    "</button>\n"
)

NEW_RIGHT_PANEL = """      <div style="display:flex;gap:28px;align-items:flex-end;">
        <div style="text-align:right;line-height:1;">
          <div id="progressPctValue" style="font-size:34px;font-weight:800;color:var(--red);">0%</div>
          <div style="font-size:11px;color:var(--gray);text-transform:uppercase;letter-spacing:0.5px;font-weight:600;margin-top:4px;">Complete</div>
        </div>
        <div style="text-align:right;line-height:1;">
          <div id="progressDaysValue" style="font-size:34px;font-weight:800;color:var(--blue);">0</div>
          <div style="font-size:11px;color:var(--gray);text-transform:uppercase;letter-spacing:0.5px;font-weight:600;margin-top:4px;">School Days</div>
        </div>
      </div>
"""

IMPORT_MODAL_RE = re.compile(
    r'\n*<div id="importModal" style="display:none;[^>]*>\s*'
    r".*?"
    r"</div>\s*</div>\s*</div>\s*",
    re.DOTALL,
)

IMPORT_FNS_RE = re.compile(
    r"\nfunction showImportModal\(\) \{.*?\n\}\s*"
    r"\nfunction closeImportModal\(\) \{.*?\n\}\s*"
    r"\nfunction processImport\(\) \{.*?\n\}\s*",
    re.DOTALL,
)


def remove_import_scores(html: str) -> str:
    if OLD_IMPORT_BUTTON in html:
        html = html.replace(OLD_IMPORT_BUTTON, NEW_RIGHT_PANEL, 1)
    html = IMPORT_MODAL_RE.sub("\n", html, count=1)
    html = IMPORT_FNS_RE.sub("\n", html, count=1)
    return html


# Step 2: Inject MASTERY_SNAPSHOT and replace the 3 mastery functions.

INJECTION_MARK_BEGIN = "/* === BEGIN MASTERY SNAPSHOT === */"
INJECTION_MARK_END = "/* === END MASTERY SNAPSHOT === */"

LET_MASTERY_RE = re.compile(
    r"let masteryData = JSON\.parse\(localStorage\.getItem\(MASTERY_KEY\) \|\| '\{\}'\);"
)


def find_fn_span(text: str, fn_name: str) -> tuple[int, int] | None:
    """Locate `function NAME(...) { ... }` and return its [start, end) span.

    Stack-based JS-aware parser: tracks strings ("`'`), template literals,
    line/block comments, and template `${...}` interpolations. Each nested
    code context (function body, ${} interpolation) has its own brace depth.
    """
    m = re.search(r"function " + re.escape(fn_name) + r"\b", text)
    if not m:
        return None
    i = text.find("{", m.end())
    if i < 0:
        return None
    # Stack entries are tuples: ('code', depth) | ('str_dq',) | ('str_sq',) | ('tmpl',)
    stack: list[tuple] = [("code", 1)]
    j = i + 1
    while j < len(text):
        c = text[j]
        top = stack[-1]
        kind = top[0]
        if kind == "code":
            depth = top[1]
            if c == "/" and j + 1 < len(text) and text[j + 1] == "/":
                nl = text.find("\n", j)
                j = nl if nl >= 0 else len(text)
                continue
            if c == "/" and j + 1 < len(text) and text[j + 1] == "*":
                end = text.find("*/", j + 2)
                j = end + 2 if end >= 0 else len(text)
                continue
            if c == '"':
                stack.append(("str_dq",))
            elif c == "'":
                stack.append(("str_sq",))
            elif c == "`":
                stack.append(("tmpl",))
            elif c == "{":
                stack[-1] = ("code", depth + 1)
            elif c == "}":
                if depth == 1:
                    # End of this code context
                    stack.pop()
                    if not stack:
                        return (m.start(), j + 1)
                    # We just popped a ${...} interpolation back to template
                else:
                    stack[-1] = ("code", depth - 1)
        elif kind == "str_dq":
            if c == "\\":
                j += 2
                continue
            if c == '"':
                stack.pop()
        elif kind == "str_sq":
            if c == "\\":
                j += 2
                continue
            if c == "'":
                stack.pop()
        elif kind == "tmpl":
            if c == "\\":
                j += 2
                continue
            if c == "`":
                stack.pop()
            elif c == "$" and j + 1 < len(text) and text[j + 1] == "{":
                stack.append(("code", 1))
                j += 2
                continue
        j += 1
    return None


def replace_or_insert_fn(html: str, fn_name: str, body: str) -> str:
    span = find_fn_span(html, fn_name)
    if span:
        return html[: span[0]] + body + html[span[1] :]
    marker = "applyMasteryColumn();"
    idx = html.rfind(marker)
    if idx < 0:
        raise RuntimeError(f"{fn_name}: not found and no marker to insert before")
    return html[:idx] + body + "\n\n" + html[idx:]


def patch_report(html: str, slug: str, summary: dict) -> str:
    # 1. Strip Import Scores feature
    html = remove_import_scores(html)

    # 2. Inject MASTERY_SNAPSHOT (replaces `let masteryData = JSON.parse...`)
    payload_js = json.dumps(summary, indent=2, sort_keys=True)
    new_init = (
        f"{INJECTION_MARK_BEGIN}\n"
        f"const MASTERY_SNAPSHOT = {payload_js};\n"
        f"const SCHOOL_DAYS_COUNT = MASTERY_SNAPSHOT.school_days || 0;\n"
        f"const masteryByIndex = {{}};\n"
        f"(MASTERY_SNAPSHOT.matched || []).forEach(m => {{ masteryByIndex[m.i] = m; }});\n"
        f"let masteryData = {{}};  // legacy stub — read-only mode\n"
        f"{INJECTION_MARK_END}"
    )
    if INJECTION_MARK_BEGIN in html:
        html = re.sub(
            re.escape(INJECTION_MARK_BEGIN) + r".*?" + re.escape(INJECTION_MARK_END),
            new_init,
            html,
            count=1,
            flags=re.DOTALL,
        )
    else:
        html, n = LET_MASTERY_RE.subn(new_init, html, count=1)
        if n != 1:
            raise RuntimeError(f"{slug}: localStorage initialiser not found")

    # 3. Replace 3 mastery functions with read-only versions
    new_apply = (
        "function applyMasteryColumn() {\n"
        "  const tbody = document.getElementById('lessonBody');\n"
        "  if (!tbody) return;\n"
        "  let lessonIdx = -1;\n"
        "  Array.from(tbody.rows).forEach(tr => {\n"
        "    if (tr.classList.contains('phase-row')) return;\n"
        "    lessonIdx++;\n"
        "    const ex = tr.querySelector('.mastery-col');\n"
        "    if (ex) ex.remove();\n"
        "    const m = masteryByIndex[lessonIdx];\n"
        "    const td = document.createElement('td');\n"
        "    td.className = 'mastery-col';\n"
        "    td.innerHTML = m\n"
        "      ? `<span class=\"mastery-btn done\" title=\"${m.score}%\">&#10003;</span><span class=\"mastery-date\">${m.date}</span>`\n"
        "      : '<span class=\"mastery-btn\">&#9675;</span>';\n"
        "    tr.appendChild(td);\n"
        "    if (m) tr.classList.add('mastered');\n"
        "    else tr.classList.remove('mastered');\n"
        "  });\n"
        "  updateProgress();\n"
        "}"
    )
    new_update = (
        "function updateProgress() {\n"
        "  const total = MASTERY_SNAPSHOT.total || lessons.length;\n"
        "  const masteredCount = (MASTERY_SNAPSHOT.matched || []).length;\n"
        "  const pct = total ? Math.round(masteredCount / total * 100) : 0;\n"
        "  const label = document.getElementById('progressLabel');\n"
        "  const bar = document.getElementById('progressBarInner');\n"
        "  const pctEl = document.getElementById('progressPctValue');\n"
        "  const daysEl = document.getElementById('progressDaysValue');\n"
        "  if (label) label.textContent = masteredCount + ' of ' + total + ' lessons mastered';\n"
        "  if (bar) bar.style.width = pct + '%';\n"
        "  if (pctEl) pctEl.textContent = pct + '%';\n"
        "  if (daysEl) daysEl.textContent = SCHOOL_DAYS_COUNT;\n"
        "}"
    )
    new_toggle = (
        "function toggleMastery() { /* read-only: data comes from MASTERY_SNAPSHOT */ }"
    )

    html = replace_or_insert_fn(html, "applyMasteryColumn", new_apply)
    html = replace_or_insert_fn(html, "updateProgress", new_update)
    html = replace_or_insert_fn(html, "toggleMastery", new_toggle)
    return html


# ---------------------------------------------------------------------------
# index.html
# ---------------------------------------------------------------------------

INDEX_BLOCK_BEGIN = "/* === BEGIN INDEX PROGRESS === */"
INDEX_BLOCK_END = "/* === END INDEX PROGRESS === */"

INDEX_CSS_VAR_INSERT = "    --red: #CC0000;\n"
INDEX_CSS_RULES = """
  .plan-stats .stat-item.pct .number { color: var(--red); }
  .plan-stats .stat-item.days .number { color: var(--blue); }
"""
INDEX_NEW_STAT_ITEMS = """        <div class="stat-item pct">
          <div class="number" data-pct>0%</div>
          <div class="label">Complete</div>
        </div>
        <div class="stat-item days">
          <div class="number" data-days>0</div>
          <div class="label">School Days</div>
        </div>
"""


def patch_index(html: str, plan_summaries: dict) -> str:
    # 1. Add --red CSS variable if missing
    if "--red" not in html:
        html = html.replace(
            "    --gray: #6c757d;\n",
            "    --gray: #6c757d;\n" + INDEX_CSS_VAR_INSERT,
            1,
        )
    # 2. Add CSS rules for pct/days colors if missing
    if ".stat-item.pct" not in html:
        anchor = (
            "  .plan-stats .stat-item .label {\n"
            "    font-size: 11px;\n"
            "    text-transform: uppercase;\n"
            "    color: var(--gray);\n"
            "    letter-spacing: 0.5px;\n"
            "  }\n"
        )
        html = html.replace(anchor, anchor + INDEX_CSS_RULES, 1)

    # 3. Per-card: add data-slug + extra stat items (idempotent)
    for slug in PLAN_DATES:
        href = f'href="{slug}/reading-plan-report.html"'
        # Add data-slug if not already on the <a> tag
        a_re = re.compile(
            r'(<a class="plan-card" ' + re.escape(href) + r'(?:\s[^>]*?)?)(>)',
            re.DOTALL,
        )

        def add_slug(mm: re.Match) -> str:
            head, close = mm.group(1), mm.group(2)
            if 'data-slug=' in head:
                return mm.group(0)
            return head + f' data-slug="{slug}"' + close

        html = a_re.sub(add_slug, html, count=1)

        # Add the two new stat items just before `</div>\n      <div class="arrow">`
        # within this card region. Idempotent: skip if `data-pct` already inside
        # the card.
        card_pat = re.compile(
            r'(<a class="plan-card" '
            + re.escape(href)
            + r'[^>]*>.*?<div class="plan-stats">.*?)'
            r'(\n      </div>\n      <div class="arrow">)',
            re.DOTALL,
        )

        def add_stats(mm: re.Match) -> str:
            chunk = mm.group(1)
            if "data-pct" in chunk:
                return mm.group(0)
            return chunk + "\n" + INDEX_NEW_STAT_ITEMS.rstrip("\n") + mm.group(2)

        html = card_pat.sub(add_stats, html, count=1)

    # 4. Insert/replace the inline progress script before </body>
    progress = {}
    for slug, summary in plan_summaries.items():
        total = summary.get("total", 0)
        mastered = len(summary.get("matched", []))
        progress[slug] = {
            "pct": round(mastered / total * 100) if total else 0,
            "days": summary.get("school_days", 0),
        }

    payload = json.dumps(progress, indent=2, sort_keys=True)
    new_block = (
        f"<script>\n"
        f"{INDEX_BLOCK_BEGIN}\n"
        f"const INDEX_PROGRESS = {payload};\n"
        f"{INDEX_BLOCK_END}\n"
        f"document.querySelectorAll('.plan-card[data-slug]').forEach(card => {{\n"
        f"  const slug = card.dataset.slug;\n"
        f"  const p = INDEX_PROGRESS[slug] || {{ pct: 0, days: 0 }};\n"
        f"  const pctEl = card.querySelector('[data-pct]');\n"
        f"  const daysEl = card.querySelector('[data-days]');\n"
        f"  if (pctEl) pctEl.textContent = p.pct + '%';\n"
        f"  if (daysEl) daysEl.textContent = p.days;\n"
        f"}});\n"
        f"</script>\n"
    )

    # Replace existing block (between markers), or insert before </body>
    if INDEX_BLOCK_BEGIN in html:
        html = re.sub(
            r"<script>\s*"
            + re.escape(INDEX_BLOCK_BEGIN)
            + r".*?"
            + re.escape(INDEX_BLOCK_END)
            + r".*?</script>\s*",
            new_block,
            html,
            count=1,
            flags=re.DOTALL,
        )
    else:
        html = html.replace("</body>", new_block + "</body>", 1)

    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not ACTIVITY_FILE.exists():
        raise SystemExit(
            f"Missing {ACTIVITY_FILE}. Run rpt2_activity_log SQL and save its "
            f"`data` array there first."
        )
    activity_records = json.loads(ACTIVITY_FILE.read_text())
    snapshot = build_snapshot(activity_records)
    plan_summaries: dict[str, dict] = {}

    for slug in PLAN_DATES:
        report = ROOT / slug / "reading-plan-report.html"
        if not report.exists():
            print(f"  ! {slug}: report missing, skipping")
            continue
        html = report.read_text()
        lessons = parse_lessons(html)
        summary = render_summary(snapshot[slug], lessons)
        plan_summaries[slug] = summary
        report.write_text(patch_report(html, slug, summary))
        print(
            f"  ✓ {slug:14s} {len(summary['matched']):3d}/{summary['total']:3d} "
            f"mastered, {summary['school_days']} school days"
        )

    index_path = ROOT / "index.html"
    if index_path.exists():
        index_path.write_text(patch_index(index_path.read_text(), plan_summaries))
        print("  ✓ index.html")


if __name__ == "__main__":
    main()
