"""
AST Builder — Phase 4.

Phase 9 (P1 Remediation): Makes AST validation alias-aware and join-aware via 
SchemaSymbolResolver. Every table/column reference is rigorously validated against 
the canonical Knowledge Base schema, allowing for multi-table references.

Per the Master System Prompt's Compile-then-Execute SQL Logic: the system
must never let an LLM's proposed query structure become SQL directly. This
module is the deterministic gate in between — it takes a Planning Agent's
ScenarioIntent (LLM output, NOT trusted) and the Context Minimizer's
context_slice (Knowledge-Base-derived, TRUSTED) and either:

  - builds a validated AST using ONLY tables/columns/joins that actually
    exist in context_slice, or
  - rejects the intent with explicit reasons, listing exactly which
    table/column/join references couldn't be verified.
"""

from __future__ import annotations

from app.agents.schemas import ScenarioIntent, ValidatedAST

_ALLOWED_OPS = {"=", "!=", "<>", ">", "<", ">=", "<=", "IS NULL", "IS NOT NULL", "IN", "NOT IN", "LIKE"}


def _index_by_lower_name(names: list[str]) -> dict[str, str]:
    """Map lowercased name -> canonical (KB-verified) name."""
    return {n.lower(): n for n in names}


class SchemaSymbolResolver:
    def __init__(self, context_slice: dict):
        self.known_tables = _index_by_lower_name(context_slice.get("candidate_tables", []))
        self.kb_joins = context_slice.get("joins", [])
        
        self.columns_by_table: dict[str, dict[str, str]] = {}
        for col in context_slice.get("columns", []):
            self.columns_by_table.setdefault(col["table_name"], {})[col["column_name"].lower()] = col["column_name"]
            
        self.registry: dict[str, str] = {}
        
    def register_table(self, table_expr: str) -> str:
        parts = table_expr.strip().split()
        if not parts:
            raise ValueError("Empty table expression.")
            
        table_name = parts[0].lower()
        # If an explicit alias is given, keep its original casing. 
        # If no alias, the default alias is the canonical uppercase table name.
        canonical = self.known_tables.get(table_name)
        if not canonical:
            raise ValueError(f"Unknown table '{parts[0]}' in table expression '{table_expr}'.")

        alias_key = parts[-1].lower() if len(parts) > 1 else canonical.lower()
        alias_display = parts[-1] if len(parts) > 1 else canonical
        
        if alias_key in self.registry and self.registry[alias_key][1] != canonical:
            raise ValueError(f"Alias collision: '{alias_display}' used for multiple tables.")
            
        self.registry[alias_key] = (alias_display, canonical)
        return canonical

    def resolve_column(self, col_ref: str) -> str:
        parts = col_ref.split(".", 1)
        if len(parts) == 2:
            prefix, col = parts[0].lower(), parts[1].lower()
            if prefix not in self.registry:
                raise ValueError(f"Unknown alias/table prefix '{parts[0]}' in '{col_ref}'.")
                
            alias_display, canonical_table = self.registry[prefix]
            known_cols = self.columns_by_table.get(canonical_table, {})
            canonical_col = known_cols.get(col)
            
            if not canonical_col:
                raise ValueError(f"Unknown column '{parts[1]}' for alias/table '{parts[0]}' (resolves to '{canonical_table}').")
                
            return f"{alias_display}.{canonical_col}"
            
        else:
            col = parts[0].lower()
            matches = []
            for alias_key, (alias_display, canonical_table) in self.registry.items():
                if col in self.columns_by_table.get(canonical_table, {}):
                    matches.append((alias_display, canonical_table))
                    
            if not matches:
                raise ValueError(f"Unknown column '{parts[0]}' (not found in any referenced table).")
            if len(matches) > 1:
                tables = [m[1] for m in matches]
                raise ValueError(f"Ambiguous column '{parts[0]}' found in multiple referenced tables: {tables}.")
                
            matched_alias_display, matched_canonical_table = matches[0]
            canonical_col = self.columns_by_table[matched_canonical_table][col]
            return f"{matched_alias_display}.{canonical_col}"

    def validate_join(self, from_alias: str, to_alias: str) -> dict:
        from_table_tuple = self.registry.get(from_alias.lower())
        to_table_tuple = self.registry.get(to_alias.lower())
        
        if not from_table_tuple or not to_table_tuple:
            raise ValueError(f"Invalid join references: {from_alias} -> {to_alias} (one or both unknown).")
            
        from_display, from_table = from_table_tuple
        to_display, to_table = to_table_tuple
        
        match = next(
            (
                j for j in self.kb_joins
                if {j["from_table"], j["to_table"]} == {from_table, to_table}
            ),
            None,
        )
        if not match:
            raise ValueError(f"No verified join path exists between '{from_table}' and '{to_table}' in the Knowledge Base.")
            
        if match["from_table"] == from_table:
            on_clause = f"{from_display}.{match['from_column']} = {to_display}.{match['to_column']}"
        else:
            on_clause = f"{to_display}.{match['from_column']} = {from_display}.{match['to_column']}"
            
        return {
            "on": on_clause,
            "join_type": match.get("join_type") or "INNER",
        }


