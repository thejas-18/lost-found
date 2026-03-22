import ollama
import json


MODEL = "mistral"


def generate_verification_questions(item_title, description):

    prompt = f"""
You are an AI verification system.

Item: {item_title}
Description: {description}

Generate 5 short questions to verify ownership.

Return ONLY JSON list.

Example:
["What color was the item?","Any brand logo?","Where exactly did you lose it?"]
"""

    try:

        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response["message"]["content"]

        questions = json.loads(content)

        return questions

    except:

        return [
            "What color was the item?",
            "Did it have any brand logo?",
            "Where exactly did you lose it?",
            "Did it have any scratches or marks?",
            "Any unique feature?"
        ]


def verify_claim(description, answers):

    prompt = f"""
Item description:
{description}

User answers:
{answers}

Evaluate ownership likelihood.

Return ONLY JSON.

Format:

{{
"score": number 0-100,
"decision": "likely owner | suspicious | false claim"
}}
"""

    try:

        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response["message"]["content"]

        result = json.loads(content)

        return result

    except:

        return {
            "score": 0,
            "decision": "unable to verify"
        }