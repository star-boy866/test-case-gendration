import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"d:\test-case-gendration\healthcare-nl-testgen\backend").absolute()))

from app.services.canonical_parser import parse_canonical_docx

def dump():
    docx_path = Path(r"d:\test-case-gendration\healthcare-nl-testgen\backend\tests\fixtures\golden_sources\CR 18175 PRV-INT-027 UT DOCUMENT 1.docx")
    doc = parse_canonical_docx(docx_path)
    
    print(f"Total paragraphs: {len(doc.paragraphs)}")
    for i, p in enumerate(doc.paragraphs):
        if len(p) > 5:
            print(f"P {i}: {p[:100]}")

if __name__ == "__main__":
    dump()
