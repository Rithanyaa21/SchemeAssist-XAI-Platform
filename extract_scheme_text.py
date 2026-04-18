import fitz
import os
import re

pdf_folder = "gov_myscheme/text_data"
output_file = "scheme_text_data.txt"

all_text = []
count = 0

for file in os.listdir(pdf_folder)[:50]:   # limit for demo

    if file.endswith(".pdf"):

        path = os.path.join(pdf_folder, file)

        try:
            doc = fitz.open(path)

            text = ""

            for page in doc[:5]:   # read first 5 pages only
                text += page.get_text()

            # basic cleaning
            text = re.sub(r"\s+", " ", text)

            # keep only important sections
            if "Eligibility" in text or "Benefits" in text:
                all_text.append(text)
                count += 1

        except:
            pass


with open(output_file, "w", encoding="utf-8") as f:
    for scheme in all_text:
        f.write(scheme)
        f.write("\n\n====================\n\n")

print("Extraction complete.")
print("Schemes processed:", count)