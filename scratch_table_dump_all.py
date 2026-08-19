import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"d:\test-case-gendration\healthcare-nl-testgen\backend").absolute()))

from app.services.canonical_parser import parse_canonical_docx

def dump():
    files = [
        "CR 18175 PRV-INT-027 UT DOCUMENT 1.docx",
        "Service Authorization Part E_CR18140_V0.1 1.docx",
        "Report Definition- OPT-TPL-005.docx"
    ]
    for fname in files:
        print(f"\n====================== {fname} ======================")
        docx_path = Path(r"d:\test-case-gendration\healthcare-nl-testgen\backend\tests\fixtures\golden_sources") / fname
        doc = parse_canonical_docx(docx_path)
        print(f"Total tables: {len(doc.tables)}")
        for i, t in enumerate(doc.tables):
            if not t.rows:
                continue
            headers = [c.text.strip().replace("\n", " ") for c in t.rows[0].cells]
            print(f"Table {i} Headers: {headers[:10]}")
            if "business label" in [h.lower() for h in headers] or "field type" in [h.lower() for h in headers] or "report body" in [h.lower() for h in headers]:
                print(f"  -> Report Body Table found! Rows: {len(t.rows)}")
                for j, row in enumerate(t.rows[:5]):
                    texts = [c.text.strip().replace("\n", " ") for c in row.cells]
                    print(f"    Row {j}: {texts[:5]}")

if __name__ == "__main__":
    dump()
