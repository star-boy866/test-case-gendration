import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Set
from PIL import Image, ImageDraw, ImageFont

from app.domain.cognos_test_case import EvidenceReference
from app.cognos.schema.nh_mmis_dsd_models import NhMmisDsd
from app.domain.cognos_requirement import RequirementSet

logger = logging.getLogger(__name__)

@dataclass
class EvidenceTarget:
    """Target context for rendering a semantic evidence proof."""
    methodology: str
    section_override: Optional[str] = None
    target_labels: Set[str] = field(default_factory=set)
    source_column: Optional[str] = None
    test_case_id: str = ""

class DSDEvidenceRenderer:
    """
    Phase 10.8I: Generic DSD Evidence Renderer
    Produces a clean, semantic proof image directly from the NhMmisDsd model,
    eliminating the need for any OS-level DOCX or Word application dependencies.
    """
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load fonts
        try:
            self.font_large = ImageFont.truetype("arial.ttf", 22)
            self.font_title = ImageFont.truetype("arialbd.ttf", 18)
            self.font_header = ImageFont.truetype("arialbd.ttf", 14)
            self.font_body = ImageFont.truetype("arial.ttf", 14)
        except Exception:
            try:
                # Secondary fallback for Linux/Docker environments if testing there later
                self.font_large = ImageFont.truetype("DejaVuSans.ttf", 22)
                self.font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
                self.font_header = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
                self.font_body = ImageFont.truetype("DejaVuSans.ttf", 14)
            except Exception:
                self.font_large = ImageFont.load_default()
                self.font_title = ImageFont.load_default()
                self.font_header = ImageFont.load_default()
                self.font_body = ImageFont.load_default()
            
    def render(
        self, 
        target: EvidenceTarget, 
        dsd: NhMmisDsd, 
        req_set: RequirementSet
    ) -> Optional[EvidenceReference]:
        """
        Renders the evidence target into a PNG image and returns the reference.
        Never throws an error; returns None on failure.
        """
        try:
            if not target.methodology:
                return None
                
            img_name = f"proof_{target.test_case_id}.png" if target.test_case_id else f"proof_{hash(str(target))}.png"
            img_path = self.output_dir / img_name
            
            section_name, rows, highlights, headers, source_page = self._extract_semantic_data(target, dsd)
            
            self._draw_evidence_card(target, dsd, section_name, source_page, headers, rows, highlights, img_path)
            
            final_section = section_name
            if source_page:
                final_section = f"Page {source_page} • {section_name}"
                
            return EvidenceReference(
                evidence_type="DSD_SEMANTIC_PROOF",
                section=final_section,
                description=f"Semantic evidence for {target.test_case_id}",
                snapshot_path=str(img_path.absolute()),
                document_name=dsd.report_definition.source_document if dsd.report_definition else "DSD"
            )
                
        except Exception as e:
            logger.warning(f"DSDEvidenceRenderer generation failed for {target.test_case_id}: {e}")
            return None

    def _extract_semantic_data(self, target: EvidenceTarget, dsd: NhMmisDsd):
        """Extracts the relevant headers, rows, and highlighted indices from the DSD."""
        methodology = target.methodology
        rows = []
        highlights = []
        headers = []
        section_name = target.section_override or "Report Evidence"
        source_page = None

        if methodology in ("LABEL_VALIDATION", "LAYOUT_VALIDATION"):
            section_name = "Report Layout"
            if dsd.layout: source_page = dsd.layout.source_page
            headers = ["Business Label", "Source Column", "Processing Rule"]
            valid_rows = [r for r in dsd.report_specification if r.business_label and r.business_label.strip()]
            for idx, row in enumerate(valid_rows):
                rows.append([row.business_label, row.source_column, row.processing_rules])
                if row.business_label in target.target_labels:
                    highlights.append(idx)
                    
        elif methodology == "SORT_VALIDATION":
            section_name = "Sorts"
            if dsd.sorts and len(dsd.sorts) > 0: source_page = dsd.sorts[0].source_page
            headers = ["Sort By", "Direction"]
            valid_sorts = [s for s in dsd.sorts if s.sort_by and s.sort_by.strip()]
            for idx, s in enumerate(valid_sorts):
                rows.append([s.sort_by, s.direction])
                if s.sort_by in target.target_labels or (target.source_column and target.source_column in s.sort_by):
                    highlights.append(idx)
                    
        elif methodology == "DATE_FORMAT_VALIDATION":
            section_name = "Report Specification"
            if dsd.report_specification and len(dsd.report_specification) > 0: source_page = dsd.report_specification[0].source_page
            headers = ["Business Label", "Processing Rule"]
            valid_rows = [r for r in dsd.report_specification if r.business_label and r.business_label.strip()]
            for idx, row in enumerate(valid_rows):
                if "date" in (row.processing_rules or "").lower() or "mm/" in (row.processing_rules or "").lower() or row.business_label in target.target_labels:
                    rows.append([row.business_label, row.processing_rules])
                    if row.business_label in target.target_labels or (target.source_column and target.source_column in row.business_label):
                        highlights.append(len(rows) - 1)
                        
        elif methodology == "DB_REPORT_DATA_VALIDATION":
            section_name = "Report Specification"
            if dsd.report_specification and len(dsd.report_specification) > 0: source_page = dsd.report_specification[0].source_page
            headers = ["Business Label", "Source Table", "Source Column", "Processing Rule"]
            valid_rows = [r for r in dsd.report_specification if r.business_label and r.business_label.strip()]
            for idx, row in enumerate(valid_rows):
                rows.append([row.business_label, row.source_table, row.source_column, row.processing_rules])
                if row.business_label in target.target_labels:
                    highlights.append(len(rows) - 1)
                    
        elif methodology == "CONTROL_BREAK_VALIDATION":
            section_name = "Control Breaks"
            if dsd.control_breaks and len(dsd.control_breaks) > 0: source_page = dsd.control_breaks[0].source_page
            headers = ["Control Break", "Level"]
            valid_cbs = [cb for cb in dsd.control_breaks if cb.control_break and cb.control_break.strip()]
            for idx, cb in enumerate(valid_cbs):
                rows.append([cb.control_break, cb.level])
                if target.source_column and target.source_column in cb.control_break:
                    highlights.append(idx)
                    
        elif methodology == "DB_COUNT_VALIDATION":
            section_name = "Counts & Totals"
            if dsd.counts and len(dsd.counts) > 0: source_page = dsd.counts[0].source_page
            elif dsd.totals and len(dsd.totals) > 0: source_page = dsd.totals[0].source_page
            headers = ["Type", "Field", "Level"]
            for idx, c in enumerate(dsd.counts):
                rows.append(["Count", c.count, c.level])
            for idx, t in enumerate(dsd.totals):
                rows.append(["Total", t.total, t.level])
                
        else:
            section_name = f"DSD Context: {methodology}"
            headers = ["Context", "Value"]
            rows = [["Methodology", methodology], ["Target Column", target.source_column or "N/A"]]
            if dsd.report_definition: source_page = dsd.report_definition.source_page
            
        return section_name, rows, highlights, headers, source_page

    def _draw_evidence_card(
        self, 
        target: EvidenceTarget, 
        dsd: NhMmisDsd, 
        section_name: str, 
        source_page: Optional[int],
        headers: List[str], 
        rows: List[List[str]], 
        highlights: List[int],
        img_path: Path
    ):
        """Draws the visual PNG evidence card matching the layout requested by the user."""
        
        # Calculate image dimensions based on content
        width = 1200
        # Estimate height: Header ~180px, Row ~40px, Padding ~50px
        est_height = 250 + (len(rows) * 45)
        if est_height < 600: est_height = 600
        
        img = Image.new('RGB', (width, est_height), color=(250, 252, 255))
        draw = ImageDraw.Draw(img)
        
        # Draw Main Outer Border
        draw.rectangle([10, 10, width - 10, est_height - 10], outline=(200, 200, 200), width=2)
        
        # Draw Card Header Banner
        draw.rectangle([12, 12, width - 12, 80], fill=(235, 240, 250))
        draw.line([(12, 80), (width - 12, 80)], fill=(200, 200, 200), width=2)
        
        title_text = section_name.upper()
        if source_page:
            title_text = f"PAGE {source_page} • {title_text}"
            
        draw.text((30, 20), title_text, font=self.font_large, fill=(10, 30, 100))
        
        rid = dsd.report_definition.client_report_id if dsd.report_definition else "N/A"
        rtitle = dsd.report_definition.report_title if dsd.report_definition else "N/A"
        dept = dsd.report_definition.client_division_department if dsd.report_definition else "N/A"
        
        draw.text((30, 50), f"{rid}  |  {rtitle}", font=self.font_title, fill=(50, 50, 50))
        
        # Draw Metadata
        y = 110
        draw.text((30, y), f"Report ID: {rid}", font=self.font_header, fill=(50, 50, 50))
        draw.text((300, y), f"Department: {dept}", font=self.font_header, fill=(50, 50, 50))
        y += 40
        
        # Draw Table Line
        draw.line([(30, y), (width - 30, y)], fill=(200, 200, 200), width=1)
        y += 20
        
        if not rows:
            draw.text((30, y), "No relevant semantic data populated in this section.", font=self.font_body, fill=(150, 0, 0))
            img.save(img_path)
            return
            
        # Dynamic Column Widths
        col_widths = []
        for i in range(len(headers)):
            max_w = draw.textlength(headers[i], font=self.font_header)
            for row in rows:
                if i < len(row):
                    w = draw.textlength(str(row[i]), font=self.font_body)
                    if w > max_w: max_w = w
            col_widths.append(int(max_w) + 60) # Padding
            
        # Draw Headers
        x_start = 30
        for i, h in enumerate(headers):
            x = x_start + sum(col_widths[:i])
            draw.text((x, y), h, font=self.font_header, fill=(0, 0, 0))
        y += 30
        
        draw.line([(30, y), (width - 30, y)], fill=(220, 220, 220), width=1)
        y += 10
        
        # Draw Rows
        for r_idx, row in enumerate(rows):
            row_height = 40
            if r_idx in highlights:
                # Highlight Box
                draw.rectangle(
                    [x_start - 5, y - 5, x_start + sum(col_widths) - 20, y + 25], 
                    fill=(255, 250, 200), 
                    outline=(230, 200, 100),
                    width=1
                )
                
            for c_idx, cell in enumerate(row):
                x = x_start + sum(col_widths[:c_idx])
                text = str(cell)
                if len(text) > 80: text = text[:77] + "..."
                
                # Make highlighted text bold visually by using font_header
                use_font = self.font_header if r_idx in highlights else self.font_body
                draw.text((x, y), text, font=use_font, fill=(10, 10, 10))
                
            y += row_height
            
        img.save(img_path)
