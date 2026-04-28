# app/services/form_parser.py
# Converts clinical intake PDFs into validated FormSchema JSON files.
#
# Five-stage pipeline (all LLM calls are small and independent):
#   Stage 0 — extract_and_clean()     no LLM   strip noise, tag checkboxes/tables
#   Stage 1 — discover_sections()     1 call   gpt-4o-mini, section boundaries only
#   Stage 2 — extract_questions()     N calls  gpt-4o, per-section, run in parallel
#   Stage 3 — extract_scoring()       1 call   conditional, only scored forms
#   Stage 4 — generate_hints()        M calls  batches of 15 questions
#   Stage 5 — assemble_form()         no LLM   Pydantic validation + ParseReport
#
# The parser is a developer-time tool only. Pre-converted JSONs are committed
# to backend/app/forms/ so the runtime interview engine never calls this module.

import asyncio
import json
import re
import textwrap
from io import BytesIO
from typing import Optional

import pypdf
from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import (
    FormSchema,
    ParseReport,
    QuestionSchema,
    SectionBoundary,
    SectionSchema,
    ScoringRange,
    ScoringSchema,
)

# ── Checkbox / multi-column detection constants ───────────────────────────────

_CHECKBOX_RE = re.compile(r"[☐□✓✗✘☑☒]|\[ *\]|\[x\]|\[X\]", re.IGNORECASE)
_MULTI_CHOICE_THRESHOLD = 3          # lines with this many checkboxes are candidates
_HINT_BATCH_SIZE = 15
_SCORING_KEYWORDS = re.compile(
    r"\b(scoring|score interpretation|total score|score range|"
    r"interpretation|results|cut.?off)\b",
    re.IGNORECASE,
)

# ── Known clinical section headers used as fallback anchors ───────────────────

_KNOWN_HEADERS = [
    "reason for visit",
    "chief complaint",
    "history of present illness",
    "past medical history",
    "surgical history",
    "medications",
    "allergies",
    "social history",
    "family history",
    "review of systems",
    "scoring",
    "score interpretation",
    "functional impact",
]


def _make_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


# ── Stage 0: text extraction + preprocessing ──────────────────────────────────

def extract_and_clean(pdf_source: bytes | str) -> str:
    """
    Extract text from a PDF (bytes or URL path string) and clean it for LLM processing.

    Returns a single string with:
    - Page headers/footers stripped (lines appearing on >1 page)
    - Checkbox symbols normalized to [CHECK]
    - Multi-choice candidate lines tagged #MULTI_CHOICE_CANDIDATE
    - Table-like rows tagged #TABLE_ROW
    - Pages delimited by --- PAGE N ---
    """
    if isinstance(pdf_source, str):
        import urllib.request
        with urllib.request.urlopen(pdf_source) as resp:
            pdf_source = resp.read()

    reader = pypdf.PdfReader(BytesIO(pdf_source))
    pages_raw: list[list[str]] = []

    for page in reader.pages:
        raw = page.extract_text() or ""
        lines = [line for line in raw.splitlines() if line.strip()]
        pages_raw.append(lines)

    # Detect repeated header/footer lines (appear on more than one page)
    from collections import Counter
    line_counts: Counter = Counter()
    for page_lines in pages_raw:
        for line in set(page_lines):
            line_counts[line.strip()] += 1

    repeated = {line for line, count in line_counts.items() if count > 1 and len(line) < 80}

    # Build clean per-page text
    cleaned_pages: list[str] = []
    for page_num, page_lines in enumerate(pages_raw, start=1):
        cleaned: list[str] = []
        for line in page_lines:
            stripped = line.strip()
            if not stripped or stripped in repeated:
                continue

            # Normalize checkbox symbols
            check_count = len(_CHECKBOX_RE.findall(stripped))
            normalized = _CHECKBOX_RE.sub("[CHECK]", stripped)

            # Tag line type
            if check_count >= _MULTI_CHOICE_THRESHOLD:
                normalized = f"#MULTI_CHOICE_CANDIDATE {normalized}"
            elif re.search(r"  {3,}|\t", line):
                # Multiple spaces/tabs suggest table-like column layout
                normalized = f"#TABLE_ROW {normalized}"

            cleaned.append(normalized)

        if cleaned:
            cleaned_pages.append(f"--- PAGE {page_num} ---\n" + "\n".join(cleaned))

    return "\n\n".join(cleaned_pages)


