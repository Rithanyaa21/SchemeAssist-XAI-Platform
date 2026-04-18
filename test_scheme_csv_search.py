import pandas as pd
import re

CSV_FILE = "datas/myscheme_dataset.csv"


def clean_query(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def load_data():
    df = pd.read_csv(CSV_FILE)

    for col in df.columns:
        df[col] = df[col].fillna("").astype(str)

    return df


def score_scheme(row, query_words):
    score = 0

    searchable_text = " ".join([
        row["scheme_name"],
        row["category"],
        row["state"],
        row["target_group"],
        row["description"],
        row["eligibility"],
        row["benefits"]
    ]).lower()

    for word in query_words:
        if word in searchable_text:
            score += 2

        if word in row["category"].lower():
            score += 5

        if word in row["target_group"].lower():
            score += 4

        if word in row["scheme_name"].lower():
            score += 3

    return score


def search_schemes(query, df, top_n=5):
    query = clean_query(query)

    # query expansion
    synonyms = {
        "students": ["student", "school", "college", "education", "scholarship"],
        "farmer": ["farm", "farmers", "agriculture", "crop", "kisan"],
        "women": ["woman", "girl", "mother", "female", "widow"],
        "entrepreneur": ["business", "startup", "enterprise", "msme"],
        "disability": ["disabled", "handicap", "pwd"],
        "senior": ["old age", "elderly", "aged", "pension"],
        "poverty": ["bpl", "poor", "low income", "below poverty line"]
    }

    query_words = query.split()
    expanded_words = set(query_words)

    for word in query_words:
        for key, values in synonyms.items():
            if word in key or word in values:
                expanded_words.add(key)
                expanded_words.update(values)

    results = []

    for _, row in df.iterrows():
        score = score_scheme(row, expanded_words)
        if score > 0:
            results.append((score, row))

    results.sort(key=lambda x: x[0], reverse=True)

    return results[:top_n]


def print_results(results):
    if not results:
        print("\nNo relevant schemes found.")
        return

    print("\nTop matching schemes:\n")

    for i, (score, row) in enumerate(results, start=1):
        print(f"{i}. {row['scheme_name']}")
        print(f"   Category     : {row['category']}")
        print(f"   State        : {row['state']}")
        print(f"   Target Group : {row['target_group']}")
        print(f"   Benefits     : {row['benefits']}")
        print(f"   Eligibility  : {row['eligibility']}")
        print(f"   Source       : {row['official_source']}")
        print(f"   Match Score  : {score}")
        print("-" * 80)


if __name__ == "__main__":
    df = load_data()

    print("Scheme CSV chatbot test started...")

    while True:
        q = input("\nAsk about government schemes: ")

        if q.lower() == "exit":
            break

        results = search_schemes(q, df)
        print_results(results)