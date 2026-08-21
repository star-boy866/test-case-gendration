import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

from app.domain.cognos_test_case import CognosTestCase
from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import RequirementSet
from app.infrastructure.llm.llm_provider import get_llm_call, LLMUnavailableError
from app.core.telemetry import get_logger

logger = get_logger(__name__)

PROMPT_TEMPLATE = """You are an expert Cognos UT Test Designer.
Your task is to refine a deterministically generated test case into natural, professional developer language.

You MUST NOT invent new requirements or change the authoritative facts.
Your ONLY job is to improve the readability of the Title, Steps, and Expected Result.

--- REPORT CONTEXT ---
Report ID: {report_id}
Report Title: {report_title}

--- AUTHORITATIVE FACTS (DO NOT CHANGE) ---
Category: {category}
Objective: {objective}
Source Table: {source_table}
Source Column: {source_column}
Processing Rule: {processing_rule}
Formatting Rule: {formatting_rule}
Requirements Addressed:
{requirements_text}

--- ORIGINAL TEXT TO REFINE ---
Title: {title}
Steps:
{steps}
Expected Result: {expected_result}

--- INSTRUCTIONS ---
Return ONLY a valid JSON object with EXACTLY these three keys (no markdown blocks, no extra text):
{{
  "refined_title": "<A clear, concise developer-style test title>",
  "refined_steps": "<A numbered list of test execution steps in natural language (use 1., 2., etc.)>",
  "refined_expected_result": "<The precise expected outcome based on the processing rules and source mapping>"
}}
"""

class CognosLLMService:
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.llm_call = get_llm_call()

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        # Find JSON block
        if "```json" in text:
            match = re.search(r"```json(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()
        elif "```" in text:
            match = re.search(r"```(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()
        
        # fallback brace matching
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            text = text[start:end+1]
            
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("llm_json_decode_error", error=str(e), text=text)
            return {}

    def _build_prompt(self, tc: CognosTestCase, report_def: ReportDefinition, req_set: RequirementSet) -> str:
        req_texts = []
        if tc.requirement_ids:
            for rid in tc.requirement_ids:
                req = next((r for r in req_set.requirements if r.requirement_id == rid), None)
                if req:
                    req_texts.append(f"- [{rid}] {req.requirement_text}")
        
        reqs_str = "\n".join(req_texts) if req_texts else "None"
        
        return PROMPT_TEMPLATE.format(
            report_id=report_def.metadata.report_id,
            report_title=report_def.metadata.report_title,
            category=tc.category,
            objective=tc.objective,
            source_table=tc.source_table or "N/A",
            source_column=tc.source_column or "N/A",
            processing_rule=tc.processing_rule or "N/A",
            formatting_rule=tc.formatting_rule or "N/A",
            requirements_text=reqs_str,
            title=tc.test_case_title,
            steps=tc.test_steps,
            expected_result=tc.expected_result
        )

    def _refine_single_test_case(self, tc: CognosTestCase, report_def: ReportDefinition, req_set: RequirementSet) -> CognosTestCase:
        prompt = self._build_prompt(tc, report_def, req_set)
        
        try:
            response_text = self.llm_call(prompt)
            data = self._extract_json(response_text)
            
            # Apply only if valid keys exist, keeping authoritative deterministic facts untouched.
            if "refined_title" in data and data["refined_title"]:
                tc.test_case_title = str(data["refined_title"])
            if "refined_steps" in data and data["refined_steps"]:
                tc.test_steps = str(data["refined_steps"])
            if "refined_expected_result" in data and data["refined_expected_result"]:
                tc.expected_result = str(data["refined_expected_result"])
                
        except LLMUnavailableError:
            logger.warning("llm_unavailable_during_refinement", test_case_id=tc.test_case_id)
        except Exception as e:
            logger.error("llm_refinement_failed", error=str(e), test_case_id=tc.test_case_id)
            
        return tc

    def refine_test_cases(self, test_cases: List[CognosTestCase], report_def: ReportDefinition, req_set: RequirementSet) -> List[CognosTestCase]:
        """Refines a list of test cases in parallel using the LLM."""
        refined_cases = []
        
        # Parallelize the LLM calls to reduce latency
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._refine_single_test_case, tc.model_copy(deep=True), report_def, req_set): tc
                for tc in test_cases
            }
            
            # Collect results
            results_map = {}
            for future in as_completed(futures):
                original_tc = futures[future]
                try:
                    refined_tc = future.result()
                    results_map[original_tc.test_case_id] = refined_tc
                except Exception as e:
                    logger.error("parallel_refinement_error", error=str(e))
                    results_map[original_tc.test_case_id] = original_tc
                    
        # Return in the original order
        return [results_map[tc.test_case_id] for tc in test_cases]