# ── Stage 1: section discovery ────────────────────────────────────────────────

async def discover_sections(text: str, form_id: str) -> list[SectionBoundary]:
    """
    Send the cleaned text to gpt-4o-mini and ask only for section boundaries.
    Falls back to regex anchor detection if the LLM output is malformed.
    """
    client = _make_client()
    system = textwrap.dedent("""
        You are parsing a clinical intake PDF that has been converted to plain text.
        Your only job is to identify the section headings and their positions in the text.

        Return a JSON array — nothing else — in exactly this shape:
        [
          {"id": "s1", "title": "Section Title", "start_char": 0, "end_char": 500},
          ...
        ]

        Rules:
        - id values must be sequential strings: s1, s2, s3, ...
        - start_char and end_char are character offsets into the text you receive
        - Do not extract any questions — boundaries only
        - Ignore page markers (--- PAGE N ---) as section boundaries
    """).strip()

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": f"Text to parse:\n\n{text}"},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
        # The model may wrap in a key or return a bare array
        if isinstance(parsed, dict):
            parsed = next(iter(parsed.values()), [])
        boundaries = [SectionBoundary(**item) for item in parsed]
        if _boundaries_valid(boundaries, len(text)):
            return boundaries
    except Exception:
        pass

    # Fallback: use known clinical header regex
    return _regex_section_fallback(text, form_id)


def _boundaries_valid(boundaries: list[SectionBoundary], text_len: int) -> bool:
    if not boundaries:
        return False
    for b in boundaries:
        if b.start_char < 0 or b.end_char > text_len or b.start_char >= b.end_char:
            return False
    return True


