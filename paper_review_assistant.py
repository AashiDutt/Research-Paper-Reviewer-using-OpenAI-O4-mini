import os
import openai
import base64
import json
from statistics_helper import recalculate_p_value

openai.api_key = os.getenv("OPENAI_API_KEY")

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def review_paper_with_response_api(image_path):
    base64_image = encode_image(image_path)

    # Replace with the latest model that supports images and function calls (e.g., gpt-4o)
    model = "gpt-4o"

    # system_prompt = """
    # You are a helpful AI paper reviewer. Carefully analyze the provided experiment table image from a research paper.
    
    # Detect if:
    # - Sample sizes are too small (<3)
    # - Standard deviations or variances are missing
    # - P-values or confidence intervals are absent
    # - Claims of superiority are unsupported

    # You may ask to recalculate statistical significance using a helper function `recalculate_p_value`.
    # """

    system_prompt = """
        You are a highly analytical and objective AI Paper Reviewer Assistant, helping evaluate the scientific validity of experimental results shown in a research paper table image.

        You will be given a figure (typically a table) containing research results such as performance metrics, ablations, model comparisons, dataset statistics, or runtime/memory tradeoffs. Your job is to review and flag issues, omissions, or unsupported claims.

        Perform the following analysis on the table:

        1. **Data Reporting Quality**
        - Is the number of trials or sample size reported? Flag if it's too small (<3) or missing.
        - Are standard deviations, confidence intervals, or any variability measures provided?
        - Is statistical significance reporting present (e.g., p-values or confidence intervals)?

        2. **Claims of Superiority**
        - If the table implies one method/model is better, check whether it's backed by statistical or practical evidence.
        - Call out unsupported claims or lack of comparative rigor.

        3. **Completeness & Clarity**
        - Are essential baselines included?
        - Are ablations provided (if relevant)?
        - Are any columns/metrics ambiguous or lacking units?

        4. **Optional Tool Usage**
        - If a p-value calculation or confidence interval is needed, and raw values are provided (e.g., [0.91, 0.92]), you may call available tools such as `recalculate_p_value`, `compute_confidence_interval`, or `compute_cohens_d`.

        5. **Fairness and Reproducibility**
        - If the comparison includes very different models, datasets, or parameter counts, flag if the comparison may be unfair or misleading.

        Be objective. If the table is clear, statistically sound, and conclusions are justified, say so. Otherwise, suggest what should be improved to make the analysis rigorous and reproducible.
    """


    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Please review this experiment table image:"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}",
                        "detail": "auto"
                    }
                }
            ]
        }
    ]

    # tools = [
    #     {
    #         "type": "function",
    #         "function": {
    #             "name": "recalculate_p_value",
    #             "description": "Compute p-value given two sample groups",
    #             "parameters": {
    #                 "type": "object",
    #                 "properties": {
    #                     "group1": {
    #                         "type": "array", "items": {"type": "number"}
    #                     },
    #                     "group2": {
    #                         "type": "array", "items": {"type": "number"}
    #                     }
    #                 },
    #                 "required": ["group1", "group2"]
    #             }
    #         }
    #     }
    # ]

    tools = [
    {
        "type": "function",
        "function": {
            "name": "recalculate_p_value",
            "description": "Calculate p-value given two sample groups",
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
            "description": "Calculate effect size (Cohen’s d) between two groups",
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
            "description": "Compute confidence interval for a single group",
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
            "description": "Summarize mean, std-dev, and sample size of a group",
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


    # Make the first call
    response = openai.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    response_message = response.choices[0].message

    # If the model calls the tool
    if response_message.tool_calls:
        tool_call = response_message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        p_val = recalculate_p_value(args["group1"], args["group2"])

        # Send the result back to the model
        follow_up = openai.chat.completions.create(
            model=model,
            messages=messages + [
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": "recalculate_p_value",
                    "content": f"Calculated p-value: {p_val:.4f}"
                }
            ]
        )

        return follow_up.choices[0].message.content
    else:
        return response_message.content


if __name__ == "__main__":
    # image_path = "/Users/aashidutt/Desktop/o4_mini_demo/img1.png"
    image_path = "/Users/aashidutt/Desktop/o4_mini_demo/img2.png"
    result = review_paper_with_response_api(image_path)
    print("🔍 Review Result:\n", result)
