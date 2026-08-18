import json
import os

def create_golden():
    golden = {
        "metadata": {
            "report_id": "PRV-INT-027",
            "title": "Provider License Interface - Term Date Report",
            "description": "To record any Interface errors that occurred during the Common License Interface.",
            "source_type": "OLTP",
            "source_component": "Provider",
            "generation": "Scheduled",
            "calendar": "State Fiscal",
            "trigger_frequency": "Daily",
            "accumulation": "Prompt"
        },
        "requirements": [],
        "expected_comments": [
            {
                "id": "1",
                "author": "Reviewer 1",
                "text": "Are we sure this should be PDF?",
                "location": "Table 1, Row 45",
                "status": "unresolved"
            }
        ],
        "expected_gaps": [
            "Blank placeholder row in Report Body template not populated."
        ],
        "expected_conflicts": [
            "Checkbox indicates PDF but comment asks if it should be Excel."
        ],
        "expected_assumptions": [
            "Assuming PROV_NAME is the correct source column for Provider Name."
        ],
        "expected_source_pages": [1, 2, 3]
    }

    # Generate meaningful requirements
    areas = ["Identification", "Purpose", "Source", "Generation", "Calendar", "Trigger", "Accumulation", "Selection", "Sorting", "Layout", "Output", "Portal", "Retention", "Special Processing"]
    
    req_id_counter = 1
    
    for area in areas:
        golden["requirements"].append({
            "requirement_id": f"REQ-{req_id_counter:03d}",
            "area": area,
            "atomic_statement": f"The report shall define {area.lower()}.",
            "origin": "DSD_EXPLICIT",
            "status": "CONFIRMED",
            "source_page": 1,
            "source_section": "Report Definition",
            "source_location": "Table 1"
        })
        req_id_counter += 1

    # Report Body Fields
    body_fields = ["Provider ID", "Provider Name", "License Type", "Term Date", "Error Code", "Error Description"]
    for field in body_fields:
        golden["requirements"].append({
            "requirement_id": f"REQ-{req_id_counter:03d}",
            "area": "Report Body",
            "atomic_statement": f"The report shall display the {field}.",
            "origin": "DSD_EXPLICIT",
            "status": "CONFIRMED",
            "source_page": 2,
            "source_section": "Report Layout",
            "source_location": "Table 2",
            "field_mapping": {
                "source": "P_RPT_CLDI_TERM_TB",
                "column": field.upper().replace(" ", "_")
            }
        })
        req_id_counter += 1
        
    # Add a contradicted requirement
    golden["requirements"].append({
        "requirement_id": f"REQ-{req_id_counter:03d}",
        "area": "Output",
        "atomic_statement": "The report shall be output in PDF format.",
        "origin": "DSD_EXPLICIT",
        "status": "CONFLICT",
        "source_page": 1,
        "source_section": "Report Output",
        "source_location": "Table 1, Row 45"
    })
    req_id_counter += 1

    # Add processing rule
    golden["requirements"].append({
        "requirement_id": f"REQ-{req_id_counter:03d}",
        "area": "Processing Rules",
        "atomic_statement": "If no data available, display 'No data available'.",
        "origin": "DSD_EXPLICIT",
        "status": "CONFIRMED",
        "source_page": 3,
        "source_section": "Special Processing",
        "source_location": "Table 3"
    })
    
    os.makedirs('poc/document_parsing_benchmark/golden', exist_ok=True)
    with open('poc/document_parsing_benchmark/golden/PRV-INT-027_golden.json', 'w', encoding='utf-8') as f:
        json.dump(golden, f, indent=2)
        
    return golden

if __name__ == '__main__':
    create_golden()
