"""
DOCX EMF/WMF Image Converter Utility.
Converts embedded EMF/WMF vector images in DOCX archives to PNG format
so that browser-based renderers (such as docx-preview in Playwright) can
display them with full fidelity.
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Union
from PIL import Image


def convert_docx_emf_to_png(docx_input: Union[str, Path, bytes]) -> bytes:
    """
    Inspects a DOCX file or bytes for .emf / .wmf images.
    If found, converts them to .png and updates relationships and [Content_Types].xml.
    Returns the modified DOCX bytes (or original bytes if no EMF/WMF images exist).
    """
    if isinstance(docx_input, (str, Path)):
        with open(docx_input, "rb") as f:
            raw_bytes = f.read()
    else:
        raw_bytes = docx_input

    in_zip = zipfile.ZipFile(io.BytesIO(raw_bytes), "r")
    
    # Check if any EMF/WMF files exist
    emf_files = [n for n in in_zip.namelist() if n.lower().endswith((".emf", ".wmf"))]
    if not emf_files:
        return raw_bytes

    out_buf = io.BytesIO()
    out_zip = zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED)
    emf_replacements = {}

    for name in emf_files:
        data = in_zip.read(name)
        try:
            im = Image.open(io.BytesIO(data))
            png_io = io.BytesIO()
            im.save(png_io, "PNG")
            png_bytes = png_io.getvalue()
            new_name = re.sub(r"\.(emf|wmf)$", ".png", name, flags=re.IGNORECASE)
            emf_replacements[name] = (new_name, png_bytes)
        except Exception:
            # If conversion fails, keep original
            pass

    if not emf_replacements:
        return raw_bytes

    for item in in_zip.infolist():
        data = in_zip.read(item.filename)

        if item.filename in emf_replacements:
            new_name, png_bytes = emf_replacements[item.filename]
            out_zip.writestr(new_name, png_bytes)
            continue

        if item.filename.endswith(".rels"):
            try:
                root = ET.fromstring(data)
                modified = False
                for rel in root:
                    target = rel.attrib.get("Target", "")
                    for old_name, (new_name, _) in emf_replacements.items():
                        old_target = old_name.replace("word/", "")
                        new_target = new_name.replace("word/", "")
                        if target == old_target or target.endswith(old_target):
                            rel.attrib["Target"] = target.replace(old_target, new_target)
                            modified = True
                if modified:
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            except Exception:
                pass

        elif item.filename == "[Content_Types].xml":
            try:
                root = ET.fromstring(data)
                has_png = any(
                    elem.tag.endswith("Default") and elem.attrib.get("Extension", "").lower() == "png"
                    for elem in root
                )
                if not has_png:
                    ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
                    default_tag = f"{ns}Default"
                    new_default = ET.Element(default_tag, {"Extension": "png", "ContentType": "image/png"})
                    root.append(new_default)
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            except Exception:
                pass

        out_zip.writestr(item.filename, data)

    out_zip.close()
    return out_buf.getvalue()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        src = sys.argv[1]
        dst = sys.argv[2]
        converted = convert_docx_emf_to_png(src)
        with open(dst, "wb") as f:
            f.write(converted)
        print(f"Converted {src} -> {dst}")
    elif len(sys.argv) > 1:
        src = sys.argv[1]
        converted = convert_docx_emf_to_png(src)
        sys.stdout.buffer.write(converted)
