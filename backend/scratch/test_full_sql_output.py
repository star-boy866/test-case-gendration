import sys
sys.path.insert(0, '.')
import re
from app.cognos.pipeline import run_cognos_pipeline
from app.cognos.rules.sql_generator import DeterministicSqlGenerator, _is_template_placeholder
from pathlib import Path

res = run_cognos_pipeline(Path('runs/210/source/source.docx'))
rd = res.report_definition
req_set = res.requirement_set
cases = res.test_suite.test_cases

field_to_col, col_to_table = DeterministicSqlGenerator._build_source_mappings(cases[0], rd, req_set)
raw_criteria = DeterministicSqlGenerator._extract_raw_criteria(cases[0], rd, req_set)

# Test SQL generation logic
seen_cols = set()
col_exprs = []
source_mappings = []
has_lookup = False
lookup_info = {}

primary_table = None

fields_list = []
if rd and rd.report_fields:
    fields_list = [rf for rf in rd.report_fields if not _is_template_placeholder(rf.business_label or rf.field_name)]

if not fields_list:
    dbre_cases = [tc for tc in cases if 'DBRE' in tc.test_case_id]
    fields_list = dbre_cases

for f in fields_list:
    lbl = getattr(f, 'business_label', None) or getattr(f, 'field_name', None) or getattr(f, 'source_field', None) or ""
    col = getattr(f, 'source_column', None) or ""
    tbl = getattr(f, 'source_table', None) or ""
    proc_rule = getattr(f, 'processing_rule', None) or ""

    if not col:
        col = DeterministicSqlGenerator._resolve_column(lbl, field_to_col, tbl or "P_RPT_CLDI_TERM_TB")
    if not tbl and col:
        tbl = col_to_table.get(col.upper(), "P_RPT_CLDI_TERM_TB")

    if not primary_table and tbl and tbl not in ("NOT_DEFINED", "N/A", "Multiple"):
        primary_table = tbl

    if not col or col in seen_cols:
        continue
    seen_cols.add(col)

    alias = re.sub(r'[^A-Za-z0-9_]+', '_', lbl or col).strip('_')
    is_lookup = (
        "valid values" in proc_rule.lower() or
        "code, hyphen" in proc_rule.lower() or
        "code - description" in proc_rule.lower() or
        "r_vv_tb" in proc_rule.lower() or
        col.upper().endswith("_CD") or
        "reval" in lbl.lower()
    )

    if is_lookup:
        has_lookup = True
        lookup_info = {
            "table": "R_VV_TB",
            "col": col,
            "code_col": "R_VV_CD",
            "desc_col": "R_VV_LONG_DESC",
            "domain": col
        }
        col_expr = (
            f"COALESCE(\n"
            f"        CASE\n"
            f"            WHEN t.{col} IS NULL\n"
            f"              OR rv.R_VV_LONG_DESC IS NULL\n"
            f"            THEN NULL\n"
            f"            ELSE t.{col} || '-' || rv.R_VV_LONG_DESC\n"
            f"        END,\n"
            f"        t.{col}\n"
            f"    )                              AS {alias}"
        )
        source_mappings.append({"field": f"{lbl} (Description)", "column": "R_VV_LONG_DESC", "table": "R_VV_TB"})
    else:
        pad = max(1, 30 - len(f"t.{col}"))
        col_expr = f"t.{col}{' ' * pad}AS {alias}"

    col_exprs.append(col_expr)
    source_mappings.append({"field": lbl, "column": col, "table": tbl or primary_table})

if not primary_table:
    primary_table = "P_RPT_CLDI_TERM_TB"

# Build WHERE
where_conditions = []
for crit in raw_criteria:
    cond, mapping, err = DeterministicSqlGenerator._parse_and_bind_criterion(crit, field_to_col, primary_table)
    if cond:
        where_conditions.append(cond)
    if mapping and mapping not in source_mappings:
        source_mappings.append(mapping)

# Build ORDER BY
order_cols = []
for f in fields_list:
    lbl = getattr(f, 'business_label', None) or getattr(f, 'field_name', None) or getattr(f, 'source_field', None) or ""
    col = getattr(f, 'source_column', None) or ""
    alias = re.sub(r'[^A-Za-z0-9_]+', '_', lbl or col).strip('_')
    if alias and alias not in order_cols:
        order_cols.append(alias)

select_str = ",\n\n    ".join(col_exprs)
from_str = f"FROM {primary_table} t"
join_str = ""
if has_lookup:
    join_str = (
        f"\nLEFT JOIN {lookup_info['table']} rv\n"
        f"    ON t.{lookup_info['col']} = rv.{lookup_info['code_col']}\n"
        f"   AND rv.R_VV_DOMAIN_NAM = '{lookup_info['domain']}'"
    )

where_str = ""
if where_conditions:
    where_str = f"\nWHERE\n    " + "\n    AND ".join(where_conditions)

order_str = ""
if order_cols:
    order_str = f"\nORDER BY\n    " + ",\n    ".join(order_cols)

full_sql = f"SELECT\n    {select_str}\n\n{from_str}{join_str}{where_str}{order_str};"
print("Generated Full Report SQL:\n")
print(full_sql)
