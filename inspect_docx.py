import os
import sys
from pathlib import Path

backend_dir = Path(r"D:\test-case-gendration\healthcare-nl-testgen\backend")
sys.path.insert(0, str(backend_dir))

# pyrefly: ignore [missing-import]
from app.services.cognos_docx_parser import parse_cognos_docx

def inspect():
    docx_path = Path(r"D:\test-case-gendration\healthcare-nl-testgen\Report Definition – OPR.docx")
    doc = parse_cognos_docx(docx_path)
    
    print(f"Total Sections: {len(doc.sections)}")
    for i, sec in enumerate(doc.sections):
        print(f"\n--- Section {i}: {sec.name} (Page ~{sec.estimated_page}) ---")
        print(f"Paragraphs: {len(sec.paragraphs)}")
        print(f"Checkboxes: {len(sec.checkboxes)}")
        print(f"Tables: {len(sec.tables)}")
        
        for j, t in enumerate(sec.tables):
            print(f"  Table {j} rows: {len(t)}")
            for row in t:
                # Truncate row for display
                print(f"    {row[:3]}")

if __name__ == "__main__":
    inspect()
