"""
Scenario Composer - Composes CognosTestCase based on applicable methodology patterns.
"""
from typing import List, Optional

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import CognosRequirement
from app.domain.cognos_test_case import CognosTestCase, TestCasePriority, EvidenceRequirement
from app.cognos.rules.scenario_patterns import ApplicablePattern, MethodologyPattern


class ScenarioComposer:
    def __init__(self, rd: ReportDefinition, base_precondition: str):
        self.rd = rd
        self.base_precondition = base_precondition

    def compose(self, applicable_patterns: List[ApplicablePattern]) -> List[CognosTestCase]:
        cases = []
        for pattern in applicable_patterns:
            cases.extend(self._compose_pattern(pattern))
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
            MethodologyPattern.LOOKUP_DESCRIPTION_VALIDATION: self._build_lookup,
            MethodologyPattern.BOX_EXECUTION_VALIDATION: self._build_box,
            MethodologyPattern.SDR_DELIVERY_VALIDATION: self._build_sdr,
            MethodologyPattern.DB_REPORT_DATA_VALIDATION: self._build_db_report_data,
        }
        builder = builder_map.get(pattern.pattern)
        if builder:
            return builder(pattern)
        return []

    def _get_common_kwargs(self, pattern: ApplicablePattern) -> dict:
        req_ids = list(set([req.requirement_id for req in pattern.requirements if req.requirement_id]))
        source_doc = self.rd.source_document or ""
        st = "REVIEW_REQUIRED"
        tables = {}
        for r in pattern.requirements:
            if r.source_table:
                tables[r.source_table] = tables.get(r.source_table, 0) + 1
        if tables:
            st = max(tables, key=tables.get)

        return {
            "report_id": self.rd.metadata.report_id or "COGNOS-RPT",
            "report_name": self.rd.metadata.report_title or "Cognos Report",
            "requirement_ids": req_ids,
            "source_document": source_doc,
            "preconditions": self.base_precondition,
            "source_table": st,
            "origin": "DEV_UT_METHODOLOGY",
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

    def _build_layout(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        fields = [req.field for req in pattern.requirements if req.field]
        field_str = ", ".join(fields) if fields else "report layout fields"
        
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing layout requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Generated report output", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Report Layout",
            test_case_title=f"Verify layout/presentation for {kwargs['report_id']}",
            test_case_description="Validate the report header, footer, pagination, and structural layout matches the DSD.",
            objective="Verify the layout format is correctly implemented.",
            test_data="N/A",
            test_steps=(
                f"1. Generate report {kwargs['report_id']}.\n"
                f"2. Compare layout presentation against DSD layout requirements."
            ),
            expected_result="The report layout (header, footer, pagination) matches the format specified in the DSD.",
            priority=TestCasePriority.MEDIUM,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_label(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        labels = [req.field for req in pattern.requirements if req.field]
        label_str = ", ".join(labels) if labels else "all columns"
        
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing label requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Generated report output", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Report Label",
            test_case_title=f"Verify column labels in {kwargs['report_id']}",
            test_case_description="Ensure that all column headers/labels exactly match the DSD specifications.",
            objective="Verify column labels.",
            test_data="N/A",
            test_steps=(
                f"1. Generate report {kwargs['report_id']}.\n"
                f"2. Inspect the column headers.\n"
                f"3. Verify headers match: {label_str}."
            ),
            expected_result=f"The column headers exactly match the DSD: {label_str}.",
            priority=TestCasePriority.MEDIUM,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_sort(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        cases = []
        for req in pattern.requirements:
            kwargs = self._get_common_kwargs(pattern)
            kwargs["source_field"] = req.field or "N/A"
            kwargs["linked_requirements"] = [req.requirement_id] if req.requirement_id else []
            
            sort_str = req.processing_rule or "the DSD sorting requirements"
            
            evidences = [
                EvidenceRequirement(evidence_type="DSD", description="DSD showing sort requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
                EvidenceRequirement(evidence_type="REPORT", description="Generated report output showing sort order", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]"),
                EvidenceRequirement(evidence_type="DB", description="Database query showing natural order", placeholder="[DB EVIDENCE — INSERT SCREENSHOT]")
            ]
            
            tc = CognosTestCase(
                **kwargs,
                category="Sorting",
                test_case_title=f"Verify sort ordering on {kwargs['source_field']}",
                test_case_description=f"Validate that the data is sorted according to the specification for {kwargs['source_field']}.",
                objective="Verify report data sorting.",
                test_data="Records with varied sort keys to demonstrate ordering.",
                test_steps=(
                    f"1. Generate report {kwargs['report_id']}.\n"
                    f"2. Inspect the ordering of records.\n"
                    f"3. Verify sort order matches: {sort_str}."
                ),
                expected_result=f"Records are sorted according to the DSD: {sort_str}.",
                priority=TestCasePriority.HIGH,
                **self._format_evidence(evidences)
            )
            cases.append(tc)
        return cases

    def _build_script_output(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing output format requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="OUTPUT_FILE", description="Generated output file", placeholder="[OUTPUT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Output Format",
            test_case_title=f"Verify script/output format for {kwargs['report_id']}",
            test_case_description="Ensure the report is produced in the required output format (e.g. CSV, Excel) and retention policy.",
            objective="Verify report output format and generation script.",
            test_data="N/A",
            test_steps=(
                f"1. Run the operational script for {kwargs['report_id']}.\n"
                f"2. Locate the generated output.\n"
                f"3. Verify the output format and naming."
            ),
            expected_result="The output is generated in the required format and stored appropriately.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_report_name(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing report metadata", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="COGNOS_CONFIGURATION", description="Cognos portal showing report properties", placeholder="[COGNOS CONFIGURATION EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Metadata",
            test_case_title=f"Verify Report Name and Description for {kwargs['report_id']}",
            test_case_description="Validate that the report's name and description in Cognos match the DSD.",
            objective="Verify report metadata.",
            test_data="N/A",
            test_steps=(
                f"1. Navigate to the report in the Cognos portal.\n"
                f"2. View the report properties.\n"
                f"3. Verify the Report Name and Description."
            ),
            expected_result=f"The Report Name is '{kwargs['report_name']}' and the description matches the DSD.",
            priority=TestCasePriority.MEDIUM,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_no_data(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing no-data requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Generated report with no data", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="No Data",
            test_case_title=f"Verify No Data scenario for {kwargs['report_id']}",
            test_case_description="Validate the report behavior when no data meets the selection criteria.",
            objective="Verify no-data processing logic.",
            test_data="Parameters that yield zero records.",
            test_steps=(
                f"1. Run report {kwargs['report_id']} using criteria that return no data.\n"
                f"2. Verify the output matches the no-data specification."
            ),
            expected_result="The report displays the specified no-data message or empty layout as per the DSD.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_date_format(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing date format requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Generated report showing date formatting", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Date Format",
            test_case_title=f"Verify date formats in {kwargs['report_id']}",
            test_case_description="Ensure that all date fields apply the correct display formatting.",
            objective="Verify date formatting.",
            test_data="Records with valid dates.",
            test_steps=(
                f"1. Generate report {kwargs['report_id']}.\n"
                f"2. Inspect date columns.\n"
                f"3. Verify formatting aligns with the DSD."
            ),
            expected_result="All date columns are formatted exactly as specified in the DSD.",
            priority=TestCasePriority.MEDIUM,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_control_break(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing control break requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Report showing control breaks", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Control Break",
            test_case_title=f"Verify control breaks in {kwargs['report_id']}",
            test_case_description="Validate section or page breaks trigger correctly upon grouping value changes.",
            objective="Verify control break logic.",
            test_data="Records grouped across multiple distinct control values.",
            test_steps=(
                f"1. Generate report {kwargs['report_id']}.\n"
                f"2. Review the boundaries between groups.\n"
                f"3. Verify control break layout applies correctly."
            ),
            expected_result="The report breaks correctly as specified in the DSD when the control field changes.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_db_count(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing count/total requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Report showing totals", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="SQL_OUTPUT", description="Database count query results", placeholder="[DB EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Totals/Counts",
            test_case_title=f"Verify DB Counts/Totals in {kwargs['report_id']}",
            test_case_description="Verify that report record counts or value totals match the underlying database sums.",
            objective="Verify report counts against database.",
            test_data="Set of records to be counted/summed.",
            test_steps=(
                f"1. Run an aggregate SQL query to count/sum the expected records.\n"
                f"2. Generate report {kwargs['report_id']}.\n"
                f"3. Compare the report totals with the SQL output."
            ),
            expected_result="The counts and totals in the report exactly match the database query results.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_duplicate(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing distinct/duplicate requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Report showing unique records", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="DB", description="Database state showing multiple rows", placeholder="[DB EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Duplicate Data",
            test_case_title=f"Verify Duplicate Prevention in {kwargs['report_id']}",
            test_case_description="Validate that the report suppresses duplicate records as required.",
            objective="Verify distinct/unique record logic.",
            test_data="Database setup containing multiple identical or joining rows that could cause duplication.",
            test_steps=(
                f"1. Identify or insert duplicate test records in the database.\n"
                f"2. Generate report {kwargs['report_id']}.\n"
                f"3. Confirm that only distinct records are displayed according to DSD."
            ),
            expected_result="The report successfully prevents duplicate rows and displays distinct records as specified.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_lookup(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing lookup requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Report showing lookup description", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="DB", description="Database showing lookup code", placeholder="[DB EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Lookup Logic",
            test_case_title=f"Verify Lookup Description mapping in {kwargs['report_id']}",
            test_case_description="Validate that codes are correctly transformed into descriptions via lookups.",
            objective="Verify lookup code-to-description transformation.",
            test_data="Records with lookup codes.",
            test_steps=(
                f"1. Query the source code in the database and verify the expected description in the lookup table.\n"
                f"2. Generate report {kwargs['report_id']}.\n"
                f"3. Verify the report displays the resolved description instead of the code."
            ),
            expected_result="The codes are successfully resolved and displayed as descriptions according to the DSD.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_box(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing Box execution/distribution requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="BOX", description="Box scheduling configuration/job output", placeholder="[BOX EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Distribution",
            test_case_title=f"Verify Box execution/scheduler for {kwargs['report_id']}",
            test_case_description="Ensure the report can be scheduled and executed via Box.",
            objective="Verify Box scheduler integration.",
            test_data="N/A",
            test_steps=(
                f"1. Trigger the Box job for {kwargs['report_id']}.\n"
                f"2. Monitor the execution logs.\n"
                f"3. Verify successful completion and file distribution."
            ),
            expected_result="The Box job executes successfully and distributes the output as required.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_sdr(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing SDR/EDMS delivery requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="SDR", description="SDR delivery confirmation", placeholder="[SDR EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        tc = CognosTestCase(
            **kwargs,
            category="Distribution",
            test_case_title=f"Verify SDR/EDMS Delivery for {kwargs['report_id']}",
            test_case_description="Validate the report is delivered to the SDR/EDMS platform.",
            objective="Verify SDR delivery integration.",
            test_data="N/A",
            test_steps=(
                f"1. Trigger the report generation targeting SDR delivery.\n"
                f"2. Navigate to the SDR/EDMS platform.\n"
                f"3. Verify the report document is uploaded and accessible."
            ),
            expected_result="The report is successfully delivered to SDR/EDMS with correct metadata.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        return [tc]

    def _build_db_report_data(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        cases = []
        
        reqs = pattern.requirements
        
        kwargs = self._get_common_kwargs(pattern)
        evidences = [
            EvidenceRequirement(evidence_type="DSD", description="DSD showing data mapping requirements", placeholder="[DSD EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="REPORT", description="Generated report data", placeholder="[REPORT EVIDENCE — INSERT SCREENSHOT]"),
            EvidenceRequirement(evidence_type="DB", description="Source database records", placeholder="[DB EVIDENCE — INSERT SCREENSHOT]")
        ]
        
        field_names = [r.field for r in reqs if r.field]
        field_str = ", ".join(field_names[:5]) + ("..." if len(field_names) > 5 else "")
        
        tc = CognosTestCase(
            **kwargs,
            category="Database Validation",
            test_case_title=f"Verify DB-to-Report data mapping for {kwargs['report_id']}",
            test_case_description="Validate that report data exactly matches the source database, applying standard logic.",
            objective="Verify direct data mapping and logic.",
            test_data=f"Source tables: {kwargs['source_table']}",
            test_steps=(
                f"1. Query the source database for the test records.\n"
                f"2. Generate report {kwargs['report_id']}.\n"
                f"3. Verify report columns (e.g., {field_str}) match the database query results."
            ),
            expected_result="All report data fields correctly map to and match their respective source database values.",
            priority=TestCasePriority.HIGH,
            **self._format_evidence(evidences)
        )
        cases.append(tc)
        
        # Analysis of transformations
        for req in reqs:
            if req.processing_rule and ("if" in req.processing_rule.lower() or "case" in req.processing_rule.lower()):
                tc_kwargs = {**kwargs, "requirement_ids": [req.requirement_id] if req.requirement_id else []}
                tc_trans = CognosTestCase(
                    **tc_kwargs,
                    category="Column Logic",
                    test_case_title=f"Verify '{req.field}' DB logic",
                    test_case_description=f"Validate '{req.field}' specific logic: {req.processing_rule}",
                    objective=f"Verify DB mapping logic for {req.field}.",
                    test_data=f"DB Setup: records fulfilling the conditions in rule.",
                    test_steps=(
                        f"1. Setup data in database according to condition.\n"
                        f"2. Generate report {kwargs['report_id']}.\n"
                        f"3. Verify '{req.field}' matches expected rule."
                    ),
                    expected_result=f"The field '{req.field}' evaluates correctly based on {req.processing_rule}.",
                    priority=TestCasePriority.MEDIUM,
                    **self._format_evidence(evidences)
                )
                cases.append(tc_trans)
        
        return cases
