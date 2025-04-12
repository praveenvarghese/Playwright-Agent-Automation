import json

def extract_from_file(json_path, test_case_id):
    seen = set()
    selector_list = []
    selector_text = "# CSS selectors detected from raw JSON\n\n"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for history_item in data.get("history", []):
        actions = history_item.get("result", [])
        elements = history_item.get("state", {}).get("interacted_element", [])

        for action, element in zip(actions, elements):
            if not element or "css_selector" not in element:
                continue

            selector = element["css_selector"]
            if selector in seen:
                continue
            seen.add(selector)

            tag = element.get("tag_name", "unknown")
            content = action.get("extracted_content", "").lower()

            if "click" in content:
                action_type = "click"
            elif "input" in content:
                action_type = "input"
            elif "scroll" in content:
                action_type = "scroll"
            else:
                action_type = "unknown"

            selector_list.append({
                "action": action_type,
                "tag": tag,
                "text": content,
                "selector": selector
            })

            selector_text += f"Action: {action_type}\nElement: {tag}\nText: {content}\nSelector: {selector}\n\n"

    with open(f"{test_case_id}_selectors.json", "w", encoding="utf-8") as f:
        json.dump(selector_list, f, indent=2)
    with open(f"{test_case_id}_selectors.txt", "w", encoding="utf-8") as f:
        f.write(selector_text)

    print(f"✅ Extracted {len(selector_list)} selectors with actions")

# Run extraction
extract_from_file("TC-ENV-001_raw_agent_result.json", "TC-ENV-001")