def build_ast(intent: ScenarioIntent, context_slice: dict) -> ValidatedAST:
    reasons: list[str] = []
    resolver = SchemaSymbolResolver(context_slice)
    
    # 1. Register target table
    try:
        from_canonical = resolver.register_table(intent.target_table)
        from_parts = intent.target_table.strip().split()
        from_alias_key = from_parts[-1].lower() if len(from_parts) > 1 else from_canonical.lower()
        if len(from_parts) > 1:
            from_table_expr = f"{from_canonical} {from_parts[-1]}"
        else:
            from_table_expr = from_canonical
    except ValueError as e:
        reasons.append(str(e))
        return ValidatedAST(is_valid=False, rejection_reasons=reasons)
        
    # 2. Register joins
    validated_joins = []
    for joined_table_expr in intent.joins_needed:
        try:
            to_canonical = resolver.register_table(joined_table_expr)
            to_parts = joined_table_expr.strip().split()
            to_alias_key = to_parts[-1].lower() if len(to_parts) > 1 else to_canonical.lower()
            
            join_info = resolver.validate_join(from_alias_key, to_alias_key)
            
            if len(to_parts) > 1:
                final_table_expr = f"{to_canonical} {to_parts[-1]}"
            else:
                final_table_expr = to_canonical
                
            validated_joins.append({
                "table": final_table_expr,
                "on": join_info["on"],
                "join_type": join_info["join_type"]
            })
        except ValueError as e:
            reasons.append(str(e))
            
    if reasons:
        return ValidatedAST(is_valid=False, rejection_reasons=reasons)

    # 3. Validate target_columns
    select: list[str] = []
    for col in intent.target_columns:
        try:
            select.append(resolver.resolve_column(col))
        except ValueError as e:
            reasons.append(str(e))
            
    if not intent.target_columns:
        reasons.append("intent proposed no target_columns to select — cannot build a meaningful query.")

    # 4. Validate filters
    where: list[dict] = []
    for f in intent.filters:
        col = f.get("column", "")
        op = (f.get("op") or "=").upper()
        value = f.get("value", "")
        
        if op not in _ALLOWED_OPS:
            reasons.append(f"filter operator '{op}' is not an allowed comparison operator.")
            continue
            
        try:
            where.append({"column": resolver.resolve_column(col), "op": op, "value": value})
        except ValueError as e:
            reasons.append(str(e))
            
    # 5. Validate group_by
    group_by: list[str] = []
    for col in intent.group_by:
        try:
            group_by.append(resolver.resolve_column(col))
        except ValueError as e:
            reasons.append(str(e))

    # 6. Validate order_by
    order_by: list[str] = []
    for col in intent.order_by:
        try:
            order_by.append(resolver.resolve_column(col))
        except ValueError as e:
            reasons.append(str(e))
            
    # 7. Validate having
    having: list[dict] = []
    for f in intent.having:
        col = f.get("column", "")
        op = (f.get("op") or "=").upper()
        value = f.get("value", "")
        
        if op not in _ALLOWED_OPS:
            reasons.append(f"filter operator '{op}' is not an allowed comparison operator.")
            continue
            
        try:
            having.append({"column": resolver.resolve_column(col), "op": op, "value": value})
        except ValueError as e:
            reasons.append(str(e))

    if reasons:
        return ValidatedAST(is_valid=False, rejection_reasons=reasons)

    return ValidatedAST(
        is_valid=True,
        select=select,
        from_table=from_table_expr,
        joins=validated_joins,
        where=where,
        group_by=group_by,
        order_by=order_by,
        having=having,
        rejection_reasons=[],
    )
