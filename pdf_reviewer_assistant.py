import os
import fitz  # PyMuPDF
import json
import tiktoken
from openai import OpenAI
from statistics_helper import (
    recalculate_p_value,
    compute_cohens_d,
    compute_confidence_interval,
    describe_group
)

client = OpenAI()

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
def chunk_text(text, max_tokens=12000, model="o4-mini"):
    encoding = tiktoken.get_encoding("cl100k_base")  # Use GPT-4 compatible tokenizer
    tokens = encoding.encode(text)
    chunks = []

    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i + max_tokens]
        chunk_text = encoding.decode(chunk)
        chunks.append(chunk_text)

    return chunks

# -----------------------------
# Step 3: Tool mapping (function registry)
# -----------------------------
tool_function_map = {
    "recalculate_p_value": recalculate_p_value,
    "compute_cohens_d": compute_cohens_d,
    "compute_confidence_interval": compute_confidence_interval,
    "describe_group": describe_group,
}

# -----------------------------
# Step 4: Tool Mapping
# -----------------------------
tools = [
            {
                "type": "function",
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
            },
            {
                "type": "function",
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
            },
            {
                "type": "function",
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
            },
            {
                "type": "function",
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
        ]

# -----------------------------
# Step 5: Review one chunk (with tool support)
# -----------------------------
def review_text_chunk(chunk):
    try:
        response = client.responses.create(
            model="o4-mini",
            reasoning={"effort": "high"},
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert AI research reviewer. Read the given chunk of a research paper and highlight weak arguments, "
                        "unsupported claims, or flawed methodology. You can request tools to: Recalculate p-values, Compute confidence intervals, "
                        "Estimate effect size (Cohen's d), Describe sample statistics. Be rigorous and explain your reasoning. "
                        "Conclude with suggestions and a verdict."
                    )
                },
                {
                    "role": "user",
                    "content": chunk
                }
            ],
            tools = tools,

        )

        # Check for tool calls
        for item in response.output:
            if getattr(item, "type", None) == "function_call":
                fn_call = getattr(item, "function_call", {})
                fn_name = getattr(fn_call, "name", "")
                args = getattr(fn_call, "arguments", {})

                if fn_name in tool_function_map:
                    tool_result = tool_function_map[fn_name](**args)

                    # Send back tool result as continuation input
                    tool_response = client.responses.create(
                        model="o4-mini",
                        reasoning={"effort": "high"},
                        input=[
                            *response.output,
                            {
                                "role": "tool",
                                "name": fn_name,
                                "content": str(tool_result)
                            }
                        ],
                        max_output_tokens=3000
                    )

                    if hasattr(tool_response, "output_text") and tool_response.output_text:
                        return tool_response.output_text.strip()


        # If no tool was called, return original response
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text.strip()

        if response.status == "incomplete":
            reason = getattr(response.incomplete_details, "reason", "unknown")
            return f"⚠️ Incomplete response: {reason}"

        return "⚠️ No valid output returned by the model."

    except Exception as e:
        return f"❌ Error during chunk review: {e}"

# -----------------------------
# Step 6: Full paper review
# -----------------------------
def review_full_pdf(pdf_path):
    raw_text = extract_text_from_pdf(pdf_path)
    chunks = chunk_text(raw_text)

    print(f"\n📄 Extracted {len(chunks)} chunks from PDF\n")

    all_reviews = []
    for idx, chunk in enumerate(chunks):
        print(f"\n🔍 Reviewing Chunk {idx + 1}/{len(chunks)}...")
        review = review_text_chunk(chunk)

        formatted_review = f"""
### Chunk {idx + 1} Review
{review}
        """
        all_reviews.append(formatted_review)

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
