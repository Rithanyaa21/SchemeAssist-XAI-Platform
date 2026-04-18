import ollama  # kept (not used)

import re
from sentence_transformers import SentenceTransformer, util

print("Scheme chatbot started...")

# ✅ Load AI model
model = SentenceTransformer('all-MiniLM-L6-v2')


def clean_text(text):

    patterns = [
        r"are you sure.*?sign out",
        r"something went wrong.*?ok",
        r"sign in",
        r"cancel",
        r"feedback",
        r"check eligibility",
        r"apply now",
        r"frequently asked questions",
        r"sources and references",
        r"documents required",
        r"application process",
    ]

    text = text.lower()

    for pattern in patterns:
        text = re.sub(pattern, " ", text)

    # remove junk characters
    text = re.sub(r"[^a-z0-9₹.,\n ]", " ", text)

    # remove extra spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def load_schemes():
    with open("scheme_text_data.txt", "r", encoding="utf-8") as f:
        data = f.read()

    schemes = data.split("====================")

    schemes = [clean_text(s) for s in schemes if s.strip() != ""]

    return schemes


# ✅ Load once
SCHEMES = load_schemes()

# ✅ Create embeddings
scheme_embeddings = model.encode(SCHEMES, convert_to_tensor=True)


def search_schemes(query):

    query_embedding = model.encode(query, convert_to_tensor=True)

    scores = util.cos_sim(query_embedding, scheme_embeddings)[0]

    k = min(3, len(SCHEMES))
    top_results = scores.topk(k)

    results = []
    seen = set()

    for idx in top_results.indices:
        scheme = SCHEMES[int(idx)]
        if scheme not in seen:
            results.append(scheme)
            seen.add(scheme)

    return results


# ✅ NEW: Structured formatter (THIS FIXES YOUR MESSY OUTPUT)
def format_scheme_output(text):

    # Try extracting key parts
    name_match = re.search(r"([a-z0-9 %\-]+ scheme)", text)
    benefit_match = re.search(r"benefit[s]?(.*?)(eligibility|who can apply|$)", text)
    eligibility_match = re.search(r"eligibility(.*?)(benefit|who can apply|$)", text)

    name = name_match.group(1).title() if name_match else "Government Scheme"

    benefits = benefit_match.group(1).strip()[:200] if benefit_match else "Benefits information available."
    eligibility = eligibility_match.group(1).strip()[:200] if eligibility_match else "Check official eligibility criteria."

    # Clean again for safety
    benefits = re.sub(r"\s+", " ", benefits)
    eligibility = re.sub(r"\s+", " ", eligibility)

    formatted = f"""
### 🏷️ {name}

**📌 Eligibility:**
- {eligibility}

**💰 Benefits:**
- {benefits}

---
"""

    return formatted


def generate_answer(query):

    schemes = search_schemes(query)

    if not schemes:
        return "❌ No relevant schemes found."

    final_output = "## 📊 Relevant Government Schemes\n"

    for s in schemes:
        final_output += format_scheme_output(s)

    return final_output


if __name__ == "__main__":

    while True:

        q = input("\nAsk about government schemes: ")

        if q.lower() == "exit":
            break

        answer = generate_answer(q)

        print("\n", answer)