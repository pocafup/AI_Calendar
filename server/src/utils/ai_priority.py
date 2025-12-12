import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")


def compute_ai_priority_score(event_name: str, event_description: str) -> float | None:
    """
    Semantic importance score: 0–100.
    User-assigned priority and due dates are handled separately.
    """
    if not openai.api_key:
        print("[AI] No OPENAI_API_KEY set; skipping AI scoring.")
        return None

    prompt = f"""
You are ranking tasks by how important or impactful they seem,
ignoring user labels and due dates.

Task title: {event_name}
Task description: {event_description}

Return ONLY a single number from 0 to 100 (no text), where:
- 90–100 = extremely important
- 70–89  = important
- 40–69  = moderate
- 0–39   = minor
"""

    try:
        print(f"[AI] Scoring task: {event_name!r}")
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You score the semantic importance of tasks."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        text = resp.choices[0].message["content"].strip()
        print("[AI] Raw model output:", text)
        score = float(text)
        score = max(0.0, min(score, 100.0))
        print(f"[AI] Parsed score: {score}")
        return score
    except Exception as e:
        print("[AI] priority scoring error:", e)
        return None
