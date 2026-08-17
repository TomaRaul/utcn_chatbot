import os
import re
import sys
import requests
import psycopg2
import fitz
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "chatbot_db",
    "user": "postgres",
    "password": os.getenv("DB_PASSWORD", "")
}

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
PDF_DIR = "./pdf_processed"

SECTION_NAMES = {
    "1": "Date despre program",
    "2": "Date despre disciplină (denumire, titulari curs, titulari seminar/laborator, an, semestru, tip evaluare, regim)",
    "3": "Timpul total estimat (ore curs, seminar, laborator, credite)",
    "4": "Precondiții",
    "5": "Condiții de desfășurare",
    "6": "Competențele specifice acumulate",
    "7": "Obiectivele disciplinei",
    "8": "Conținuturi (programa de curs, seminar, laborator, bibliografie)",
    "9": "Coroborare cu așteptările comunității",
    "10": "Evaluare (criterii, metode, ponderi)",
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_embedding(text):
    r = requests.post(OLLAMA_URL, json={"model": EMBEDDING_MODEL, "prompt": text}, timeout=120)
    r.raise_for_status()
    return r.json()["embedding"]

def format_vector(emb):
    return "[" + ",".join(map(str, emb)) + "]"

def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def clean_text(text):
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln.strip())

def extract_discipline_name(text):
    m = re.search(r"2\.1\s+Denumirea\s+disciplinei\s*\n+\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None

def split_into_sections(text):
    pattern = re.compile(
        r"(?m)^\s*(\d{1,2})\.\s+("
        r"Date\s+despre\s+program(?!ul)"
        r"|Date\s+despre\s+disciplin"
        r"|Timpul\s+total"
        r"|Precondi"
        r"|Condi[tț]ii"
        r"|Competen[tț]e"
        r"|Obiectivele"
        r"|Con[tț]inuturi"
        r"|Coroborare"
        r"|Evaluare"
        r")",
        re.IGNORECASE
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return [("0", text)]
    sections = []
    for i, m in enumerate(matches):
        sec_num = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sec_text = text[start:end].strip()
        if sec_text:
            sections.append((sec_num, sec_text))
    return sections

def _grab(text, start_pat, end_pat):
    m = re.search(start_pat + r"\s*\n+(.*?)\n+\s*(?=" + end_pat + r")", text, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    val = m.group(1).strip()
    val = re.sub(r"\s+", " ", val)
    return val if val and val.upper() != "N/A" else None

def _strip_section_header(val):
    if not val:
        return val
    m = re.search(r"\b(?:Prof|Conf|Lect|Lector|As|Asist|Asistent|Şl|Șl|Dr)\b\.?", val)
    return val[m.start():].strip() if m else val.strip()

def normalize_program(raw):
    if not raw:
        return None
    s = raw.lower()
    has_calc = "calculatoare" in s
    has_ti = "tehnologia informa" in s
    if has_calc and has_ti:
        return "CTI"
    if has_ti:
        return "TI"
    if has_calc:
        return "Calculatoare"
    return None

PROGRAM_LABELS = {
    "CTI": "Calculatoare și Tehnologia Informației",
    "Calculatoare": "Calculatoare",
    "TI": "Tehnologia Informației",
}

def extract_facts(text, discipline):
    facts = {"discipline": discipline}
    m = re.search(
        r"1\.6\s+Programul?\s+de\s+studii\s*/?\s*Calificarea\s*\n+\s*([^\n]+)",
        text,
        re.IGNORECASE,
    )
    raw_prog = m.group(1).strip() if m else None
    facts["program_raw"] = raw_prog
    facts["program"] = normalize_program(raw_prog)
    facts["titulari_curs"] = _strip_section_header(
        _grab(text, r"2\.2\s+Titularii?\s+de\s+curs", r"2\.3\s+")
    )
    facts["titulari_sem_lab"] = _strip_section_header(
        _grab(text, r"2\.3\s+(?:Titularul|Titularii)\b[^\n]*", r"2\.4\s+")
    )
    m = re.search(
        r"Anul\s+de\s+studiu\s*[:\n\s]*([IViv]{1,3}|[1-4])\b",
        text,
        re.IGNORECASE,
    )
    facts["anul"] = m.group(1).strip() if m else None
    m = re.search(r"2\.5\s+Semestrul\s*\n*\s*(\d{1,2})\b", text, re.IGNORECASE)
    facts["semestrul"] = m.group(1).strip() if m else None
    m = re.search(r"2\.6\s+Tipul\s+de\s+evaluare.*?\)\s*\n\s*([ECV])\b", text, re.DOTALL | re.IGNORECASE)
    facts["tip_evaluare"] = m.group(1).strip() if m else None
    m = re.search(r"3\.1\s+Num[ăa]r\s+de\s+ore\s+pe\s+s[ăa]pt[ăa]m[âa]n[ăa]\s*\n+\s*(\d+)", text, re.IGNORECASE)
    facts["ore_total_sapt"] = m.group(1).strip() if m else None
    m = re.search(r"Num[ăa]rul\s+de\s+credite\s*[:\n\s]*(\d+)\b", text, re.IGNORECASE)
    facts["credite"] = m.group(1).strip() if m else None
    return facts

EVAL_LABEL = {"E": "examen", "C": "colocviu", "V": "verificare"}

def build_qna_pairs(facts):
    d = facts["discipline"]
    pairs = []

    titulari_curs = facts.get("titulari_curs")
    titulari_sl = facts.get("titulari_sem_lab")

    if titulari_curs or titulari_sl:
        ans = []
        if titulari_curs:
            ans.append(f"Titularii de curs ai disciplinei {d} sunt: {titulari_curs}.")
        if titulari_sl and titulari_sl != titulari_curs:
            ans.append(f"Titularii de seminar / laborator / proiect ai disciplinei {d} sunt: {titulari_sl}.")
        elif titulari_sl:
            ans.append(f"Aceiași titulari susțin și activitățile de seminar / laborator / proiect.")
        full_answer = " ".join(ans)

        for q in [
            f"Cine predă {d}?",
            f"Cine este titularul disciplinei {d}?",
            f"Cine sunt profesorii de la {d}?",
            f"Cine ține cursul la {d}?",
            f"Care sunt cadrele didactice de la {d}?",
        ]:
            pairs.append((q, full_answer))

        if titulari_sl:
            for q in [
                f"Cine ține seminarul la {d}?",
                f"Cine ține laboratorul la {d}?",
                f"Cine sunt titularii de seminar la {d}?",
            ]:
                pairs.append((q, f"Titularii de seminar / laborator / proiect ai disciplinei {d} sunt: {titulari_sl}."))

    if facts.get("credite"):
        a = f"Disciplina {d} are {facts['credite']} credite."
        for q in [
            f"Câte credite are {d}?",
            f"Care este numărul de credite pentru {d}?",
            f"Cu câte credite se cotează {d}?",
        ]:
            pairs.append((q, a))

    if facts.get("ore_total_sapt"):
        a = f"Disciplina {d} are {facts['ore_total_sapt']} ore pe săptămână în total."
        for q in [
            f"Câte ore pe săptămână are {d}?",
            f"Câte ore are {d}?",
            f"Câte ore săptămânale sunt la {d}?",
        ]:
            pairs.append((q, a))

    if facts.get("tip_evaluare"):
        code = facts["tip_evaluare"].upper()
        label = EVAL_LABEL.get(code, code)
        a = f"Tipul de evaluare la disciplina {d} este {label} (cod: {code})."
        for q in [
            f"Care este tipul de evaluare la {d}?",
            f"Cum se evaluează la {d}?",
            f"Ce tip de examinare are {d}?",
            f"Are examen la {d}?",
        ]:
            pairs.append((q, a))

    if facts.get("program"):
        prog_key = facts["program"]
        prog_label = PROGRAM_LABELS.get(prog_key, prog_key)
        a = f"Disciplina {d} face parte din programul {prog_label}. Specializarea: {prog_key}."
        for q in [
            f"La ce specializare se face {d}?",
            f"La ce program de studii se face {d}?",
            f"Pe ce specializare este {d}?",
            f"{d} la ce specializare se preda?",
        ]:
            pairs.append((q, a))

    if facts.get("anul"):
        a = f"Disciplina {d} se studiază în anul {facts['anul']}."
        for q in [
            f"În ce an se face {d}?",
            f"În ce an de studiu se predă {d}?",
        ]:
            pairs.append((q, a))

    if facts.get("semestrul"):
        a = f"Disciplina {d} se studiază în semestrul {facts['semestrul']}."
        for q in [
            f"În ce semestru se face {d}?",
            f"În ce semestru se predă {d}?",
        ]:
            pairs.append((q, a))

    for full in re.findall(r"([A-ZȘȚĂÎÂ][^,\n]*?)\s*-\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+)",
                           " ".join(filter(None, [titulari_curs, titulari_sl]))):
        name_full = full[0].strip()
        email = full[1].strip()
        m = re.search(r"([A-ZȘȚĂÎÂ][a-zșțăîâ]+)\s*$", name_full)
        last = m.group(1) if m else name_full
        a = f"Adresa de email a profesorului {name_full} este {email}."
        for q in [
            f"Care este emailul lui {last}?",
            f"Care este adresa de email a {last}?",
            f"Ce email are {last}?",
            f"Care este emailul lui {name_full}?",
        ]:
            pairs.append((q, a))

    return pairs

def build_chunks(pdf_path):
    filename = os.path.basename(pdf_path)
    raw = extract_text(pdf_path)
    text = clean_text(raw)
    discipline = extract_discipline_name(text) or filename.replace(".pdf", "")

    chunks = []

    facts = extract_facts(text, discipline)
    qna_pairs = build_qna_pairs(facts)
    for q, a in qna_pairs:
        chunks.append({
            "discipline": discipline,
            "section": "qna",
            "section_label": "Q&A extras din fișa de disciplină",
            "filename": filename,
            "question": q,
            "answer": a,
            "embed_text": q + " " + a,
        })

    sections = split_into_sections(text)
    for sec_num, sec_text in sections:
        sec_label = SECTION_NAMES.get(sec_num, "")
        header = f"Disciplina: {discipline}.\nSecțiunea {sec_num} — {sec_label}.\n\n"
        body = sec_text
        q_text = f"Informații despre {discipline} — secțiunea {sec_num} ({sec_label})"

        if len(body) > 1800:
            sub_chunks = _split_long_section(body, 1500)
            for j, sc in enumerate(sub_chunks, 1):
                full = header + f"(partea {j}/{len(sub_chunks)})\n" + sc
                chunks.append({
                    "discipline": discipline,
                    "section": sec_num,
                    "section_label": sec_label,
                    "filename": filename,
                    "question": q_text + f" (partea {j}/{len(sub_chunks)})",
                    "answer": full,
                    "embed_text": q_text + " " + full,
                })
        else:
            full = header + body
            chunks.append({
                "discipline": discipline,
                "section": sec_num,
                "section_label": sec_label,
                "filename": filename,
                "question": q_text,
                "answer": full,
                "embed_text": q_text + " " + full,
            })
    return chunks

def _split_long_section(text, target):
    parts = []
    paras = text.split("\n\n")
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 2 > target and buf:
            parts.append(buf.strip())
            buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf.strip():
        parts.append(buf.strip())
    if not parts:
        return [text[i:i+target] for i in range(0, len(text), target)]
    return parts

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    resume = os.environ.get("RESUME_INGEST") == "1"

    already_done = set()
    if resume:
        cur.execute(
            "SELECT DISTINCT source FROM knowledge_base WHERE source LIKE '%.pdf'"
        )
        already_done = {r[0] for r in cur.fetchall()}
        log(f"RESUME mode: {len(already_done)} PDFs already in DB will be skipped.")
    else:
        cur.execute("DELETE FROM knowledge_base WHERE source LIKE '%.pdf'")
        deleted = cur.rowcount
        conn.commit()
        log(f"Deleted {deleted} old PDF chunks.")

    pdf_files = sorted(Path(PDF_DIR).glob("*.pdf"))
    log(f"Found {len(pdf_files)} PDFs in folder.")

    total = 0
    skipped = 0
    for pdf in pdf_files:
        if pdf.name in already_done:
            skipped += 1
            continue
        log(f"Processing {pdf.name}")
        chunks = build_chunks(str(pdf))
        qna_count = sum(1 for c in chunks if c["section"] == "qna")
        sec_count = len(chunks) - qna_count
        log(f"  Built {qna_count} Q&A pairs + {sec_count} section chunks (discipline: {chunks[0]['discipline'] if chunks else '?'})")
        for ch in chunks:
            try:
                emb = get_embedding(ch["embed_text"])
                chunk_type = "qna" if ch["section"] == "qna" else "section"
                cur.execute(
                    "INSERT INTO knowledge_base (question, answer, source, embedding, chunk_type) VALUES (%s, %s, %s, %s, %s)",
                    (ch["question"], ch["answer"], ch["filename"], format_vector(emb), chunk_type)
                )
                total += 1
            except Exception as e:
                log(f"  Embedding failed for {ch['filename']} sec {ch['section']}: {e}")
        conn.commit()

    cur.close()
    conn.close()
    if resume:
        log(f"Done. Inserted {total} new chunks (skipped {skipped} already-ingested PDFs).")
    else:
        log(f"Done. Inserted {total} chunks.")

if __name__ == "__main__":
    main()
