# Custom MobyMax Reading Plans — Workflow

This project produces individualized MobyMax Reading Skills remediation plans, one per student. Inputs are standardized reading assessments (STAAR or "Alpha Standardized Reading"); outputs are a styled HTML report, an assignable XLSX lesson list, and a card on the root `index.html`. Use this file as the single source of truth when onboarding a new student — every convention here is load-bearing and was learned from prior runs.

## Inputs

**Source folder** — `<First Last>/` at the project root, full name with the original capitalization and a space (e.g. `Marcus Fuentes/`). Source folders are NOT committed; if a new student's folder isn't covered by `.gitignore`, add it before staging anything.

**Assessments** — accept either format, and a single student folder may mix both:

- **PDF**: filename pattern `[<First Last> ]Alpha {Standardized Reading|ELA STAAR} G<grade>.<id>.pdf`. Use the Read tool with the `pages:` parameter (mandatory for PDFs >10 pages). Extract per-question: question text, student's answer, correct answer, and any item-type/skill label shown.
- **CSV**: one row per question. Required columns (case-insensitive): `q`, `question`, `student_answer`, `correct_answer`. Optional: `skill`, `passage`, `paragraph_ref`. Multiple assessments may be one CSV per file or a single CSV with a `test` column.

**Curriculum source** — prefer in this order:
1. `Mobymax Catalog/mobymax_read_g<grade>.json` (G3–G8). Canonical machine-readable list with `lid`, lesson, topic, course, XP.
2. `New XP MobyMax Reading Skills.xlsx` at the project root. Single shared copy — fallback for older students or grades not in the catalog JSONs.

## Workflow

1. **Detect inputs.** List `<First Last>/`, classify each file as PDF assessment, CSV assessment, or curriculum xlsx. Confirm the student's grade from the filenames.
2. **Extract wrong answers.** For each assessment, build `{test, q#, question, student_answer, correct_answer, skill_tag}`. Compute per-test score = correct / total. Tag each wrong answer with one of the canonical skill-gap categories below.
3. **Aggregate skill gaps.** Count errors per category across all assessments; rank descending. The bar widths in the report are proportional to error count (top gap = 100%).
4. **Assemble lessons.** Pull lessons from the curriculum source for the student's grade (and one grade above when prior students did so for the same grade band — check the nearest prior student in the same grade range). Group into 4–6 Parts; each Part targets the top-ranked gaps in order. Each lesson has `{phase, phaseName, gr, course, topic, lesson, xp, gap, lid?}`. Phase IDs are `w1`, `w2`, … (kept for backward-compat with the existing JS filter; the *display* text is "Part N").
5. **Emit deliverables and update the index.** See next two sections.

## Outputs (published to `<firstname>/`)

Output folder = lowercase first name only (`marcus/`, `eddie/`). Hyphenate with the last name only to disambiguate (`edgar-shinar/`). Leave the `<First Last>/` source folder in place.

Required files:
- `reading-plan-report.html` — single-file styled report, no external assets. Mirror the structure of `marcus/reading-plan-report.html` (best current template for G3–G5) or `eddie/reading-plan-report.html` (for older grades). Sections, in order:
  - Header — student, grade, report date, platform
  - `.score-cards` — color-coded `pass` / `warn` / `fail` per test
  - `Skill Gap Analysis` — ranked list with bars
  - `Wrong Answers — Detailed Breakdown` — one `<h3>` + table per test
  - Multi-part remediation plan summary — `.phase-grid` with `p1`–`p4` cards
  - Full filterable lesson table + totals bar
- `custom-mobymax-reading-plan.xlsx` — flat assignable list. Columns: Part / Grade / Course / Topic / Lesson / XP. (Acceptable alt name: `<Name> - Reading Plan.xlsx`, as used for Edgar.)

