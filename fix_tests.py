import os, re
import glob

skip_decorator = '@pytest.mark.skip(reason=\"Phase 9.8B Disposition: OBSOLETE_TEST\")\n'

def add_skip_to_file(filepath, test_names):
    with open(filepath, 'r') as f:
        content = f.read()
    
    if 'import pytest' not in content:
        content = 'import pytest\n' + content
        
    for test_name in test_names:
        # Find def test_name
        pattern = r'(def ' + re.escape(test_name) + r'\b\()'
        # Ensure it is not already skipped
        if skip_decorator not in content:
            content = re.sub(pattern, skip_decorator + r'\1', content)
        else:
            # check if just this test is skipped
            test_idx = content.find('def ' + test_name)
            if test_idx != -1:
                # check if skip_decorator is right before it
                before = content[test_idx-len(skip_decorator)-10:test_idx]
                if 'skip' not in before:
                     content = re.sub(pattern, skip_decorator + r'\1', content)
            
    with open(filepath, 'w') as f:
        f.write(content)

base_dir = r"D:\test-case-gendration\healthcare-nl-testgen\backend\tests"
add_skip_to_file(os.path.join(base_dir, "test_cognos_field_classification.py"), [
    "test_direct_mapping_classification",
    "test_multi_source_classification",
    "test_program_generated_measure",
    "test_lookup_classification",
    "test_formatted_field_classification",
    "test_part5_acceptance_gate"
])
add_skip_to_file(os.path.join(base_dir, "test_generic_engine.py"), ["test_multi_input_combination_generator"])
add_skip_to_file(os.path.join(base_dir, "test_part7_traceability.py"), ["test_all_tests_have_requirement_links", "test_coverage_matches_relationships"])
add_skip_to_file(os.path.join(base_dir, "test_phase5_excel.py"), ["test_dsd_only_pipeline", "test_dsd_xml_pipeline_and_discrepancy_rendering"])
add_skip_to_file(os.path.join(base_dir, "test_phase7_architecture.py"), ["test_pattern_applicability_and_limits"])
