import sys
import re
import fitz
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PDF_DIR = Path(r"C:\UTCluj\an4\TomaRaul_LICENTA\pdf_pipeline\pdf_processed")

def extract_text(p):
    doc = fitz.open(p)
    t = "".join(page.get_text() for page in doc)
    doc.close()
    return t

def diag(pdf):
    text = extract_text(str(pdf))
    issues = []

    m = re.search(r"2\.1\s+Denumirea\s+disciplinei\s*\n+\s*([^\n]+)", text, re.IGNORECASE)
    name = m.group(1).strip() if m else None
    if not name:
        issues.append("name: MISSING")
    elif len(name) > 80:
        issues.append(f"name: too long ({len(name)} chars) — '{name[:80]}...'")
    elif name.count(",") >= 1 and len(name) > 50:
        issues.append(f"name: comma-joined multi-subject? — '{name}'")

    if m:
        end = m.end()
        rest = text[end:end+150]
        next_line = rest.lstrip("\n").split("\n", 1)[0].strip() if rest.lstrip("\n") else ""
        if next_line and not re.match(r"^\s*2\.\d", next_line) and len(next_line) > 20:
            if re.match(r"^[A-ZȘȚĂÎÂ]", next_line):
                issues.append(f"name: next-line follow-on? — '{next_line[:80]}'")

    m = re.search(r"Anul\s+de\s+studiu\s*[:\n\s]*([IViv]{1,3}|[1-4])\b", text, re.IGNORECASE)
    if not m:
        issues.append("year: MISSING")
    else:
        tok = m.group(1).lower()
        year = int(tok) if tok.isdigit() else {"i": 1, "ii": 2, "iii": 3, "iv": 4}.get(tok)
        if year is None or year < 1 or year > 4:
            issues.append(f"year: out of range — {m.group(1)}")

    m = re.search(r"Semestrul\s*[\n:\s]*(\d{1,2})\b", text, re.IGNORECASE)
    if not m:
        issues.append("sem: MISSING")
    else:
        s = int(m.group(1))
        if s < 1 or s > 8:
            issues.append(f"sem: out of range — {s}")

    m = re.search(r"Num[ăa]rul\s+de\s+credite\s*[\n:\s]*(\d+)", text, re.IGNORECASE)
    if not m:
        issues.append("credits: MISSING")
    else:
        c = int(m.group(1))
        if c < 1 or c > 12:
            issues.append(f"credits: suspicious — {c}")

    m = re.search(r"Tipul\s+de\s+evaluare.*?\)\s*\n\s*([ECV])\b", text, re.DOTALL | re.IGNORECASE)
    if not m:
        issues.append("eval: MISSING (E/C/V)")

    m = re.search(r"2\.2\s+Titularii?\s+de\s+curs\s*\n+(.+?)\n\s*2\.3", text, re.DOTALL | re.IGNORECASE)
    if not m:
        issues.append("titulari curs: section missing")
    else:
        body = m.group(1)
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", body)
        if len(emails) == 0:
            issues.append("titulari curs: no emails extracted")

    m = re.search(r"1\.6\s+Programul?\s+de\s+studii\s*/?\s*Calificarea\s*\n+\s*([^\n]+)",
                  text, re.IGNORECASE)
    if not m:
        issues.append("program: MISSING")

    sec_count = len(re.findall(r"^\s*([1-9]|10)\.\s+\w", text, re.MULTILINE))
    if sec_count < 5:
        issues.append(f"sections: only {sec_count} headers detected")

    return issues

def main():
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    print(f"Scanning {len(pdfs)} PDFs in {PDF_DIR}\n")
    bad = 0
    for p in pdfs:
        issues = diag(p)
        if issues:
            bad += 1
            print(f"=== {p.name} ===")
            for x in issues:
                print(f"  ! {x}")
            print()
    print(f"--- {bad}/{len(pdfs)} PDFs have at least one issue ---")

if __name__ == "__main__":
    main()
