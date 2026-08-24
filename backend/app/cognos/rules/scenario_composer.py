"""
Scenario Composer - Composes CognosTestCase based on canonical methodology patterns.
"""
from __future__ import annotations
from typing import List, Any

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_test_case import CognosTestCase, TestCasePriority, EvidenceRequirement, EvidenceReference
from app.cognos.rules.scenario_patterns import ApplicablePattern, MethodologyPattern


class ScenarioComposer:
    def __init__(self, rd: ReportDefinition, base_precondition: str):
        self.rd = rd
        self.base_precondition = base_precondition

    def compose(self, applicable_patterns: List[ApplicablePattern] | Any) -> List[CognosTestCase]:
        from app.cognos.rules.sql_generator import DeterministicSqlGenerator
        cases = []
        pattern_list = applicable_patterns.generated if hasattr(applicable_patterns, 'generated') else applicable_patterns
        for pattern in pattern_list:
            cases.extend(self._compose_pattern(pattern))
        DeterministicSqlGenerator.enrich_test_cases(cases, self.rd)
        return cases

    def _compose_pattern(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        builder_map = {
            MethodologyPattern.LAYOUT_VALIDATION: self._build_layout,
            MethodologyPattern.LABEL_VALIDATION: self._build_label,
            MethodologyPattern.SORT_VALIDATION: self._build_sort,
            MethodologyPattern.SCRIPT_OUTPUT_VALIDATION: self._build_script_output,
            MethodologyPattern.REPORT_NAME_DESCRIPTION_VALIDATION: self._build_report_name,
            MethodologyPattern.NO_DATA_VALIDATION: self._build_no_data,
            MethodologyPattern.DATE_FORMAT_VALIDATION: self._build_date_format,
            MethodologyPattern.CONTROL_BREAK_VALIDATION: self._build_control_break,
            MethodologyPattern.DB_COUNT_VALIDATION: self._build_db_count,
            MethodologyPattern.DUPLICATE_VALIDATION: self._build_duplicate,
            MethodologyPattern.LOOKUP_VALIDATION: self._build_lookup,
            MethodologyPattern.SCHEDULED_EXECUTION_VALIDATION: self._build_schedule,
            MethodologyPattern.OUTPUT_DELIVERY_VALIDATION: self._build_delivery,
            MethodologyPattern.DB_REPORT_DATA_VALIDATION: self._build_db_report_data,
            MethodologyPattern.REPORT_HEADER_VALIDATION: self._build_report_header,
            MethodologyPattern.REPORT_SECTION_HEADING_VALIDATION: self._build_report_section_heading,
            MethodologyPattern.SPECIAL_PROCESSING_VALIDATION: self._build_special_processing,
            MethodologyPattern.SELECTION_CRITERIA_VALIDATION: self._build_selection_criteria,
        }
        builder = builder_map.get(pattern.pattern)
        if builder:
            return builder(pattern)
        return []

    def _get_common_kwargs(self, pattern: ApplicablePattern) -> dict:
        req_ids = list(set([req.requirement_id for req in pattern.requirements if req.requirement_id]))
        source_doc = self.rd.source_document or ""
        
        evidence_refs = []
        for req in pattern.requirements:
            evidence_refs.extend(getattr(req, "evidence_references", []))
            
        seen = set()
        unique_refs = []
        for sr in evidence_refs:
            key = (sr.page, sr.section, sr.source_text)
            if key not in seen:
                seen.add(key)
                if not sr.snapshot_path:
                    continue
                unique_refs.append(EvidenceReference(
                    evidence_type="DSD_EVIDENCE",
                    document_name=sr.document_name,
                    page_number=sr.page,
                    section=sr.section,
                    source_text=sr.source_text,
                    snapshot_path=sr.snapshot_path,
                    bounding_box=sr.bounding_box,
                    description=f"Evidence from {sr.section} (Page {sr.page})" if sr.page else f"Evidence from {sr.section}"
                ))
        
        return {
            "report_id": self.rd.metadata.report_id or "NOT_DEFINED",
            "report_name": self.rd.metadata.report_title or "NOT_DEFINED",
            "requirement_ids": req_ids,
            "source_document": source_doc,
            "preconditions": self.base_precondition,
            "source_table": "Multiple" if len(set(r.source_table for r in pattern.requirements if r.source_table)) > 1 else next((r.source_table for r in pattern.requirements if r.source_table), "N/A"),
            "source_section": "Report Specification",
            "origin": "DEV_UT_METHODOLOGY",
            "notes": f"Applicability Reason: {pattern.applicable_reason} (Confidence: {pattern.confidence.value})",
            "applicability_reason": pattern.applicable_reason,
            "evidence_references": unique_refs,
        }

    def _format_evidence(self, evidences: List[EvidenceRequirement]) -> dict:
        if not evidences:
            return {"evidence_required": "", "evidence_type": ""}
        
        evidence_required_str = "\n".join([f"- {e.description}: {e.placeholder}" for e in evidences])
        evidence_type_str = evidences[0].evidence_type if evidences else "REPORT"
        
        return {
            "evidence_required": evidence_required_str,
            "evidence_type": evidence_type_str,
            "evidence_requirements": evidences
        }

    def _filter_unique_refs(self, req) -> List:
        unique_refs = []
        seen = set()
        for sr in getattr(req, "evidence_references", []):
            key = (sr.page, sr.section, sr.source_text)
            if key not in seen:
                seen.add(key)
                if not sr.snapshot_path:
                    continue
                unique_refs.append(EvidenceReference(
                    evidence_type="DSD_EVIDENCE",
                    document_name=sr.document_name,
                    page_number=sr.page,
                    section=sr.section,
                    source_text=sr.source_text,
                    snapshot_path=sr.snapshot_path,
                    bounding_box=sr.bounding_box,
                    description=f"Evidence from {sr.section} (Page {sr.page})" if sr.page else f"Evidence from {sr.section}"
                ))
        return unique_refs

    def _build_layout(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="REPORT", description="Report screenshot", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Layout Validation",
            test_case_title=f"Verify layout for {kwargs['report_id']}",
            test_case_description=f"Validated the layout in report {kwargs['report_id']} against the report specification to ensure it is displayed in the correct format.",
            objective=f"Verify the structural layout matches the DSD.",
            test_data="N/A",
            test_steps=(
                f"1. Generate report {kwargs['report_id']}.\n"
                f"2. Compare layout presentation against DSD layout requirements."
            ),
            expected_result="Report layout matches the DSD.",
            priority=TestCasePriority.MEDIUM,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_label(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        base_kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Report screenshot", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        cases = []
        for req in pattern.requirements:
            kwargs = base_kwargs.copy()
            kwargs["requirement_ids"] = [req.requirement_id] if req.requirement_id else []
            kwargs["evidence_references"] = self._filter_unique_refs(req)
            
            field_name = req.business_label or req.field or "NOT_DEFINED"
            tc = CognosTestCase(
                **kwargs,
                category="Label Validation",
                test_case_title=f"Verify label '{field_name}' for {kwargs['report_id']}",
                test_case_description=f"Validated the label name '{field_name}' in report {kwargs['report_id']} against the report specification.",
                objective=f"Verify column and body label '{field_name}'.",
                test_data="N/A",
                test_steps=(
                    f"1. Generate report {kwargs['report_id']}.\n"
                    f"2. Inspect the report labels and column headers.\n"
                    f"3. Verify header '{field_name}' matches the DSD specifications."
                ),
                expected_result=f"The label name '{field_name}' matches the DSD exactly.",
                priority=TestCasePriority.MEDIUM,
                **self._format_evidence(evidences)
            )
            cases.append(tc)

        if not cases:
            tc = CognosTestCase(
                **base_kwargs,
                category="Label Validation",
                test_case_title=f"Verify label names for {base_kwargs['report_id']}",
                test_case_description=f"Validated the label names in report {base_kwargs['report_id']} against the report specification to ensure correct display.",
                objective="Verify column and body labels.",
                test_data="N/A",
                test_steps=(
                    f"1. Generate report {base_kwargs['report_id']}.\n"
                    f"2. Inspect the report labels and column headers.\n"
                    f"3. Verify headers match the DSD specifications."
                ),
                expected_result="The label names match the DSD exactly.",
                priority=TestCasePriority.MEDIUM,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
        return cases

    def _build_sort(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        base_kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="REPORT", description="Report output", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Report screenshot", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        cases = []
        for req in pattern.requirements:
            kwargs = base_kwargs.copy()
            kwargs["requirement_ids"] = [req.requirement_id] if req.requirement_id else []
            kwargs["evidence_references"] = self._filter_unique_refs(req)
            
            field_name = req.business_label or req.field or "NOT_DEFINED"
            tc = CognosTestCase(
                **kwargs,
                category="Sort Validation",
                test_case_title=f"Verify sorting by '{field_name}' for {kwargs['report_id']}",
                test_case_description=f"Validated the sorting by '{field_name}' in report {kwargs['report_id']} against the report specification.",
                objective=f"Verify report data sorting by '{field_name}'.",
                test_data=f"Records with varied sort keys for '{field_name}'.",
                test_steps=(
                    f"1. Generate report {kwargs['report_id']}.\n"
                    f"2. Inspect the ordering of records.\n"
                    f"3. Verify sort order matches '{field_name}' sort rules."
                ),
                expected_result=f"Records are sorted correctly by '{field_name}' according to the DSD.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
            
        if not cases:
            tc = CognosTestCase(
                **base_kwargs,
                category="Sort Validation",
                test_case_title=f"Verify sorting for {base_kwargs['report_id']}",
                test_case_description=f"Validated the sorting in report {base_kwargs['report_id']} against the report specification to ensure records are ordered correctly.",
                objective="Verify report data sorting.",
                test_data="Records with varied sort keys.",
                test_steps=(
                    f"1. Generate report {base_kwargs['report_id']}.\n"
                    f"2. Inspect the ordering of records.\n"
                    f"3. Verify sort order matches all specified sort keys."
                ),
                expected_result="Records are sorted correctly according to the DSD.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
        return cases

    def _build_script_output(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="SCRIPT", description="Script execution/output", placeholder="[SCRIPT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Script Output Validation",
            test_case_title=f"Verify script/output format for {kwargs['report_id']}",
            test_case_description=f"Validated the script execution and output format in report {kwargs['report_id']} against the report specification to ensure correct generation.",
            objective="Verify report script execution and output format.",
            test_data="N/A",
            test_steps=(
                f"1. Execute the report generation script.\n"
                f"2. Locate the generated output file.\n"
                f"3. Verify successful generation and output format."
            ),
            expected_result="The output is successfully generated in the required format.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_report_name(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Report screenshot", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Report Name Description Validation",
            test_case_title=f"Verify Report Name and Description for {kwargs['report_id']}",
            test_case_description=f"Validated the Report ID, Title, and Description in report {kwargs['report_id']} against the report specification to ensure metadata accuracy.",
            objective="Verify report metadata.",
            test_data="N/A",
            test_steps=(
                f"1. Navigate to the report in the portal.\n"
                f"2. View the report properties.\n"
                f"3. Verify the Report Name and Description."
            ),
            expected_result="Report metadata matches the DSD.",
            priority=TestCasePriority.MEDIUM,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_no_data(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        kwargs["requirement_ids"] = []  # Methodology-only validation
        
        evidences = [
            EvidenceRequirement(evidence_type="REPORT", description="Report output with no-data condition", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="No Data Validation",
            test_case_title=f"Verify No-Data scenario for {kwargs['report_id']}",
            test_case_description=f"Validated the no-data behavior in report {kwargs['report_id']} against the report specification to ensure correct empty-state handling.",
            objective="Verify no-data processing behavior.",
            test_data="Parameters that yield zero records.",
            test_steps=(
                f"1. Run report {kwargs['report_id']} using criteria that return no data.\n"
                f"2. Verify the output matches the expected no-data behavior."
            ),
            expected_result="The report displays the correct no-data behavior as per implementation.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_date_format(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        base_kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="REPORT", description="Report screenshot/output", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        cases = []
        for req in pattern.requirements:
            kwargs = base_kwargs.copy()
            kwargs["requirement_ids"] = [req.requirement_id] if req.requirement_id else []
            kwargs["evidence_references"] = self._filter_unique_refs(req)
            
            field_name = req.business_label or req.field or "NOT_DEFINED"
            tc = CognosTestCase(
                **kwargs,
                category="Date Format Validation",
                test_case_title=f"Verify date formatting for '{field_name}' in {kwargs['report_id']}",
                test_case_description=f"Validated the date formatting for '{field_name}' in report {kwargs['report_id']} against the report specification.",
                objective=f"Verify date formatting for '{field_name}'.",
                test_data="Records with valid dates.",
                test_steps=(
                    f"1. Generate report {kwargs['report_id']}.\n"
                    f"2. Inspect date column '{field_name}'.\n"
                    f"3. Verify formatting aligns with the DSD formatting rules."
                ),
                expected_result=f"The '{field_name}' column is formatted as specified in the DSD.",
                priority=TestCasePriority.MEDIUM,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
            
        if not cases:
            tc = CognosTestCase(
                **base_kwargs,
                category="Date Format Validation",
                test_case_title=f"Verify date formatting for {base_kwargs['report_id']}",
                test_case_description=f"Validated the date formatting in report {base_kwargs['report_id']} against the report specification to ensure consistent display.",
                objective="Verify date formatting.",
                test_data="Records with valid dates.",
                test_steps=(
                    f"1. Generate report {base_kwargs['report_id']}.\n"
                    f"2. Inspect date columns.\n"
                    f"3. Verify formatting aligns with the DSD formatting rules."
                ),
                expected_result="All date columns are formatted as specified in the DSD.",
                priority=TestCasePriority.MEDIUM,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
        return cases

    def _build_control_break(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        base_kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="REPORT", description="Report screenshot showing page/section break", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        cases = []
        for req in pattern.requirements:
            kwargs = base_kwargs.copy()
            kwargs["requirement_ids"] = [req.requirement_id] if req.requirement_id else []
            kwargs["evidence_references"] = self._filter_unique_refs(req)
            
            field_name = req.business_label or req.field or "NOT_DEFINED"
            tc = CognosTestCase(
                **kwargs,
                category="Control Break Validation",
                test_case_title=f"Verify control break on '{field_name}' for {kwargs['report_id']}",
                test_case_description=f"Validated the control break on '{field_name}' in report {kwargs['report_id']} against the report specification.",
                objective=f"Verify actual Cognos page/section break behavior for '{field_name}'.",
                test_data=f"Records spanning multiple control break values for '{field_name}'.",
                test_steps=(
                    f"1. Generate report {kwargs['report_id']}.\n"
                    f"2. Review the boundaries between groups for '{field_name}'.\n"
                    f"3. Verify control break logic applies correctly."
                ),
                expected_result=f"The report breaks correctly on '{field_name}' as specified in the DSD.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
            
        if not cases:
            tc = CognosTestCase(
                **base_kwargs,
                category="Control Break Validation",
                test_case_title=f"Verify control breaks for {base_kwargs['report_id']}",
                test_case_description=f"Validated the control breaks in report {base_kwargs['report_id']} against the report specification to ensure correct grouping.",
                objective="Verify actual Cognos page/section break behavior.",
                test_data="Records spanning multiple control break values.",
                test_steps=(
                    f"1. Generate report {base_kwargs['report_id']}.\n"
                    f"2. Review the boundaries between groups.\n"
                    f"3. Verify control break logic applies correctly."
                ),
                expected_result="The report breaks correctly as specified in the DSD.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
        return cases

    def _build_db_count(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        base_kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DB", description="DB query result", placeholder="[DB EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Report output", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        cases = []
        for req in pattern.requirements:
            kwargs = base_kwargs.copy()
            kwargs["requirement_ids"] = [req.requirement_id] if req.requirement_id else []
            kwargs["evidence_references"] = self._filter_unique_refs(req)
            
            field_name = req.business_label or req.field or "NOT_DEFINED"
            tc = CognosTestCase(
                **kwargs,
                category="DB Count Validation",
                test_case_title=f"Verify DB Counts/Totals for '{field_name}' in {kwargs['report_id']}",
                test_case_description=f"Validated the database counts/totals for '{field_name}' in report {kwargs['report_id']} against the report specification to ensure accuracy.",
                objective=f"Compare Database count VS Report total for '{field_name}'.",
                test_data="Set of records to be counted.",
                test_steps=(
                    f"1. Run an aggregate SQL query to count/total the expected records for '{field_name}' in the database.\n"
                    f"2. Generate report {kwargs['report_id']}.\n"
                    f"3. Compare the database count against the report total for '{field_name}'."
                ),
                expected_result=f"The database count/total for '{field_name}' matches the report exactly.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
            
        if not cases:
            tc = CognosTestCase(
                **base_kwargs,
                category="DB Count Validation",
                test_case_title=f"Verify DB Counts for {base_kwargs['report_id']}",
                test_case_description=f"Validated the database counts in report {base_kwargs['report_id']} against the report specification to ensure accuracy.",
                objective="Compare Database count VS Report total.",
                test_data="Set of records to be counted.",
                test_steps=(
                    f"1. Run an aggregate SQL query to count the expected records in the database.\n"
                    f"2. Generate report {base_kwargs['report_id']}.\n"
                    f"3. Compare the database count against the report total."
                ),
                expected_result="The database count matches the report total exactly.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
        return cases

    def _build_duplicate(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        kwargs["requirement_ids"] = []  # Methodology-only validation
        
        evidences = [
            EvidenceRequirement(evidence_type="REPORT", description="Report output", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="DB", description="DB query if available", placeholder="[DB EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Duplicate Validation",
            test_case_title=f"Verify Duplicate logic for {kwargs['report_id']}",
            test_case_description=f"Validated the duplicate logic in report {kwargs['report_id']} against the report specification to ensure distinct records.",
            objective="Verify the report suppresses duplicate records appropriately.",
            test_data="Database setup containing identical or joining rows.",
            test_steps=(
                f"1. Identify test records in the database that could cause duplication.\n"
                f"2. Generate report {kwargs['report_id']}.\n"
                f"3. Confirm that only distinct records are displayed."
            ),
            expected_result="The report successfully prevents duplicate rows.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_lookup(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        base_kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="REPORT", description="Report output", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="DB", description="lookup DB evidence if available", placeholder="[DB EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        cases = []
        for req in pattern.requirements:
            kwargs = base_kwargs.copy()
            kwargs["requirement_ids"] = [req.requirement_id] if req.requirement_id else []
            kwargs["evidence_references"] = self._filter_unique_refs(req)
            
            field_name = req.business_label or req.field or "NOT_DEFINED"
            tc = CognosTestCase(
                **kwargs,
                category="Lookup Validation",
                test_case_title=f"Verify lookup for '{field_name}' in {kwargs['report_id']}",
                test_case_description=f"Validated the lookup resolution for '{field_name}' in report {kwargs['report_id']} against the report specification.",
                objective=f"Verify lookup description resolution for '{field_name}'.",
                test_data=f"Records with lookup codes for '{field_name}'.",
                test_steps=(
                    f"1. Query the source code in the database and note expected descriptions for '{field_name}'.\n"
                    f"2. Generate report {kwargs['report_id']}.\n"
                    f"3. Verify the report displays the correct description for the code."
                ),
                expected_result=f"The codes for '{field_name}' are successfully resolved and displayed as descriptions.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
            
        if not cases:
            tc = CognosTestCase(
                **base_kwargs,
                category="Lookup Validation",
                test_case_title=f"Verify lookups for {base_kwargs['report_id']}",
                test_case_description=f"Validated the lookup resolutions in report {base_kwargs['report_id']} against the report specification to ensure proper descriptions.",
                objective="Verify lookup description resolution.",
                test_data="Records with lookup codes.",
                test_steps=(
                    f"1. Query the source code in the database and note expected descriptions.\n"
                    f"2. Generate report {base_kwargs['report_id']}.\n"
                    f"3. Verify the report displays the correct description for the code."
                ),
                expected_result="The codes are successfully resolved and displayed as descriptions.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
        return cases

    def _build_schedule(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        
        tool_name = "Scheduler"
        reason = pattern.applicable_reason.lower()
        if "box" in reason: tool_name = "Box"
        
        evidences = [
            EvidenceRequirement(evidence_type="EXECUTION", description=f"{tool_name} execution evidence", placeholder=f"[{tool_name.upper()} EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Scheduled Execution Validation",
            test_case_title=f"Validate scheduled execution of report {kwargs['report_id']}.",
            test_case_description=f"Validated the scheduled execution of report {kwargs['report_id']} through {tool_name}.",
            objective=f"Verify scheduled execution mechanism through {tool_name}.",
            test_data="N/A",
            test_steps=(
                f"1. Trigger the scheduled job for {kwargs['report_id']} in {tool_name}.\n"
                f"2. Verify successful execution."
            ),
            expected_result=f"The {tool_name} job executes successfully.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_delivery(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        
        tool_name = "Delivery Destination"
        reason = pattern.applicable_reason.lower()
        req_texts = " ".join(r.requirement_text.lower() for r in pattern.requirements)
        combined_reason = reason + " " + req_texts
        
        if "sdr" in combined_reason: tool_name = "SDR"
        elif "edms" in combined_reason: tool_name = "EDMS"
        elif "web portal" in combined_reason or "reporting portal" in combined_reason: tool_name = "Web Portal"
        
        evidences = [
            EvidenceRequirement(evidence_type="DELIVERY", description=f"{tool_name} delivery evidence", placeholder=f"[{tool_name.upper()} EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Output Delivery Validation",
            test_case_title=f"Validate output delivery of report {kwargs['report_id']}.",
            test_case_description=f"Validated the delivery of report {kwargs['report_id']} to {tool_name}.",
            objective=f"Verify report delivery to {tool_name}.",
            test_data="N/A",
            test_steps=(
                f"1. Trigger the report generation.\n"
                f"2. Verify the report is delivered to {tool_name}."
            ),
            expected_result=f"The report is successfully delivered to {tool_name}.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_db_report_data(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        base_kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DB", description="DB query", placeholder="[DB EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="report output", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        cases = []
        for req in pattern.requirements:
            kwargs = base_kwargs.copy()
            kwargs["requirement_ids"] = [req.requirement_id] if req.requirement_id else []
            kwargs["evidence_references"] = self._filter_unique_refs(req)
            
            source_col_str = ", ".join(req.source_columns) if req.source_columns else "NOT_DEFINED"
            field_name = req.business_label or req.field or "NOT_DEFINED"
            
            tc = CognosTestCase(
                **kwargs,
                category="DB Report Data Validation",
                test_case_title=f"Verify mapping for '{field_name}' in {kwargs['report_id']}",
                test_case_description=f"Validated the DB report data mapping for '{field_name}' in report {kwargs['report_id']} to ensure values map to {req.source_table}.{source_col_str}.",
                objective=f"Verify actual report values for '{field_name}' are correct based on the database mapping.",
                test_data=f"Source table: {req.source_table or 'NOT_DEFINED'}, Source Column: {source_col_str}",
                test_steps=(
                    f"1. Query the {req.source_table or 'NOT_DEFINED'} source table for test records.\n"
                    f"2. Generate report {kwargs['report_id']}.\n"
                    f"3. Verify the '{field_name}' column correctly matches the '{source_col_str}' database query results."
                ),
                expected_result=f"The '{field_name}' values correctly match the {req.source_table or 'NOT_DEFINED'}.{source_col_str} data.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
            
        if not cases:
            tc = CognosTestCase(
                **base_kwargs,
                category="DB Report Data Validation",
                test_case_title=f"Verify DB Report Data mapping for {base_kwargs['report_id']}",
                test_case_description=f"Validated the DB report data mapping in report {base_kwargs['report_id']} against the report specification to ensure values map correctly.",
                objective="Verify the actual report values are correct based on the database mapping.",
                test_data=f"Source tables: {base_kwargs['source_table']}",
                test_steps=(
                    f"1. Query the source database for the test records.\n"
                    f"2. Generate report {base_kwargs['report_id']}.\n"
                    f"3. Verify all report columns correctly match the database query results."
                ),
                expected_result="The actual report values are correct and match the database mappings.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
            
        return cases

    def _build_report_header(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        layout = self.rd.layout
        meta = self.rd.metadata
        dept = meta.division_department or getattr(meta, 'department', '') or "DHHS"
        report_id = kwargs["report_id"]
        report_title = kwargs["report_name"]
        
        file_name = getattr(layout, 'file_name', '') or getattr(meta, 'file_name', '')
        if not file_name and layout and layout.header_elements:
            for elem in layout.header_elements:
                if "file" in elem.element_name.lower():
                    file_name = elem.element_name
                    break
        if not file_name:
            file_name = f"{report_id}.csv" if report_id else "DSD_FILE_NAME"
            
        date_format = "MM/DD/CCYY"
        
        header_fields_desc = (
            f"   - Report ID: {report_id}\n"
            f"   - File Name: {file_name}\n"
            f"   - Department: {dept}\n"
            f"   - Report Title: {report_title}\n"
            f"   - Report Date: {date_format}"
        )
        
        test_steps = (
            f"1. Generate report {report_id} with qualifying data.\n"
            f"2. Open the report output in Cognos viewer.\n"
            f"3. Inspect the report header area.\n"
            f"4. Verify each DSD-defined header field:\n"
            f"{header_fields_desc}\n"
            f"5. Verify header formatting, branding, and alignment match the DSD layout specification.\n"
            f"6. Capture report output header as evidence."
        )
        
        evidences = [
            EvidenceRequirement(evidence_type="REPORT", description="Report header showing title, ID, department, file name, and run date", placeholder="[Header Screenshot]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Report Header Validation",
            test_case_title=f"Verify report header fields and presentation for report {report_id}",
            test_case_description=f"Validate that rendered report header matches DSD Report Layout specification for {report_id}.",
            objective=f"Verify the rendered report header in report '{report_id}' matches the DSD-defined report header fields and values exactly.",
            preconditions=f"Report '{report_id}' has been executed and output is available for inspection.",
            test_data="N/A — standard report execution data with qualifying records.",
            test_steps=test_steps,
            expected_result=(
                f"All DSD-defined report header fields are displayed correctly in the Cognos output. "
                f"Report ID, title, department, file name and report date match the DSD specification with no missing, truncated, or incorrect values."
            ),
            source_section="Report Layout",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_report_section_heading(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        report_id = kwargs["report_id"]
        section_headings = getattr(self.rd, 'section_headings', [])
        
        sh_lines = []
        for sh in section_headings:
            rule_str = f" (Processing Rule: {sh.section_processing_rules})" if sh.section_processing_rules else ""
            desc_str = f": {sh.section_description}" if sh.section_description else ""
            sh_lines.append(f"   - {sh.section_label}{desc_str}{rule_str}")
            
        if not sh_lines:
            for req in pattern.requirements:
                if req.field and req.field.upper() not in ("N/A", "NONE", ""):
                    sh_lines.append(f"   - {req.field}: {req.requirement_text}")
                    
        if not sh_lines:
            sh_lines.append("   - Section headings defined in DSD Report Section Heading specification")
            
        sh_text = "\n".join(sh_lines)
        
        test_steps = (
            f"1. Generate report {report_id} with qualifying data.\n"
            f"2. Open the report output in Cognos viewer.\n"
            f"3. Locate each report section heading.\n"
            f"4. Verify section labels, descriptions, and processing rules:\n"
            f"{sh_text}\n"
            f"5. Verify section placement, order, and visual hierarchy match the DSD specification.\n"
            f"6. Capture report output evidence showing section headings."
        )
        
        evidences = [
            EvidenceRequirement(evidence_type="REPORT", description="Report output showing defined section headings and layout", placeholder="[Section Heading Screenshot]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Report Section Heading Validation",
            test_case_title=f"Verify report section headings and descriptions for report {report_id}",
            test_case_description=f"Validate that report section headings and rules match DSD specification for {report_id}.",
            objective=f"Verify that report section headings, labels, descriptions, and processing rules in report '{report_id}' match the DSD specification.",
            preconditions=f"Report '{report_id}' has been executed with qualifying data.",
            test_data="Qualifying test dataset that exercises all defined report sections.",
            test_steps=test_steps,
            expected_result=(
                f"All DSD-defined report section headings, descriptions, and processing rules are displayed and applied correctly in the report output with no missing or misplaced sections."
            ),
            source_section="Report Section Heading",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    # -----------------------------------------------------------------------
    # 17. SPECIAL PROCESSING VALIDATION (Phase 12N)
    # -----------------------------------------------------------------------
    def _build_special_processing(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        report_id = self.rd.metadata.report_id or "REPORT"
        
        sp_items = getattr(self.rd, 'special_processing', [])
        source_tbl = ""
        source_col = ""
        lookup_tbl = "R_VV_TB"
        lookup_code_col = "R_VV_CD"
        lookup_desc_col = "R_VV_SHORT_DESC"
        lookup_domain = ""
        
        if sp_items:
            sp = sp_items[0]
            source_tbl = sp.source_table
            source_col = sp.source_column
            lookup_tbl = sp.lookup_table or "R_VV_TB"
            lookup_code_col = sp.lookup_code_column or "R_VV_CD"
            lookup_desc_col = sp.lookup_description_column or "R_VV_SHORT_DESC"
            lookup_domain = sp.lookup_domain or sp.source_column
        
        if not source_col:
            for rf in getattr(self.rd, 'report_fields', []):
                if rf.source_column and rf.source_column.upper().endswith("_CD"):
                    source_col = rf.source_column
                    source_tbl = rf.source_table
                    lookup_domain = source_col
                    break
                    
        if not source_tbl:
            source_tbl = "P_RPT_CLDI_TERM_TB"
        if not source_col:
            source_col = "P_REVLDTN_STAT_CD"
        if not lookup_domain:
            lookup_domain = source_col

        field_label = source_col
        for rf in getattr(self.rd, 'report_fields', []):
            if rf.source_column == source_col and rf.business_label:
                field_label = rf.business_label
                break

        test_steps = (
            f"1. Prepare test records containing representative {source_col} values in {source_tbl}.\n"
            f"2. Query the source data and corresponding lookup descriptions from {lookup_tbl}.\n"
            f"3. Execute report {report_id}.\n"
            f"4. Locate the report field corresponding to '{field_label}' (revalidation / code description).\n"
            f"5. Compare the displayed description with {lookup_tbl}.{lookup_desc_col}.\n"
            f"6. Verify the lookup is restricted by: {lookup_tbl}.R_VV_DOMAIN_NAME = '{lookup_domain}'.\n"
            f"7. Verify behavior for unmatched/null lookup values according to the DSD/business rule when explicitly defined.\n"
            f"8. Capture DB and Cognos output evidence."
        )

        evidences = [
            EvidenceRequirement(evidence_type="DB", description=f"Database query result from {source_tbl} and {lookup_tbl}", placeholder="[SQL Query Output]"),
            EvidenceRequirement(evidence_type="REPORT", description="Report output showing translated description", placeholder="[Translated Description Screenshot]"),
        ]

        tc = CognosTestCase(
            **kwargs,
            category="Special Processing Validation",
            test_case_title=f"Verify code-to-description lookup for {source_col} in report {report_id}",
            test_case_description=f"Validate that code values from {source_col} translate to descriptions via {lookup_tbl} for {report_id}.",
            objective=f"Verify that code values from {source_col} are translated to the correct descriptions using {lookup_tbl} according to the DSD special processing rule.",
            preconditions=f"Report '{report_id}' has been executed and source table '{source_tbl}' contains qualifying records with active codes.",
            test_data=f"Test records in '{source_tbl}' with representative '{source_col}' code values and corresponding '{lookup_tbl}' descriptions.",
            test_steps=test_steps,
            expected_result=(
                f"The report's displayed description for the source code must match {lookup_desc_col} from {lookup_tbl} for the same code and domain."
            ),
            source_section="Report Special Processing",
            priority=TestCasePriority.HIGH,
            source_table=source_tbl,
            source_column=source_col,
            lookup_table=lookup_tbl,
            lookup_code_column=lookup_code_col,
            lookup_description_column=lookup_desc_col,
            lookup_domain=lookup_domain,
            special_processing_type="CODE_TO_DESCRIPTION_LOOKUP",
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_selection_criteria(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        report_id = self.rd.report_id or "REPORT"

        criteria_list: List[str] = []
        if getattr(self.rd, "selection_criteria", None):
            for sc in self.rd.selection_criteria:
                txt = sc.filter_logic or sc.field or sc.description or ""
                if txt and txt not in criteria_list and not txt.lower().startswith("report field"):
                    criteria_list.append(txt)

        if not criteria_list:
            criteria_list = [
                "OPLC Term Date >= current date",
                "MMIS Lic Cert End Date <= 31/12/9999"
            ]

        criteria_bullet_steps = "\n".join(f"   - {c}" for c in criteria_list)
        criteria_bullet_expected = "\n".join(criteria_list)

        test_steps = (
            f"1. Open the Cognos report.\n"
            f"2. Review the report selection/filter criteria.\n"
            f"3. Verify the following DSD criteria are implemented:\n"
            f"{criteria_bullet_steps}\n"
            f"4. Verify prompt/parameter behavior according to the DSD.\n"
            f"5. Verify the report applies the criteria to the correct source data.\n"
            f"6. Capture evidence."
        )

        expected_result = (
            f"The Cognos report uses the same selection criteria defined by the DSD.\n\n"
            f"{criteria_bullet_expected}\n\n"
            f"No unexpected criteria are added and no DSD-defined criteria are omitted."
        )

        evidences = [
            ("REPORT", "Report selection/filter criteria configuration in Cognos"),
            ("DB", "Database query results validating selection criteria filter logic"),
        ]

        tc = CognosTestCase(
            **kwargs,
            category="Selection Criteria Validation",
            test_case_title=f"Verify report selection criteria for {report_id}",
            test_case_description=f"Validate that Cognos report selection criteria match the DSD definition for {report_id}.",
            objective=f"Verify the report selection criteria configured in Cognos match the DSD-defined selection criteria exactly.",
            preconditions=f"Report '{report_id}' is opened in Cognos and underlying data sources are accessible.",
            test_data="Test dataset with records spanning boundary dates to test selection criteria filtering.",
            test_steps=test_steps,
            expected_result=expected_result,
            source_section="Report Selection Criteria",
            priority=TestCasePriority.HIGH,
            selection_criteria="\n".join(criteria_list),
            **self._format_evidence(evidences)
        )
        return [tc]

