import os
import re
import sys
from collections import defaultdict

import psycopg2
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", ""),
}

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
MANIFEST_SOURCE = "manifest_semestre"

ROMAN_TO_INT = {"i": 1, "ii": 2, "iii": 3, "iv": 4}
INT_TO_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}

def get_embedding(text: str) -> list:
    response = requests.post(
        OLLAMA_URL,
        json={"model": EMBEDDING_MODEL, "prompt": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["embedding"]

def format_vector(embedding: list) -> str:
    return "[" + ",".join(map(str, embedding)) + "]"

def extract_discipline_info(cur, source: str):
    cur.execute(
        "SELECT question, answer FROM knowledge_base WHERE source = %s",
        (source,),
    )
    rows = cur.fetchall()
    blob = "\n".join((q or "") + "\n" + (a or "") for q, a in rows)

    name = None
    credits = None
    year = None
    semester = None
    spec = None

    m = re.search(r"Disciplina\s+(.+?)\s+are\s+(\d+)\s+credite", blob, re.IGNORECASE)
    if m:
        name = m.group(1).strip().rstrip(".")
        credits = int(m.group(2))

    m = re.search(r"studiaz[ăa]\s+(?:se\s+)?[îi]n\s+anul\s+([IViv]+|\d+)", blob, re.IGNORECASE)
    if m:
        token = m.group(1).lower()
        if token.isdigit():
            year = int(token)
        else:
            year = ROMAN_TO_INT.get(token)

    m = re.search(r"studiaz[ăa]\s+(?:se\s+)?[îi]n\s+semestrul\s+(\d+)", blob, re.IGNORECASE)
    if m:
        semester = int(m.group(1))

    m = re.search(r"Specializarea:\s*(CTI|Calculatoare|TI)\b", blob)
    if m:
        spec = m.group(1)

    if semester is None:
        if source.endswith("1.pdf"):
            semester = 1
        elif source.endswith("2.pdf"):
            semester = 2

    if not name or credits is None or semester is None or year is None:
        print(f"  [skip] {source}: name={name!r} credits={credits} year={year} sem={semester} spec={spec}")
        return None

    if year < 4 and spec != "TI":
        spec = "CTI"

    return name, credits, year, semester, spec

SPEC_LABELS = {
    "CTI": "Calculatoare și Tehnologia Informației",
    "Calculatoare": "Calculatoare",
    "TI": "Tehnologia Informației",
}

def spec_phrases(spec):
    if not spec:
        return [""]
    full = SPEC_LABELS.get(spec, spec)
    if spec == "CTI":
        return [
            "",
            f" la specializarea {spec}",
            f" la {full}",
            f" la {spec}",
        ]
    return [
        f" la specializarea {spec}",
        f" la {spec}",
        f" la {full}",
        f" la pachetul {spec}",
        f" in pachetul de {spec}",
        f" pe sectia {spec}",
    ]

def year_tokens(year_roman):
    arabic = {"I": "1", "II": "2", "III": "3", "IV": "4"}.get(year_roman, year_roman)
    return [year_roman, arabic]

def sem_tokens(sem):
    relative = ((sem - 1) % 2) + 1
    if relative == sem:
        return [sem]
    return [sem, relative]

def _spec_in_answer(spec):
    if not spec or spec == "CTI":
        return ""
    return f" la specializarea {SPEC_LABELS.get(spec, spec)}"

def variants_subjects_in_semester(year_roman, sem, subjects, spec=None):
    names = [n for n, _ in subjects]
    listing = ", ".join(names)
    listing_bullets = "\n".join(f"- {n}" for n in names)
    sa = _spec_in_answer(spec)
    answer = (
        f"In semestrul {sem} al anului {year_roman}{sa} se studiaza urmatoarele "
        f"{len(names)} discipline: {listing}."
    )
    pairs = []
    for yr in year_tokens(year_roman):
        for s in sem_tokens(sem):
            for sp in spec_phrases(spec):
                questions = [
                    f"Ce materii sunt in semestrul {s} anul {yr}{sp}?",
                    f"Care sunt disciplinele din semestrul {s} anul {yr}{sp}?",
                    f"Ce cursuri se fac in semestrul {s} anul {yr}{sp}?",
                    f"Lista materiilor din semestrul {s} anul {yr}{sp}",
                    f"Ce materii sunt in sem {s} an {yr}{sp}?",
                ]
                if not spec:
                    questions += [
                        f"Ce materii sunt in semestrul {s}?",
                        f"Care sunt disciplinele din semestrul {s}?",
                    ]
                pairs += [(q, answer) for q in questions]
                pairs.append((
                    f"Enumera materiile din semestrul {s} anul {yr}{sp}",
                    f"Materiile din semestrul {s} anul {yr}{sp}:\n{listing_bullets}",
                ))
    return pairs

def variants_credits_per_subject(year_roman, sem, subjects, spec=None):
    lines = [f"- {n}: {c} credite" for n, c in subjects]
    sa = _spec_in_answer(spec)
    answer = (
        f"Creditele disciplinelor din semestrul {sem} anul {year_roman}{sa}:\n"
        + "\n".join(lines)
    )
    inline = ", ".join(f"{n} ({c} cr)" for n, c in subjects)
    answer_inline = f"In semestrul {sem} anul {year_roman}{sa}: {inline}."
    pairs = []
    for yr in year_tokens(year_roman):
        for s in sem_tokens(sem):
            for sp in spec_phrases(spec):
                questions = [
                    f"Cate credite are fiecare materie din semestrul {s} anul {yr}{sp}?",
                    f"Cate credite are fiecare disciplina din semestrul {s} anul {yr}{sp}?",
                    f"Spune creditele pentru fiecare materie din semestrul {s} anul {yr}{sp}",
                    f"Lista materiilor cu credite din semestrul {s} anul {yr}{sp}",
                    f"Creditele materiilor din semestrul {s} anul {yr}{sp}",
                ]
                if not spec:
                    questions += [
                        f"Cate credite are fiecare materie din semestrul {s}?",
                        f"Cate credite are fiecare disciplina din semestrul {s}?",
                        f"Cate credite are fiecare materie din sem {s}?",
                        f"Cate credite are fiecare curs din semestrul {s}?",
                    ]
                pairs += [(q, answer) for q in questions]
                pairs.append((f"Materii cu credite semestrul {s} anul {yr}{sp}", answer_inline))
    return pairs

def variants_total_credits(year_roman, sem, subjects, spec=None):
    total = sum(c for _, c in subjects)
    sa = _spec_in_answer(spec)
    answer = (
        f"In semestrul {sem} al anului {year_roman}{sa} se acumuleaza in total "
        f"{total} de credite ({len(subjects)} discipline)."
    )
    pairs = []
    for yr in year_tokens(year_roman):
        for s in sem_tokens(sem):
            for sp in spec_phrases(spec):
                questions = [
                    f"Cate credite sunt in total in semestrul {s} anul {yr}{sp}?",
                    f"Care e totalul de credite din semestrul {s} anul {yr}{sp}?",
                    f"Cate credite are semestrul {s} anul {yr}{sp}?",
                    f"Total credite semestrul {s} anul {yr}{sp}",
                ]
                if not spec:
                    questions.append(f"Cate credite are semestrul {s}?")
                pairs += [(q, answer) for q in questions]
    return pairs

def variants_count_subjects(year_roman, sem, subjects, spec=None):
    count = len(subjects)
    sa = _spec_in_answer(spec)
    answer = f"Semestrul {sem} al anului {year_roman}{sa} are {count} discipline."
    pairs = []
    for yr in year_tokens(year_roman):
        for s in sem_tokens(sem):
            for sp in spec_phrases(spec):
                questions = [
                    f"Cate materii sunt in semestrul {s} anul {yr}{sp}?",
                    f"Cate discipline sunt in semestrul {s} anul {yr}{sp}?",
                    f"Cate cursuri sunt in semestrul {s} anul {yr}{sp}?",
                ]
                if not spec:
                    questions.append(f"Cate materii are semestrul {s}?")
                pairs += [(q, answer) for q in questions]
    return pairs

def variants_year_summary(year_roman, all_subjects_by_sem, spec=None):
    pairs = []
    flat = []
    for sem in sorted(all_subjects_by_sem):
        flat.extend(all_subjects_by_sem[sem])
    total_credits = sum(c for _, c in flat)
    total_count = len(flat)
    sa = _spec_in_answer(spec)

    names = ", ".join(n for n, _ in flat)
    answer_subjects = (
        f"In anul {year_roman}{sa} se studiaza {total_count} discipline: {names}."
    )
    answer_credits = (
        f"In anul {year_roman}{sa} se acumuleaza {total_credits} de credite "
        f"din {total_count} discipline."
    )
    sections = []
    for sem in sorted(all_subjects_by_sem):
        subs = all_subjects_by_sem[sem]
        sections.append(
            f"Semestrul {sem}:\n" + "\n".join(f"- {n}: {c} credite" for n, c in subs)
        )
    answer_per_sem = (
        f"Creditele disciplinelor din anul {year_roman}{sa}, pe semestre:\n\n"
        + "\n\n".join(sections)
    )

    for yr in year_tokens(year_roman):
        for sp in spec_phrases(spec):
            for q in [
                f"Ce materii sunt in anul {yr}{sp}?",
                f"Care sunt disciplinele din anul {yr}{sp}?",
                f"Ce cursuri se fac in anul {yr}{sp}?",
                f"Lista materiilor din anul {yr}{sp}",
            ]:
                pairs.append((q, answer_subjects))
            for q in [
                f"Cate credite are anul {yr}{sp} in total?",
                f"Total credite anul {yr}{sp}",
                f"Care e totalul de credite din anul {yr}{sp}?",
            ]:
                pairs.append((q, answer_credits))
            for q in [
                f"Cate credite are fiecare materie din anul {yr}{sp}?",
                f"Creditele materiilor din anul {yr}{sp}",
                f"Spune creditele pentru fiecare materie din anul {yr}{sp}",
            ]:
                pairs.append((q, answer_per_sem))

    return pairs

def variants_year_specializations(year_roman, specs):
    real_specs = [s for s in specs if s != "CTI"]
    if not real_specs:
        return []
    labels = [SPEC_LABELS.get(s, s) for s in real_specs]
    if len(labels) == 1:
        listing = labels[0]
    elif len(labels) == 2:
        listing = f"{labels[0]} și {labels[1]}"
    else:
        listing = ", ".join(labels[:-1]) + f" și {labels[-1]}"
    answer = (
        f"In anul {year_roman} programul de studii este împărțit pe "
        f"{len(real_specs)} specializări: {listing}."
    )
    questions = []
    for yr in year_tokens(year_roman):
        questions += [
            f"Pe ce specializari se imparte anul {yr}?",
            f"Ce specializari sunt in anul {yr}?",
            f"Care sunt specializarile din anul {yr}?",
            f"Cate specializari are anul {yr}?",
            f"In ce specializari se imparte anul {yr}?",
            f"Ce pachete sunt in anul {yr}?",
            f"Care sunt pachetele anului {yr}?",
        ]
    return [(q, answer) for q in questions]

def generate_manifest_qna(grouped):
    pairs = []

    by_year_spec = defaultdict(lambda: defaultdict(list))
    for (year, sem, spec), subs in grouped.items():
        deduped = {}
        for name, credits in subs:
            if name in deduped:
                deduped[name] = max(deduped[name], credits)
            else:
                deduped[name] = credits
        subs_sorted = sorted(deduped.items(), key=lambda s: s[0].lower())
        year_roman = INT_TO_ROMAN.get(year, str(year))
        pairs.extend(variants_subjects_in_semester(year_roman, sem, subs_sorted, spec))
        pairs.extend(variants_credits_per_subject(year_roman, sem, subs_sorted, spec))
        pairs.extend(variants_total_credits(year_roman, sem, subs_sorted, spec))
        pairs.extend(variants_count_subjects(year_roman, sem, subs_sorted, spec))
        by_year_spec[(year, spec)][sem] = subs_sorted

    for (year, spec), sem_map in by_year_spec.items():
        year_roman = INT_TO_ROMAN.get(year, str(year))
        pairs.extend(variants_year_summary(year_roman, sem_map, spec))

    specs_per_year = defaultdict(set)
    for (year, _, spec), _ in grouped.items():
        if spec:
            specs_per_year[year].add(spec)

    multi_spec_years = {y for y, specs in specs_per_year.items() if len(specs) > 1}

    union_year_sem = defaultdict(dict)
    union_year = defaultdict(lambda: defaultdict(dict))
    for (year, sem, spec), subs in grouped.items():
        for name, credits in subs:
            union_year_sem[(year, sem)][name] = credits
            union_year[year][sem][name] = credits

    for (year, sem), name_map in union_year_sem.items():
        if year not in multi_spec_years:
            continue
        subs_sorted = sorted(name_map.items(), key=lambda s: s[0].lower())
        year_roman = INT_TO_ROMAN.get(year, str(year))
        pairs.extend(variants_subjects_in_semester(year_roman, sem, subs_sorted, None))
        pairs.extend(variants_credits_per_subject(year_roman, sem, subs_sorted, None))
        pairs.extend(variants_total_credits(year_roman, sem, subs_sorted, None))
        pairs.extend(variants_count_subjects(year_roman, sem, subs_sorted, None))

    for year, sem_map in union_year.items():
        if year not in multi_spec_years:
            continue
        merged = {sem: sorted(names.items(), key=lambda s: s[0].lower())
                  for sem, names in sem_map.items()}
        year_roman = INT_TO_ROMAN.get(year, str(year))
        pairs.extend(variants_year_summary(year_roman, merged, None))

    for year, specs in specs_per_year.items():
        if not specs:
            continue
        year_roman = INT_TO_ROMAN.get(year, str(year))
        pairs.extend(variants_year_specializations(year_roman, sorted(specs)))

    return pairs

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute(
        "SELECT DISTINCT source FROM knowledge_base "
        "WHERE source LIKE %s ORDER BY source",
        ("%.pdf",),
    )
    sources = [r[0] for r in cur.fetchall()]
    print(f"Found {len(sources)} discipline sources.")

    grouped = defaultdict(list)
    for src in sources:
        info = extract_discipline_info(cur, src)
        if info is None:
            continue
        name, credits, year, sem, spec = info
        print(f"  [ok] {src}: {name} -> {credits} cr, an {year}, sem {sem}, spec={spec}")
        grouped[(year, sem, spec)].append((name, credits))

    if not grouped:
        print("No disciplines parsed. Aborting.")
        sys.exit(1)

    for (year, sem, spec), subs in list(grouped.items()):
        if year == 4 and spec == "CTI":
            for target in ("Calculatoare", "TI"):
                key = (4, sem, target)
                grouped[key] = grouped.get(key, []) + list(subs)

    pairs = generate_manifest_qna(grouped)
    print(f"\nGenerated {len(pairs)} aggregated Q&A pairs.")

    cur.execute(
        "DELETE FROM knowledge_base WHERE source = %s",
        (MANIFEST_SOURCE,),
    )
    deleted = cur.rowcount
    print(f"Cleared {deleted} previous manifest entries.")
    conn.commit()

    inserted = 0
    for i, (question, answer) in enumerate(pairs, 1):
        text = question + " " + answer
        try:
            vec = format_vector(get_embedding(text))
        except Exception as exc:
            print(f"  [warn] embedding failed for #{i}: {exc}")
            continue
        cur.execute(
            "INSERT INTO knowledge_base "
            "(question, answer, source, embedding, chunk_type, status) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (question, answer, MANIFEST_SOURCE, vec, "qna", "active"),
        )
        inserted += 1
        if inserted % 10 == 0:
            conn.commit()
            print(f"  inserted {inserted}/{len(pairs)}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. Inserted {inserted} manifest entries with source='{MANIFEST_SOURCE}'.")

if __name__ == "__main__":
    main()