def _regex_section_fallback(text: str, form_id: str) -> list[SectionBoundary]:
    """Build rough section boundaries using known clinical header patterns."""
    boundaries: list[SectionBoundary] = []
    header_pattern = re.compile(
        r"^(?P<title>" + "|".join(re.escape(h) for h in _KNOWN_HEADERS) + r")\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(header_pattern.finditer(text))
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        boundaries.append(SectionBoundary(
            id=f"s{idx + 1}",
            title=match.group("title").strip().title(),
            start_char=start,
            end_char=end,
        ))
    if not boundaries:
        # Last resort: treat entire document as one section
        boundaries.append(SectionBoundary(
            id="s1", title="General", start_char=0, end_char=len(text)
        ))
    return boundaries


# ── Stage 2: per-section question extraction ──────────────────────────────────

async def _extract_section_questions(
    section_text: str,
    section: SectionBoundary,
    client: AsyncOpenAI,
) -> tuple[str, list[QuestionSchema]]:
    """Extract questions from a single section. Returns (section_id, questions)."""
    is_multi_choice_section = "#MULTI_CHOICE_CANDIDATE" in section_text

    multi_choice_hint = (
        "This section contains a checkbox list (lines tagged #MULTI_CHOICE_CANDIDATE). "
        "Treat ALL checked items as options in ONE multi_choice question. "
        "Use the section title as the question text. "
        "Strip the [CHECK] and #MULTI_CHOICE_CANDIDATE markers from option labels."
    ) if is_multi_choice_section else ""

    system = textwrap.dedent(f"""
        You are extracting questions from one section of a clinical intake form.
        Section title: "{section.title}"
        {multi_choice_hint}

        Return a JSON array — nothing else — where each element has exactly these keys:
        {{
          "id": "unique_question_id",
          "text": "exact question text from the form",
          "type": "free_text | yes_no | single_choice | multi_choice | scale | numeric",
          "options": [{{"value": 0, "label": "..."}}],
          "scoring_weight": 1,
          "skip_if": null
        }}

        Rules:
        - id format: {section.id}_q<number>  (e.g. {section.id}_q1, {section.id}_q2)
        - options is an empty array for free_text, yes_no, and numeric types
        - scoring_weight is 1 for scored questions, 0 for informational ones
        - skip_if is always null at this stage
        - Do not invent questions that are not in the text
        - Strip [CHECK], #MULTI_CHOICE_CANDIDATE, #TABLE_ROW markers from all output
    """).strip()

    response = await client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": f"Section text:\n\n{section_text}"},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = next(iter(parsed.values()), [])
        questions = [QuestionSchema(**q) for q in parsed]
        return section.id, questions
    except Exception as exc:
        # Return empty on parse failure; the caller records it in ParseReport
        print(f"[form_parser] section {section.id} extraction failed: {exc}")
        return section.id, []


async def extract_questions(
    text: str,
    boundaries: list[SectionBoundary],
) -> tuple[dict[str, list[QuestionSchema]], list[str], list[str]]:
    """
    Run per-section question extraction in parallel.

    Returns:
      (questions_by_section_id, succeeded_section_ids, failed_section_ids)
    """
    client = _make_client()
    tasks = []
    for boundary in boundaries:
        section_text = text[boundary.start_char : boundary.end_char]
        tasks.append(_extract_section_questions(section_text, boundary, client))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    questions_map: dict[str, list[QuestionSchema]] = {}
    succeeded: list[str] = []
    failed: list[str] = []

    for boundary, result in zip(boundaries, results):
        if isinstance(result, Exception):
            failed.append(boundary.id)
        else:
            sec_id, questions = result
            if questions:
                questions_map[sec_id] = questions
                succeeded.append(sec_id)
            else:
                failed.append(boundary.id)

    return questions_map, succeeded, failed


# ── Stage 3: scoring extraction ───────────────────────────────────────────────

async def extract_scoring(
    text: str,
    boundaries: list[SectionBoundary],
) -> Optional[ScoringSchema]:
    """
    Look for a scoring section by title keyword match.
    Returns None if no scoring section is found.
    """
    scoring_section = next(
        (b for b in boundaries if _SCORING_KEYWORDS.search(b.title)), None
    )
    if not scoring_section:
        return None

    section_text = text[scoring_section.start_char : scoring_section.end_char]
    client = _make_client()

    system = textwrap.dedent("""
        Extract the scoring logic from this clinical form section.

        Return a JSON object — nothing else — in exactly this shape:
        {
          "enabled": true,
          "method": "sum",
          "ranges": [
            {"min": 0, "max": 4, "triage_level": "low", "label": "Minimal"},
            ...
          ]
        }

        triage_level must be one of: "low", "moderate", "high", "emergency"
        method must be "sum" or "weighted"
        If no scoring is described, return {"enabled": false, "method": "sum", "ranges": []}
    """).strip()

    response = await client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": section_text},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
        return ScoringSchema(
            enabled=data.get("enabled", False),
            method=data.get("method", "sum"),
            ranges=[ScoringRange(**r) for r in data.get("ranges", [])],
        )
    except Exception:
        return None


# ── Stage 4: conversational hint generation ───────────────────────────────────

async def _generate_hint_batch(
    questions: list[QuestionSchema],
    client: AsyncOpenAI,
) -> list[str]:
    """Generate conversational rephrasing for a batch of up to 15 questions."""
    question_list = "\n".join(
        f"{i + 1}. {q.text}" for i, q in enumerate(questions)
    )
    system = textwrap.dedent("""
        You are rephrasing clinical intake form questions into warm, conversational
        language for a patient interview. The interviewer is an AI intake assistant.

        Return a JSON array of strings — nothing else — with exactly as many items
        as questions provided, in the same order. Each string is the rephrased version
        of the corresponding question. Keep rephrasing to one or two sentences.
        Do not include numbering or labels in the output strings.
    """).strip()

    response = await client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": f"Questions to rephrase:\n{question_list}"},
        ],
        temperature=0.3,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = next(iter(parsed.values()), [])
        return [str(h) for h in parsed]
    except Exception:
        return [""] * len(questions)


