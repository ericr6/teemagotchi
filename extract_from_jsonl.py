import json

def extract_first_n_texts(input_path, output_path, N):
    extracted = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= N:
                break
            try:
                data = json.loads(line)
                text_content = data.get("text", "")

                # Extract rich text from 'blocks'
                if "blocks" in data:
                    for block in data["blocks"]:
                        if block["type"] == "rich_text":
                            for element in block["elements"]:
                                if element["type"] == "rich_text_section":
                                    for sub_elem in element["elements"]:
                                        if sub_elem.get("type") == "text":
                                            text_content += "\n" + sub_elem["text"]

                extracted.append(text_content.strip())

            except json.JSONDecodeError as e:
                print(f"Skipping bad JSON on line {i+1}: {e}")

    with open(output_path, 'w', encoding='utf-8') as out:
        out.write("\n\n---\n\n".join(extracted))
    print(f"Saved first {len(extracted)} messages to {output_path}")


# Example usage
extract_first_n_texts("input_example/history.jsonl", "input_example/sample_1.txt", N=1)
extract_first_n_texts("input_example/history.jsonl", "input_example/sample_5.txt", N=5)
extract_first_n_texts("input_example/history.jsonl", "input_example/sample_10.txt", N=10)
