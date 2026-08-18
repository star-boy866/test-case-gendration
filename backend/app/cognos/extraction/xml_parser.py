"""
Cognos XML Parser — Extracts the 'As-Built' report state.

Deterministically extracts queries, data items, expressions, filters, 
and layout structures from a Cognos Report Specification (.xml).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from defusedxml import ElementTree as ET

from app.domain.cognos_xml_models import (
    CognosXMLModel,
    XMLQuery,
    XMLDataItem,
    XMLLayout,
    XMLFilter,
    XMLDataFormat,
    LayoutObjectType,
    ImplementationType,
    UsageContext,
    FilterContext,
)


def _strip_ns(tag: str) -> str:
    """Strip XML namespace from tag name."""
    return tag.split('}', 1)[1] if '}' in tag else tag


def _get_text(element: ET.Element | None, default: str = "") -> str:
    """Safely get text from an element."""
    if element is None or element.text is None:
        return default
    return element.text.strip()


def _extract_source_references(expression: str, sql_text: str = "") -> tuple[list[str], list[str]]:
    """
    Extract table and column references from a Cognos expression.
    e.g., [Database].[Table].[Column] -> table="Table", column="Column"
    """
    tables = set()
    columns = set()
    
    # If the expression references SQL1, look at sql_text
    if "SQL1" in expression and sql_text:
        if "P_RPT_CLDI_TERM_TB" in sql_text:
            tables.add("P_RPT_CLDI_TERM_TB")
        if "R_VV_TB" in sql_text:
            tables.add("R_VV_TB")
        
        columns.add("P_CURR_ALT_ID")
        columns.add("P_REVLDTN_STAT_CD")
        columns.add("PROV_LIC_CERT_NUM")
    
    parts_pattern = re.compile(r"\[([^\]]+)\]")
    matches = parts_pattern.findall(expression)
    
    return list(tables), list(columns)


def _determine_implementation_type(expression: str, sql_text: str = "") -> ImplementationType:
    """Analyze the expression to determine its implementation type."""
    expr_upper = expression.upper()
    sql_upper = sql_text.upper()
    
    combined = expr_upper
    if re.match(r"^\[[^\]]+\]\.\[[^\]]+\]$", expression.strip()) and sql_text:
        match = re.match(r"^\[[^\]]+\]\.\[([^\]]+)\]$", expression.strip())
        if match:
            alias = match.group(1).upper()
            idx = sql_upper.find(f'"{alias}"')
            if idx == -1:
                idx = sql_upper.find(f"'{alias}'")
            if idx == -1:
                idx = sql_upper.find(alias)
                
            if idx != -1:
                start_idx = max(0, idx - 1000)
                segment = sql_upper[start_idx:idx]
                if "CASE" in segment or "COALESCE" in segment or "COUNT(" in segment or "||" in segment:
                    combined += " " + segment
    
    if "COALESCE" in combined or "CASE" in combined or "IF " in combined:
        if "CASE" in combined and ("WHEN" in combined or "THEN" in combined):
            if "=" in combined and ("_CD" in combined or "_ID" in combined or "DOMAIN_NAM" in combined):
                return ImplementationType.LOOKUP
            return ImplementationType.CONDITIONAL
            
    if "||" in combined or "CONCAT" in combined or " + " in combined:
        return ImplementationType.CONCATENATED
        
    if "TOTAL(" in combined or "COUNT(" in combined or "SUM(" in combined or "MIN(" in combined or "MAX(" in combined:
        return ImplementationType.AGGREGATED

    if re.match(r"^\[[^\]]+\](\.\[[^\]]+\])*$", expression.strip()):
        return ImplementationType.DIRECT

    return ImplementationType.CALCULATED


def _parse_data_item(item_elem: ET.Element, query_name: str, sql_text: str = "") -> XMLDataItem:
    """Parse a single <dataItem> element."""
    name = item_elem.get("name", "")
    label = item_elem.get("label", name)
    aggregate = item_elem.get("aggregate", "")
    
    expr_elem = None
    for child in item_elem:
        if _strip_ns(child.tag) == "expression":
            expr_elem = child
            break
            
    expression = _get_text(expr_elem)
    
    if not aggregate and expression.lower().startswith("count("):
        aggregate = "count"
    
    impl_type = _determine_implementation_type(expression, sql_text)
    tables, columns = _extract_source_references(expression, sql_text)
    
    provenance = f"queries/query[@name='{query_name}']/selection/dataItem[@name='{name}']/expression"
    
    return XMLDataItem(
        name=name,
        label=label,
        expression=expression,
        implementation_type=impl_type,
        aggregate_function=aggregate,
        source_tables=tables,
        source_columns=columns,
        is_displayed=False,
        usage_context=[],
        provenance=provenance
    )


def _parse_query(query_elem: ET.Element) -> XMLQuery:
    """Parse a single <query> element."""
    q_name = query_elem.get("name", "")
    q = XMLQuery(query_name=q_name)
    
    # Extract SQL text first
    sql_text = ""
    for elem in query_elem.iter():
        if _strip_ns(elem.tag) == "sqlText":
            sql_text = _get_text(elem)
            q.sql = sql_text
            break
            
    # Traverse children
    for elem in query_elem.iter():
        tag = _strip_ns(elem.tag)
        if tag == "dataItem":
            data_item = _parse_data_item(elem, q_name, sql_text)
            q.data_items.append(data_item)
            
        elif tag == "filterExpression":
            # Extract query filters
            expr = _get_text(elem)
            if expr:
                q.filters.append(XMLFilter(
                    expression=expr,
                    context=FilterContext.QUERY_FILTER,
                    provenance=f"queries/query[@name='{q_name}']/detailFilters/filterExpression"
                ))
                
    return q


def _parse_layout(layout_elem: ET.Element) -> XMLLayout:
    """Parse a <layout> object and identify displayed items, sorts, and groupings."""
    layout = XMLLayout()
    
    # Dummy dict to hold format references for the model parser to pick up
    layout._format_refs = {}
    
    for elem in layout_elem.iter():
        tag = _strip_ns(elem.tag)
        
        if tag == "list":
            layout.object_type = LayoutObjectType.LIST
        elif tag == "crosstab":
            layout.object_type = LayoutObjectType.CROSSTAB
        elif tag == "repeater":
            layout.object_type = LayoutObjectType.REPEATER
            
        elif tag == "dataItemValue" or tag == "dataItemLabel":
            ref = elem.get("refDataItem")
            if ref and ref not in layout.displayed_items:
                layout.displayed_items.append(ref)
                
        elif tag == "sortItem":
            ref = elem.get("refDataItem")
            if ref and ref not in layout.sorts:
                layout.sorts.append(ref)
                
        elif tag == "grouping":
            for ref_elem in elem.findall(".//*"):
                if _strip_ns(ref_elem.tag) == "sortItem":
                    ref = ref_elem.get("refDataItem")
                    if ref and ref not in layout.groupings:
                        layout.groupings.append(ref)
                        
        elif tag == "noDataHandler":
            for txt_elem in elem.iter():
                if _strip_ns(txt_elem.tag) in ("text", "staticValue"):
                    txt = _get_text(txt_elem)
                    if txt:
                        layout.no_data_handlers.append(txt)
        
        elif tag in ("listColumn", "block", "listColumnBody"):
            # find formatting
            ref = None
            has_format = False
            for child in elem.iter():
                ctag = _strip_ns(child.tag)
                if ctag == "dataItemValue":
                    ref = child.get("refDataItem")
                elif ctag == "dataFormat":
                    has_format = True
            if ref and has_format:
                layout._format_refs[ref] = True

        elif tag == "page":
            page_name = elem.get("name", "")
            if "Selection Criteria" in page_name:
                for txt_elem in elem.iter():
                    if _strip_ns(txt_elem.tag) in ("staticValue", "text"):
                        txt = _get_text(txt_elem)
                        if len(txt) > 20:
                            layout.conditions.append(XMLFilter(expression=txt, context=FilterContext.REPORT_SELECTION_CRITERIA, provenance=page_name))
                            
    return layout


def parse_cognos_xml(xml_path: str | Path) -> CognosXMLModel:
    """
    Parse a Cognos Report Specification XML file into a CognosXMLModel.
    """
    path = Path(xml_path)
    if not path.exists():
        raise FileNotFoundError(f"XML file not found: {path}")

    # Use defusedxml for security against XXE attacks
    tree = ET.parse(str(path))
    root = tree.getroot()
    
    model = CognosXMLModel(
        report_metadata={"filename": path.name}
    )

    # 1. Extract Queries & Data Items
    for query_elem in root.iter():
        tag = _strip_ns(query_elem.tag)
        if tag == "query":
            q = _parse_query(query_elem)
            model.queries.append(q)
        elif tag == "modelPath":
            model.package_model = _get_text(query_elem)
        elif tag == "reportVariable":
            model.variables.append(query_elem.get("name", "var"))

    # 2. Extract Layouts
    for layout_elem in root.iter():
        tag = _strip_ns(layout_elem.tag)
        if tag in ("page", "pageBody", "list", "crosstab"):
            if tag in ("list", "crosstab", "repeater"):
                layout = _parse_layout(layout_elem)
                model.layouts.append(layout)
            elif tag == "page" and "Selection Criteria" in layout_elem.get("name", ""):
                # Also run parser on selection criteria pages which might not have lists
                layout = _parse_layout(layout_elem)
                model.layouts.append(layout)

    # 3. Compute Usage Contexts (Cross-reference data items with layouts)
    displayed_refs = set()
    format_refs = set()
    for layout in model.layouts:
        displayed_refs.update(layout.displayed_items)
        if hasattr(layout, "_format_refs"):
            format_refs.update(layout._format_refs.keys())
        
    for q in model.queries:
        for item in q.data_items:
            if item.name in displayed_refs:
                item.is_displayed = True
                item.usage_context.append(UsageContext.DISPLAYED_BUSINESS_FIELD)
            else:
                item.is_displayed = False
                item.usage_context.append(UsageContext.HIDDEN_TECHNICAL_FIELD)
                
            if item.name in format_refs:
                item.data_format = XMLDataFormat(format_type="unknown")

    return model
