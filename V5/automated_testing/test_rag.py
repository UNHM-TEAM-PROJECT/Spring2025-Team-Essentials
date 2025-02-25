import os
import json
import fitz  # PyMuPDF
import re

# Folder containing PDFs
PDF_FOLDER = "Syllabi_Sp2025"
OUTPUT_FOLDER = "outputs/compliance_reports"

# Ensure output folder exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Compliance Criteria: Key Information to Check
required_compliance_items = {
    "Instructor Name": [
        r"(instructor|name|senior lecturer|professor|assistant professor|associate professor|dr\.|mr\.|ms\.)[:\-]?", 
        r"^[a-zA-Z]+(?:\s[a-zA-Z]+)+$"
    ],
    "Title or Rank": [
        r"(title|rank|professor|dr\.|mr\.|ms\.|senior lecturer|assistant professor|associate professor|lecturer|instructor)"
    ],
    "Department or Program Affiliation": [
        r"(department|program affiliation|school of|college of)"
    ],
    "Preferred Contact Method": [
        r"(contact method|preferred contact|contact information|office hours|email|phone)"
    ],
    "Email Address": [
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    ],
    "Phone Number": [r"\b\d{3}[-.\s]??\d{3}[-.\s]??\d{4}\b", r"\(\d{3}\)\s*\d{3}[-.\s]??\d{4}"],
    "Office Address": [
        r"(office address|address|office|room|building)"
    ],
    "Office Hours": [
        r"(office hours|hours|availability|by appointment)"
    ],
    "Location (Physical or Remote)": [
        r"(physical location|remote|by appointment|location|online|in person|zoom|in-person|outside his office)"
    ],
    "Course Number": [
        r"\b(comp|COMP)[\s-]?\d{3}\b"  
    ]
}

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = "\n".join([page.get_text("text") for page in doc])
        return text
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return ""

# Function to check compliance
def check_compliance(text):
    compliance_results = {}
    missing_items = []
    for key, patterns in required_compliance_items.items():
        found = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                found.extend(matches)
        if found:
            compliance_results[key] = found
        else:
            compliance_results[key] = "Not Found"
            missing_items.append(key)
    
    compliance_results["Compliance Status"] = "Compliant" if not missing_items else f"Missing: {', '.join(missing_items)}"
    return compliance_results

# Process PDFs and check compliance
def process_pdfs():
    if not os.path.exists(PDF_FOLDER):
        print(f"Error: Folder '{PDF_FOLDER}' not found!")
        return
    
    for filename in os.listdir(PDF_FOLDER):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(PDF_FOLDER, filename)
            print(f"Processing: {filename}")
            text = extract_text_from_pdf(pdf_path)
            compliance_result = check_compliance(text)
            output_file = os.path.join(OUTPUT_FOLDER, f"{filename}.json")
            with open(output_file, "w") as f:
                json.dump(compliance_result, f, indent=4)
            print(f"Compliance check completed for {filename}. Results saved in '{output_file}'")

# Run the compliance check
if __name__ == "__main__":
    process_pdfs()





