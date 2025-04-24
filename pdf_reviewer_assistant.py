# pdf_reviewer_assistant.py (with tool support)

import os
import fitz  # PyMuPDF
import openai
import json
import tiktoken
from statistics_helper import (
    recalculate_p_value,
    compute_cohens_d,
    compute_confidence_interval,
    describe_group
)

openai.api_key = os.getenv("OPENAI_API_KEY")

# -----------------------------
# Step 1: Extract text from PDF
# -----------------------------
def extract_text_from_pdf(path):
    doc = fitz.open(path)
    full_text = "\n".join(page.get_text() for page in doc)
    return full_text

# -----------------------------
# Step 2: Chunk text if needed
# -----------------------------
def chunk_text(text, max_tokens=12000, model="gpt-4o-mini"):
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    chunks = []

    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i + max_tokens]
        chunk_text = encoding.decode(chunk)
        chunks.append(chunk_text)

    return chunks

# -----------------------------
# Step 3: Tool registry
# -----------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "recalculate_p_value",
            "description": "Calculate p-value between two sample groups",
            "parameters": {
                "type": "object",
                "properties": {
                    "group1": {"type": "array", "items": {"type": "number"}},
                    "group2": {"type": "array", "items": {"type": "number"}}
                },
                "required": ["group1", "group2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compute_cohens_d",
            "description": "Compute effect size (Cohen's d) between two groups",
            "parameters": {
                "type": "object",
                "properties": {
                    "group1": {"type": "array", "items": {"type": "number"}},
                    "group2": {"type": "array", "items": {"type": "number"}}
                },
                "required": ["group1", "group2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compute_confidence_interval",
            "description": "Compute confidence interval for a sample group",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "array", "items": {"type": "number"}},
                    "confidence": {"type": "number", "default": 0.95}
                },
                "required": ["data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "describe_group",
            "description": "Summarize sample mean, std deviation, and count",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "array", "items": {"type": "number"}}
                },
                "required": ["data"]
            }
        }
    }
]

# -----------------------------
# Step 4: Review one chunk (with tool support)
# -----------------------------
def review_text_chunk(chunk, model="gpt-4o-mini"):
    system_prompt = """
    You are an expert AI research reviewer. Read the given chunk of a research paper and highlight weak arguments, unsupported claims, or flawed methodology.

    You can request tools to:
    - Recalculate p-values
    - Compute confidence intervals
    - Estimate effect size (Cohen's d)
    - Describe sample statistics

    Be rigorous and explain your reasoning. Conclude with suggestions and a verdict.
    """

    # First request
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chunk}
        ],
        tools=tools,
        tool_choice="auto"
    )

    message = response.choices[0].message

    # Tool use branch
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        tool_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        print(f"\n🔧 Tool called: {tool_name}\nArgs: {args}")

        tool_map = {
            "recalculate_p_value": recalculate_p_value,
            "compute_cohens_d": compute_cohens_d,
            "compute_confidence_interval": compute_confidence_interval,
            "describe_group": describe_group
        }

        result = tool_map[tool_name](**args)

        # Follow-up after tool use
        follow_up = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunk},
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(result)
                }
            ]
        )
        return follow_up.choices[0].message.content

    else:
        return message.content

# -----------------------------
# Step 5: Full paper review
# -----------------------------
def review_full_pdf(pdf_path):
    raw_text = extract_text_from_pdf(pdf_path)
    chunks = chunk_text(raw_text)

    print(f"\n📄 Extracted {len(chunks)} chunks from PDF\n")

    all_reviews = []
    for idx, chunk in enumerate(chunks):
        print(f"\n🔍 Reviewing Chunk {idx + 1}/{len(chunks)}...")
        review = review_text_chunk(chunk)
        all_reviews.append(f"### Chunk {idx + 1} Review\n{review}")

    full_review = "\n\n".join(all_reviews)
    return full_review

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Review an academic paper PDF for weak arguments.")
    parser.add_argument("pdf_path", type=str, help="Path to the research paper PDF")
    args = parser.parse_args()

    review_output = review_full_pdf(args.pdf_path)

    print("\n✅ Final Aggregated Review:\n")
    print(review_output)

    with open("paper_review_output.md", "w") as f:
        f.write(review_output)

    print("\n📝 Review saved to paper_review_output.md")
