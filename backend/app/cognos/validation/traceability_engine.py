import re
from typing import Optional

from app.domain.cognos_models import ReportDefinition, ReportField
from app.domain.cognos_requirement import RequirementSet
from app.domain.cognos_xml_models import CognosXMLModel, XMLDataItem, ImplementationType, UsageContext
from app.domain.traceability_models import (
    TraceabilityResult,
    FieldTrace,
    SortTrace,
    SelectionCriteriaTrace,
    LayoutTrace,
    XMLOnlyItem,
    MappingStatus,
    ReviewStatus,
    MatchStrategy
)

class TraceabilityEngine:
    """
    Connects the authoritative DSD (ReportDefinition) to the XML (CognosXMLModel).
    The DSD is the single source of truth for test discovery.
    This engine ONLY performs evidence-based traceability analysis.
    """
    def __init__(self, dsd: ReportDefinition, req_set: RequirementSet, xml: CognosXMLModel):
        self.dsd = dsd
        self.req_set = req_set
        self.xml = xml
        
        self.xml_items_by_name: dict[str, XMLDataItem] = {}
        self.xml_items_by_label: dict[str, XMLDataItem] = {}
        for q in self.xml.queries:
            for item in q.data_items:
                self.xml_items_by_name[item.name.lower()] = item
                self.xml_items_by_label[item.label.lower()] = item

    def run(self) -> TraceabilityResult:
        result = TraceabilityResult()
        
        self._trace_fields(result)
        self._trace_sorts(result)
        self._trace_selection_criteria(result)
        self._trace_layout(result)
        self._trace_xml_only_items(result)
        
        return result

    def _normalize(self, s: str) -> str:
        return re.sub(r'[^a-z0-9]', '', s.lower()) if s else ""

    def _match_field(self, dsd_field: ReportField) -> tuple[Optional[XMLDataItem], MatchStrategy, float]:
        # 1. Exact business/display label
        dsd_label = dsd_field.business_label.lower() if dsd_field.business_label else ""
        if dsd_label and dsd_label in self.xml_items_by_label:
            return self.xml_items_by_label[dsd_label], MatchStrategy.EXACT_BUSINESS_LABEL, 1.0
            
        # 2. Exact technical/name match
        dsd_name = dsd_field.field_name.lower() if dsd_field.field_name else ""
        if dsd_name and dsd_name in self.xml_items_by_name:
            return self.xml_items_by_name[dsd_name], MatchStrategy.EXACT_TECHNICAL_NAME, 1.0
            
        # 3. Source-column intersection
        dsd_cols = {c.lower() for c in dsd_field.source_columns}
        if dsd_field.source_column:
            dsd_cols.add(dsd_field.source_column.lower())
            
        if dsd_cols:
            for item in self.xml_items_by_name.values():
                item_cols = {c.lower() for c in item.source_columns}
                if dsd_cols.intersection(item_cols):
                    return item, MatchStrategy.SOURCE_COLUMN, 0.9
                    
        # 4. Normalized alias matching
        dsd_norm = self._normalize(dsd_field.business_label)
        if not dsd_norm:
            dsd_norm = self._normalize(dsd_field.field_name)
            
        if dsd_norm:
            for item in self.xml_items_by_name.values():
                if self._normalize(item.name) == dsd_norm or self._normalize(item.label) == dsd_norm:
                    return item, MatchStrategy.NORMALIZED_ALIAS, 0.8
                
        # 5. Controlled fallback (very loose match)
        if dsd_norm and len(dsd_norm) > 4:
            for item in self.xml_items_by_name.values():
                if dsd_norm in self._normalize(item.name) or dsd_norm in self._normalize(item.label):
                    return item, MatchStrategy.FALLBACK, 0.5

        return None, MatchStrategy.NOT_MATCHED, 0.0

    def _trace_fields(self, result: TraceabilityResult):
        for field in self.dsd.report_fields:
            item, strategy, confidence = self._match_field(field)
            
            if item:
                is_complex = item.implementation_type in (
                    ImplementationType.LOOKUP, 
                    ImplementationType.CALCULATED, 
                    ImplementationType.CONDITIONAL,
                    ImplementationType.CONCATENATED,
                    ImplementationType.FORMATTED,
                    ImplementationType.AGGREGATED
                )
                
                status = MappingStatus.MATCH
                review = ReviewStatus.OK
                
                if confidence < 0.8:
                    review = ReviewStatus.REVIEW_REQUIRED
                    
                result.field_traces.append(FieldTrace(
                    dsd_field_name=field.field_name or field.business_label,
                    xml_data_item_name=item.name,
                    mapping_status=status,
                    review_status=review,
                    implementation_type=item.implementation_type.value if hasattr(item.implementation_type, 'value') else item.implementation_type,
                    transformation_present=is_complex,
                    confidence=confidence,
                    match_strategy=strategy,
                    xml_provenance=item.provenance
                ))
            else:
                result.field_traces.append(FieldTrace(
                    dsd_field_name=field.field_name or field.business_label,
                    mapping_status=MappingStatus.MISSING_IN_XML,
                    review_status=ReviewStatus.REVIEW_REQUIRED,
                    xml_provenance=""
                ))

    def _trace_sorts(self, result: TraceabilityResult):
        xml_sorts = {}
        for l in self.xml.layouts:
            for s in l.sorts:
                xml_sorts[s.lower()] = s
                
        for sort_def in self.dsd.sort_definitions:
            dsd_name = sort_def.field.lower()
            mapped_item = None
            dsd_field = next((f for f in self.dsd.report_fields if f.field_name.lower() == dsd_name or f.business_label.lower() == dsd_name), None)
            
            if dsd_field:
                item, strategy, conf = self._match_field(dsd_field)
                if item:
                    mapped_item = item.name
            else:
                if dsd_name in self.xml_items_by_name:
                    mapped_item = self.xml_items_by_name[dsd_name].name
                    
            if mapped_item and mapped_item.lower() in xml_sorts:
                result.sort_traces.append(SortTrace(
                    dsd_field_name=sort_def.field,
                    dsd_direction=sort_def.direction.value if hasattr(sort_def.direction, 'value') else sort_def.direction,
                    xml_field_name=xml_sorts[mapped_item.lower()],
                    xml_direction="Unknown", 
                    mapping_status=MappingStatus.MATCH,
                    review_status=ReviewStatus.OK
                ))
            else:
                result.sort_traces.append(SortTrace(
                    dsd_field_name=sort_def.field,
                    dsd_direction=sort_def.direction.value if hasattr(sort_def.direction, 'value') else sort_def.direction,
                    mapping_status=MappingStatus.MISSING_IN_XML,
                    review_status=ReviewStatus.REVIEW_REQUIRED
                ))

    def _trace_selection_criteria(self, result: TraceabilityResult):
        xml_filters = []
        for q in self.xml.queries:
            xml_filters.extend(q.filters)
        for l in self.xml.layouts:
            xml_filters.extend(l.conditions)
            
        for crit in self.dsd.selection_criteria:
            matched = False
            for xf in xml_filters:
                if (crit.parameter_name and crit.parameter_name.lower() in xf.expression.lower()) or \
                   (crit.field and crit.field.lower() in xf.expression.lower()) or \
                   (self._normalize(crit.description) and self._normalize(crit.description) in self._normalize(xf.expression)):
                    result.selection_traces.append(SelectionCriteriaTrace(
                        dsd_criterion=crit.field or crit.parameter_name,
                        xml_filter=xf.expression,
                        mapping_status=MappingStatus.MATCH,
                        review_status=ReviewStatus.OK,
                        provenance=xf.provenance
                    ))
                    matched = True
                    break
                    
            if not matched:
                result.selection_traces.append(SelectionCriteriaTrace(
                    dsd_criterion=crit.field or crit.parameter_name,
                    mapping_status=MappingStatus.MISSING_IN_XML,
                    review_status=ReviewStatus.REVIEW_REQUIRED
                ))

    def _trace_layout(self, result: TraceabilityResult):
        dsd_type = self.dsd.layout.presentation_type_str or (self.dsd.layout.presentation_type.value if hasattr(self.dsd.layout.presentation_type, 'value') else str(self.dsd.layout.presentation_type))
        
        if not dsd_type or dsd_type == "UNKNOWN":
            return
            
        xml_layouts = [l.object_type.value if hasattr(l.object_type, 'value') else str(l.object_type) for l in self.xml.layouts]
        
        if any(self._normalize(dsd_type) in self._normalize(x) for x in xml_layouts):
            result.layout_traces.append(LayoutTrace(
                dsd_element=dsd_type,
                xml_object=dsd_type,
                mapping_status=MappingStatus.MATCH,
                review_status=ReviewStatus.OK
            ))
        else:
            result.layout_traces.append(LayoutTrace(
                dsd_element=dsd_type,
                mapping_status=MappingStatus.MISSING_IN_XML,
                review_status=ReviewStatus.REVIEW_REQUIRED
            ))

    def _trace_xml_only_items(self, result: TraceabilityResult):
        mapped_xml_names = set(t.xml_data_item_name for t in result.field_traces if t.mapping_status == MappingStatus.MATCH)
        
        for item in self.xml_items_by_name.values():
            if item.name not in mapped_xml_names:
                item_type = "technical"
                if UsageContext.HIDDEN_TECHNICAL_FIELD in item.usage_context:
                    item_type = "hidden"
                elif item.name in self.xml.variables:
                    item_type = "variable"
                    
                result.implementation_only_items.append(XMLOnlyItem(
                    item_name=item.name,
                    item_type=item_type,
                    provenance=item.provenance
                ))