async def generate_hints(
    sections: list[SectionSchema],
) -> tuple[list[SectionSchema], list[str]]:
    """
    Add conversational_hint to every question that doesn't already have one.
    Returns updated sections and list of question IDs that still have no hint.
    """
    # Collect questions needing hints
    needing_hints: list[tuple[int, int, QuestionSchema]] = []
    for sec_idx, section in enumerate(sections):
        for q_idx, question in enumerate(section.questions):
            if not question.conversational_hint:
                needing_hints.append((sec_idx, q_idx, question))

    if not needing_hints:
        return sections, []

    client = _make_client()

    # Batch into groups of HINT_BATCH_SIZE
    batches = [
        needing_hints[i : i + _HINT_BATCH_SIZE]
        for i in range(0, len(needing_hints), _HINT_BATCH_SIZE)
    ]

    batch_results = await asyncio.gather(
        *[_generate_hint_batch([q for _, _, q in batch], client) for batch in batches],
        return_exceptions=True,
    )

    missing: list[str] = []
    for batch, hints in zip(batches, batch_results):
        if isinstance(hints, Exception):
            for _, _, q in batch:
                missing.append(q.id)
            continue
        for (sec_idx, q_idx, question), hint in zip(batch, hints):
            if hint:
                sections[sec_idx].questions[q_idx] = question.model_copy(
                    update={"conversational_hint": hint}
                )
            else:
                missing.append(question.id)

    return sections, missing


# ── Stage 5: assembly + validation ────────────────────────────────────────────

def assemble_form(
    form_id: str,
    title: str,
    description: str,
    source_url: str,
    boundaries: list[SectionBoundary],
    questions_map: dict[str, list[QuestionSchema]],
    scoring: Optional[ScoringSchema],
    succeeded: list[str],
    failed: list[str],
    retried: list[str],
) -> tuple[FormSchema, ParseReport]:
    """
    Combine all stage outputs into a validated FormSchema.
    Raises ValidationError if the assembled form is malformed.
    """
    sections: list[SectionSchema] = []
    missing_hints: list[str] = []
    ambiguous_types: list[str] = []

    for boundary in boundaries:
        questions = questions_map.get(boundary.id, [])
        for q in questions:
            if not q.conversational_hint:
                missing_hints.append(q.id)
            if q.type == "free_text" and q.options:
                ambiguous_types.append(q.id)
        sections.append(SectionSchema(
            id=boundary.id,
            title=boundary.title,
            questions=questions,
        ))

    form = FormSchema(
        form_id=form_id,
        title=title,
        description=description,
        source_url=source_url,
        sections=sections,
        scoring=scoring or ScoringSchema(),
    )

    total_questions = sum(len(s.questions) for s in form.sections)

    report = ParseReport(
        form_id=form_id,
        sections_found=len(boundaries),
        sections_succeeded=succeeded,
        sections_retried=retried,
        sections_failed=failed,
        questions_total=total_questions,
        questions_missing_hints=missing_hints,
        ambiguous_type_questions=ambiguous_types,
        scoring_extracted=scoring is not None and scoring.enabled,
        warnings=[
            f"Section {sid} failed extraction and was left empty." for sid in failed
        ],
    )

    return form, report


# ── Public entry point ────────────────────────────────────────────────────────

async def parse_pdf(
    pdf_source: bytes | str,
    form_id: str,
    title: str,
    description: str = "",
    source_url: str = "",
) -> tuple[FormSchema, ParseReport]:
    """
    Run the full 5-stage pipeline and return a validated FormSchema + ParseReport.

    pdf_source — raw PDF bytes or a URL string
    form_id    — snake_case identifier used as the filename key
    title      — human-readable form title
    """
    # Stage 0
    clean_text = extract_and_clean(pdf_source)

    # Stage 1
    boundaries = await discover_sections(clean_text, form_id)

    # Stages 2 + 3 run concurrently
    questions_task = asyncio.create_task(
        extract_questions(clean_text, boundaries)
    )
    scoring_task = asyncio.create_task(
        extract_scoring(clean_text, boundaries)
    )
    (questions_map, succeeded, failed), scoring = await asyncio.gather(
        questions_task, scoring_task
    )

    # Stage 4: build sections first so we can mutate them in-place
    sections_draft: list[SectionSchema] = [
        SectionSchema(
            id=b.id,
            title=b.title,
            questions=questions_map.get(b.id, []),
        )
        for b in boundaries
    ]
    updated_sections, missing_hints = await generate_hints(sections_draft)

    # Rebuild questions_map from updated sections for assembly
    updated_map = {s.id: s.questions for s in updated_sections}

    # Stage 5
    form, report = assemble_form(
        form_id=form_id,
        title=title,
        description=description,
        source_url=source_url,
        boundaries=boundaries,
        questions_map=updated_map,
        scoring=scoring,
        succeeded=succeeded,
        failed=failed,
        retried=[],
    )
    report.questions_missing_hints = missing_hints

    return form, report