Optional:
- `lessons.json` — only when the lesson list is large enough to benefit from a separate intermediate file (Eddie has one; the others don't).

## Update the root `index.html`

Add a new `<a class="plan-card">` entry following the existing pattern. Stats: total Lessons, total XP, number of Parts. Use the Marcus or Emma card as the template — do not modify other students' cards.

## Conventions (load-bearing)

- **"Part N", not "Week N"** — phase labels in HTML, XLSX, JSON, and prose all read "Part". (`index.html` still says "Weeks" on the older Jaya/Eddie cards; leave those alone unless touching the index for other reasons. New cards say "Parts".)
- **Output folder = lowercase first name only**, hyphenated with last name only to disambiguate.
- **Source folder = `<First Last>/`** with the original capitalization.
- **Never commit** the `<First Last>/` source folders or any credentials. Source folders are not yet listed in `.gitignore` — add the new student's folder before staging.

## Skill-gap taxonomy (canonical — used in committed reports)

- Inference & Drawing Conclusions
- Author's Purpose & Craft / Rhetoric
- Vocabulary & Context Clues
- Theme, Main Idea & Central Message
- Summary
- Cross-Text Comparison & Synthesis
- Text Features & Graphics
- Text Structure
- Text Evidence & Supporting Details
- Plot, Drama & Poetry Structure (or "Poetry Elements & Craft" for younger grades)
- Tone & Connotation (older grades only)

## Tag CSS classes (reuse, do not invent)

`tag-inference` · `tag-purpose` · `tag-vocab` · `tag-summary` · `tag-comparison` · `tag-features` · `tag-evidence` · `tag-plot` · `tag-poetry`

## Verification checklist (before declaring done)

- [ ] `<firstname>/reading-plan-report.html` opens in a browser, renders with no missing styles, prints cleanly (CSS includes a `@media print` block).
- [ ] Each score card's right + wrong = test's question count, and the % matches.
- [ ] Skill-gap error counts sum to the total wrong answers across all tests.
- [ ] Every lesson row has non-zero XP and a `phase` of `w1`–`w<N>` matching one of the phase cards.
- [ ] Totals bar (lessons / XP / parts) matches the new `index.html` card.
- [ ] `index.html` renders with the new card; existing cards still link correctly.
- [ ] No new files staged under `<First Last>/`; no credentials staged.

## Reference files

- `marcus/reading-plan-report.html` — current best template (G3–G5).
- `eddie/reading-plan-report.html`, `eddie/lessons.json` — template for older grades and the optional intermediate JSON.
- `index.html` — landing-page card pattern.
- `Mobymax Catalog/mobymax_read_g<3-8>.json` — curriculum source of truth.
- `.gitignore` — extend before committing if a new source folder isn't covered.

## Refreshing student progress (red% / blue school days)

Each report and the index card surface live progress (% complete in red, school-days worked in blue) baked into the HTML by `refresh-progress.py` — no `localStorage`, no manual import, no in-page API calls. Rerun any time the admin updates mastery.

1. Run `refresh-progress.sql` against the reporting DB (the `rpt2_activity_log` view).
2. Save the result's `data` array to `/tmp/activity_records.json`.
3. `python3 refresh-progress.py` — idempotent; rewrites each `<slug>/reading-plan-report.html` and `index.html` with a `MASTERY_SNAPSHOT` constant + `SCHOOL_DAYS_COUNT`.

Rules baked into the script:
- **Course-name match** is the new `[Mobymax] Reading G<N> hole-filling` only. Eddie has older `MobyMax - Reading Skills … Hole-Filling` activity from prior manual plans — those are intentionally excluded.
- **Lesson match** is `(grade, normalised_name)`. Strip `[Mobymax] - ` prefix, ` - Attempt N` suffix, and trailing `(grade<N>)` from `activity_name`; lowercase + collapse whitespace.
- **Mastered** = best score per `(grade, name)` ≥ 80%, dated on/after that student's plan creation date (`PLAN_DATES` at the top of `refresh-progress.py`).
- **School days** = `COUNT(DISTINCT calendar_date)` where `is_school_day=true` in any matching course since the plan's creation date.

When onboarding a new student, add them to `PLAN_DATES` in `refresh-progress.py` and to the CASE/WHERE clauses in `refresh-progress.sql`. Their `student_id` comes from a `rpt2_student.name` lookup.
