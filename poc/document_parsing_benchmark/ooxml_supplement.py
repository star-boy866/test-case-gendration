import zipfile
import re
from typing import Dict, List, Any
import xml.etree.ElementTree as ET

namespaces = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
    'w15': 'http://schemas.microsoft.com/office/word/2012/wordml'
}

def extract_ooxml_features(docx_path: str) -> Dict[str, Any]:
    """
    Extracts raw OOXML features from a docx file.
    Returns:
    - comments: list of dicts with id, author, text
    - checkboxes: dict mapping location to boolean state
    """
    results = {
        'comments': [],
        'checkboxes': []
    }
    
    try:
        with zipfile.ZipFile(docx_path, 'r') as docx_zip:
            # 1. Extract Comments
            if 'word/comments.xml' in docx_zip.namelist():
                comments_xml = docx_zip.read('word/comments.xml')
                root = ET.fromstring(comments_xml)
                for comment in root.findall('.//w:comment', namespaces):
                    c_id = comment.get(f'{{{namespaces["w"]}}}id')
                    author = comment.get(f'{{{namespaces["w"]}}}author', 'Unknown')
                    texts = []
                    for t in comment.findall('.//w:t', namespaces):
                        if t.text:
                            texts.append(t.text)
                    results['comments'].append({
                        'id': c_id,
                        'author': author,
                        'text': ''.join(texts)
                    })
            
            # 2. Extract Checkboxes from document.xml
            if 'word/document.xml' in docx_zip.namelist():
                doc_xml = docx_zip.read('word/document.xml')
                root = ET.fromstring(doc_xml)
                
                # We'll just find all checkboxes and their states.
                # Word can use form fields or content controls for checkboxes.
                
                # Check for legacy form fields (ffData)
                for ffdata in root.findall('.//w:ffData', namespaces):
                    name_el = ffdata.find('w:name', namespaces)
                    cb_el = ffdata.find('w:checkBox', namespaces)
                    if cb_el is not None:
                        checked_el = cb_el.find('w:checked', namespaces)
                        default_el = cb_el.find('w:default', namespaces)
                        is_checked = False
                        if checked_el is not None:
                            val = checked_el.get(f'{{{namespaces["w"]}}}val')
                            is_checked = (val in ['1', 'true', 'True'])
                        elif default_el is not None:
                            val = default_el.get(f'{{{namespaces["w"]}}}val')
                            is_checked = (val in ['1', 'true', 'True'])
                        
                        name = name_el.get(f'{{{namespaces["w"]}}}val') if name_el is not None else 'unknown'
                        results['checkboxes'].append({'type': 'legacy', 'name': name, 'checked': is_checked})
                
                # Check for content control checkboxes (w14:checkbox)
                for sdt in root.findall('.//w:sdt', namespaces):
                    cb = sdt.find('.//w14:checkbox', namespaces)
                    if cb is not None:
                        checked_el = cb.find('w14:checked', namespaces)
                        is_checked = False
                        if checked_el is not None:
                            val = checked_el.get(f'{{{namespaces["w14"]}}}val')
                            is_checked = (val in ['1', 'true', 'True'])
                        
                        # Try to find a label or text nearby
                        alias_el = sdt.find('.//w:alias', namespaces)
                        name = alias_el.get(f'{{{namespaces["w"]}}}val') if alias_el is not None else 'content_control'
                        results['checkboxes'].append({'type': 'content_control', 'name': name, 'checked': is_checked})
                        
    except Exception as e:
        print(f"Error extracting OOXML: {e}")
        
    return results

if __name__ == '__main__':
    import sys
    import json
    if len(sys.argv) > 1:
        res = extract_ooxml_features(sys.argv[1])
        print(json.dumps(res, indent=2))
