import json
import os
import re
import pdfplumber
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chat_models import ChatOpenAI
from langchain.schema import Document, HumanMessage
from PIL import Image
import pytesseract
import json
import os
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from docx import Document as DocxDocument

latest_syllabus_info = {}



#Define the custom prompt template for friendly, conversational tone
PROMPT_TEMPLATE = """
You are an AI assistant specializing in NECHE syllabus compliance verification. Your role is to help users check if a syllabus meets NECHE standards and provide extracted information about instructors and course details.

### Key Context Rules:

1. **For greetings:**
   - Only greet if the user's message is a greeting or they are starting a new conversation.
   - Example: "Hello! I assist with NECHE syllabus compliance. How can I help you today?"

2. **For NECHE compliance inquiries:**
   - If asked whether a syllabus is NECHE-compliant, check the extracted details from the uploaded PDF.
   - Clearly state missing details if compliance is not met.
   - Example:
     - **User:** "Is this syllabus NECHE compliant?"
     - **Assistant:** "Not NECHE Compliant: Missing the following information: Professor's Phone Number."

3. **For professor-specific inquiries:**
   - If the user asks for a professor's name, title, email, or other details, respond based on the most recently uploaded syllabus.
   - Example:
     - **User:** "Who is the professor?"
     - **Assistant:** "The professor listed in the most recent syllabus is Phillip Deen."
     - **User:** "What is their email?"
     - **Assistant:** "Phillip Deen's email is phillip.deen@unh.edu."

4. **For unrelated questions:**
   - If the question is not related to NECHE compliance or syllabus details, respond with:
     - "Sorry, I specialize in NECHE syllabus compliance. Please ask about syllabus requirements."

5. **Response Format:**
   - Keep answers **brief and focused**.
   - Avoid unnecessary formatting (no bold text, asterisks, or extra characters).
   - Use **natural and professional language**, similar to a compliance officer or faculty assistant.

6. **Supported NECHE Compliance Topics:**
   - NECHE syllabus requirements and missing elements.
   - Instructor details (name, title, department, email, phone, office hours).
   - Course-related details found in the syllabus.
   - How to correct non-compliant syllabi.

7. **Context Awareness:**
   - Track the details from the **most recent uploaded PDF**.
   - Recognize follow-up questions and answer accordingly.

Example Conversation:

- **User:** "Who is the professor?"
- **Assistant:** "The professor listed in the most recent syllabus is Phillip Deen."
- **User:** "What is their email?"
- **Assistant:** "Phillip Deen's email is phillip.deen@unh.edu."
- **User:** "Is this syllabus NECHE compliant?"
- **Assistant:** "Not NECHE Compliant: Missing the following information: Professor's Phone Number."

"""

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "uploads"
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Chroma vector store directory
persist_directory = 'db'
os.makedirs(persist_directory, exist_ok=True)

# OpenAI API Key
OPENAI_API_KEY = "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"

llm = ChatOpenAI(
    model="gpt-3.5-turbo",  # Ensure you are using a valid OpenAI model
    openai_api_key="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",  # 🔹 Replace with your actual API key
    temperature=0,  # Controls randomness (0 = more deterministic)
    top_p=1
)
# Load OpenAI Embeddings
embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=OPENAI_API_KEY)

# Initialize Chroma vector store
db = None

def initialize_chroma():
    global db
    if os.path.exists(os.path.join(persist_directory, "index")):
        db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
    else:
        db = None  # No database yet

initialize_chroma()

# Compliance Criteria: Key Information to Check
required_compliance_items = {
    "Instructor Name": [
        r"(instructor|name|senior lecturer|professor|assistant professor|associate professor|dr\.|mr\.|ms\.)[:\-]?", 
        r"^[a-zA-Z]+(?:\s[a-zA-Z]+)+$"
    ],
    "Title or Rank": [
        # Expanded patterns to include variations and abbreviations
        r"(?i)\b(title|rank|position|role)\b\s*[:-]?\s*",  # Matches "Title: Assistant Professor"
        r"(?i)\b(professor|dr|doctor|mr|ms|mrs|senior lecturer|lecturer|instructor|adjunct|faculty|adjunct)\b",
        r"(?i)\b(assistant professor|associate professor|full professor|teaching fellow|grad assistant)\b",
        r"(?i)\b(ph\.?d|m\.?sc|m\.?a|b\.?a)\b"  # Academic degrees often indicate rank
    ],
    "Department or Program Affiliation": [
        # Broader patterns to catch department/program mentions
        r"(?i)\b(department|program|school|college|division|faculty|institute)\b\s*(of|for)?\s*[a-zA-Z]+",  # Matches "Department of Computer Science"
        r"(?i)\b(affiliated with|affiliation|under)\b\s*[a-zA-Z\s]+",  # Matches "Affiliation: School of Engineering"
    ],
    "Preferred Contact Method": [
        r"(contact method|preferred contact|contact information|office hours|email|phone)"
    ],
    "Professor's Email Address": [
    r"(?i)(email|E-mail|contact)\s*:\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # Matches "Email: example@domain.com"
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?=.*(professor|instructor|faculty|contact))",  # Matches emails near "professor" or related terms
    r"(?i)(professor|instructor|faculty)\s*[:-]?\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # Matches "Professor: example@domain.com"
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?=\s*\(?(professor|instructor|faculty|contact)\)?)"  # Matches emails followed by "(professor)"
    ],

    # Professor-specific phone number 
    "Professor's Phone Number": [
    # Matches formats like "Phone: 123-456-7890", "Office Information: 603-641-4103"
    r"(?i)(phone|office information|land line|office phone|contact|cell|direct)\s*[:\-]?\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",  

    # Matches "(603) 641-4103" with optional office-related keywords
    r"\(\d{3}\)\s*\d{3}[-.\s]?\d{4}(?=\s*\(?(office|phone|cell|contact|direct|land line)\)?)",  

    # Matches numbers when preceded by "professor", "phone", "cell", "instructor", "office hours"
    r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b(?=.*(professor|phone|cell|instructor|office hours|land line|office information))",  

    # Matches numbers written without explicit labels but within NECHE-compliant sections
    r"(?i)(phone|office information|land line)[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}"
    ],

    
    "Office Address": [
        r"(office address|address|office|room|building)"
    ],
    "Office Hours": [
        r"(office hours|hours|availability|by appointment)"
    ],
    "Location (Physical or Remote)": [
        r"(physical location|remote|by appointment|location|online|in person|zoom|in-person|outside his office)"
    ],
    "Course Learning Outcomes": [
        r"(?i)\b(course\s+learning\s+outcomes|student\s+learning\s+outcomes|SLOs)\b.*",
        r"(?i)\b(learning\s+objectives|outcomes|course\s+objectives|expected\s+learning\s+outcomes)\b.*",
        r"(?i)\b(this\s+course\s+aims\s+to|upon\s+successful\s+completion|students\s+will\s+be\s+able\s+to)\b.*",
        r"(?i)\b(key\s+competencies|learning\s+goals|by\s+the\s+end\s+of\s+this\s+course|core\s+learning\s+outcomes)\b.*"
    ],
    "Credit Hour Workload": [
        r"(?i)\b(workload|credit\s+hour\s+expectations|credit\s+hours)\b.*",
        r"(?i)\b(minimum\s+45\s+hours\s+per\s+credit|total\s+workload|time\s+commitment|academic\s+work\s+requirement)\b.*",
        r"(?i)\b(course\s+workload|time\s+spent\s+per\s+credit\s+hour|study\s+hours\s+per\s+week)\b.*",
        r"(?i)\b(federal\s+definition\s+of\s+a\s+credit\s+hour|weekly\s+engagement\s+expectations)\b.*"
    ],
    "Coursework Types & Submission Methods": [
        r"(?i)\b(assignments|exams|projects|final\s+paper|graded\s+work)\b.*",
        r"(?i)\b(Canvas|Turnitin|remote\s+proctoring|on\s+paper|submission|assessment\s+methods)\b.*",
        r"(?i)\b(quiz|midterm|final\s+exam|group\s+project|presentation|lab\s+reports|discussion\s+posts)\b.*",
        r"(?i)\b(homework|problem\s+sets|case\s+studies|research\s+papers|class\s+participation)\b.*"
    ],
    
     "Grading Procedures & Final Grade Scale": [
        r"(?i)\b(grading\s+scale|grading\s+policy|final\s+grade|grade\s+calculation|evaluation\s+criteria)\b.*",
        r"(?i)\b(unh\s+grading\s+scale|grading\s+procedures|grade\s+distribution|grading\s+framework)\b.*",
        r"(?i)\b(letter\s+grades|gpa\s+calculation|grading\s+rubric|grading\s+criteria|grade\s+weights)\b.*",
        r"(?i)\b(scoring\s+system|pass\s+fail|weight\s+of\s+assignments|grading\s+guidelines)\b.*"
    ],
    "Assignment Deadlines & Policies": [
        r"(?i)\b(assignment\s+deadlines|due\s+dates|late\s+work|missed\s+assignments|submission\s+rules)\b.*",
        r"(?i)\b(late\s+submission\s+policy|makeup\s+assignments|deadline\s+extensions|submission\s+guidelines)\b.*",
        r"(?i)\b(late\s+penalty|missed\s+exams|penalty\s+for\s+late\s+work|grace\s+period|extension\s+requests)\b.*",
        r"(?i)\b(assignment\s+turn-in\s+policy|strict\s+submission\s+guidelines|deadline\s+requirements)\b.*"
    ],


    "Course Summary": [
        # General course description
        r"(?i)\b(course\s+summary|course\s+description|overview)\b.*",
        r"(?i)\b(this\s+course\s+provides|you\s+will\s+learn|students\s+will\s+explore)\b.*",
        r"(?i)\b(in\s+this\s+course\s+we\s+will|introduction\s+to)\b.*",

        # Format type: lecture, lab, discussion, hybrid, etc.
        r"(?i)\b(course\s+format|class\s+format|lecture\s+plus\s+lab|hybrid|discussion\s+based|seminar)\b.*",

        # Course and program SLOs
        r"(?i)\b(course\s+learning\s+outcomes|student\s+learning\s+outcomes|SLOs|program\s+learning\s+outcomes|PLOs)\b.*",
        r"(?i)\b(upon\s+successful\s+completion|students\s+will\s+be\s+able\s+to|learning\s+goals)\b.*",

        # Sequence of topics and important dates
        r"(?i)\b(schedule\s+of\s+topics|tentative\s+schedule|course\s+schedule|important\s+dates|week\s+by\s+week)\b.*",

        # Sensitive content disclosure
        r"(?i)\b(trigger\s+warning|sensitive\s+content|potentially\s+disturbing\s+material|controversial\s+topics)\b.*",
        r"(?i)\b(we\s+will\s+discuss\s+topics\s+that\s+may\s+be\s+upsetting)\b.*"
    ],

    "Learning Resources & Technical Requirements": [
    # Textbooks
    r"(?i)\b(required\s+texts?|textbooks?|recommended\s+books?|course\s+readings?)\b.*",
    r"(?i)\b(this\s+course\s+uses|the\s+required\s+book\s+is|you\s+must\s+read)\b.*",

    # Materials (hardware, software, etc.)
    r"(?i)\b(required\s+materials|recommended\s+materials|course\s+materials|clicker|laptop|software|required\s+tools)\b.*",
    r"(?i)\b(you\s+will\s+need\s+to\s+bring|must\s+have\s+access\s+to|supplies\s+required)\b.*",

    # Technical requirements
    r"(?i)\b(technical\s+requirements|required\s+software|internet\s+access|computer\s+requirements|system\s+requirements)\b.*",
    r"(?i)\b(zoom|teams|microsoft\s+office|browser\s+compatibility|virtual\s+labs)\b.*"
   ],

   "Course Policies": [
    # Attendance
    r"(?i)\b(attendance\s+policy|attendance\s+requirements|absence\s+policy|participation\s+and\s+attendance)\b.*",
    r"(?i)\b(students\s+must\s+attend|mandatory\s+attendance|attendance\s+is\s+expected)\b.*",

    # Academic integrity / plagiarism / AI use
    r"(?i)\b(academic\s+integrity|plagiarism|cheating|honor\s+code|academic\s+honesty)\b.*",
    r"(?i)\b(use\s+of\s+AI|ChatGPT|unauthorized\s+assistance|AI\s+tools\s+policy)\b.*",
    r"(?i)\b(students\s+are\s+expected\s+to\s+maintain\s+integrity|work\s+must\s+be\s+original)\b.*"
    ],
    "Course Number and Title": [
        r"(?i)\b(course\s+number|course\s+title|course\s+name|course\s+code)\b.*"
    ],
    "Number of Credits/Units (include a link to the federal definition of a credit hour)": [
        r"(?i)\b(credits|credit\s+hours|number\s+of\s+credits|units|federal\s+definition\s+of\s+a\s+credit\s+hour)\b.*"
    ],
    "Modality/Meeting Time and Place": [
        r"(?i)\b(modality|meeting\s+time|meeting\s+place|class\s+schedule|class\s+time|location|online|in-person|hybrid|remote)\b.*"
    ],
    "Semester/Term (and start/end dates)": [
        r"(?i)\b(semester|term|start\s+date|end\s+date|academic\s+term|academic\s+year)\b.*"
    ],

    "Program Accreditation Info": [
    r"(?i)\b(accreditation\s+requirements?|program\s+accreditation|additional\s+program\s+requirements)\b.*",
    r"(?i)\b(required\s+for\s+accreditation|meets\s+standards\s+of\s+.*accrediting\s+body)\b.*",
    r"(?i)\b(this\s+course\s+is\s+(designed|aligned)\s+to\s+meet\s+.*program\s+requirements)\b.*",
    r"(?i)\b(required\s+for\s+(ABET|ACEN|CACREP|AACSB|NCATE|CCNE|program-level\s+accreditation))\b.*",
    r"(?i)\b(additional\s+information\s+(for|related\s+to)\s+program\s+accreditation)\b.*"
]

    

    





}


    




ALLOWED_EXTENSIONS = {'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

import multiprocessing

def process_page(page):
    page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ''
    if not page_text:
        page_image = page.to_image(resolution=150).original
        page_text = pytesseract.image_to_string(Image.fromarray(page_image), config="--psm 3")
    return page_text

def extract_text_from_pdf(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
                text_list = pool.map(process_page, pdf.pages)
            return "\n".join(text_list).strip() if text_list else None
    except Exception as e:
        print(f"⚠️ Error processing PDF: {str(e)}")
        return None


# Function to extract text from PDFs
def extract_text_from_pdf(pdf_path):
    """
    Extracts full text from all pages of a PDF, ensuring accuracy.
    Uses OCR where needed and extracts tables properly.
    """
    extracted_text = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=2, y_tolerance=2)

                # ✅ If no direct text found, apply OCR
                if not page_text:
                    print(f"🔹 No direct text found on page {page.page_number}, using OCR...")
                    page_image = page.to_image(resolution=300).original
                    page_text = pytesseract.image_to_string(Image.fromarray(page_image), config="--psm 6")

                # ✅ Extract tables if present
                table_text = ""
                if page.extract_tables():
                    for table in page.extract_tables():
                        for row in table:
                            table_text += " | ".join(str(cell) if cell else "" for cell in row) + "\n"

                # ✅ Append extracted text + table text
                extracted_text.append(page_text.strip() + "\n" + table_text.strip())

    except Exception as e:
        print(f"⚠️ Error processing PDF: {str(e)}")
        return None

    return "\n".join(extracted_text).strip() if extracted_text else None

def extract_text_from_docx(docx_path):
    """
    Extracts structured text from a Word document, ensuring tables are formatted correctly.
    """
    text = []
    try:
        doc = DocxDocument(docx_path)
        
        # ✅ Extract paragraphs
        for para in doc.paragraphs:
            if para.text.strip():
                text.append(para.text.strip())

        # ✅ Extract tables properly
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text.append(row_text)

    except Exception as e:
        print(f"⚠️ Error processing DOCX: {str(e)}")
        return None

    return "\n".join(text).strip() if text else None

def process_uploaded_pdf(file_path, file_name):
    global db
    try:
        extracted_text = extract_text_from_pdf(file_path)
        print(f"Extracted text from {file_name}: {extracted_text[:1000]}...")  # Debug: Print first 100 chars
    except Exception as e:
        print(f"Error extracting text from {file_name}: {str(e)}")
        raise

    # Split into chunks
    chunks = text_splitter.split_text(extracted_text)
    documents = [Document(page_content=chunk, metadata={"source": file_name}) for chunk in chunks]

    # Reset the vector store and add new documents
    if db is not None:
        db.delete_collection()  # Clear existing documents
    db = Chroma.from_documents(documents, embedding=embeddings, persist_directory=persist_directory)
    db.persist()
    print(f"Vector store updated with {len(documents)} documents from {file_name}")  # Debug: Confirm update

# Function to check compliance
def check_neche_compliance(course_info):
    """
    Checks NECHE compliance by verifying required syllabus details are provided.
    """

    required_fields = [
        "Instructor Name",
        "Title or Rank",
        "Department or Program Affiliation",
        "Preferred Contact Method",
        "Email Address",  
        "Phone Number",   
        "Office Address",
        "Office Hours",
        "Location (Physical or Remote)",
        "Course Learning Outcomes",
        "Credit Hour Workload",
        "Coursework Types & Submission Methods",
        "Grading Procedures & Final Grade Scale",
        "Assignment Deadlines & Policies",
        "Course Description",
        "Course Format",
        "Course Topics and Schedule",
        "Sensitive Course Content",
        "Required/recommended textbook (or other source for course reference information)",
        "Other required/recommended materials (e.g., software, clicker remote, etc.)",
        "Technical Requirements",
        "Attendance",
        "Academic integrity/plagiarism/AI",
        "Program Accreditation Info",
        # New NECHE requirements
        "Course Number and Title",
        "Number of Credits/Units (include a link to the federal definition of a credit hour)",
        "Modality/Meeting Time and Place",
        "Semester/Term (and start/end dates)",
    ]

    # Identify missing fields
    missing_fields = [field for field in required_fields if not course_info.get(field) or course_info[field] in ["Not Found", ""]]

    # Special check for "Number of Credits/Units"
    credit_hour_field = "Number of Credits/Units (include a link to the federal definition of a credit hour)"
    if credit_hour_field in course_info:
        if "https://catalog.unh.edu/undergraduate/academic-policies-procedures/credit-hour-policy/" not in course_info[credit_hour_field]:
            if credit_hour_field not in missing_fields:
                missing_fields.append(credit_hour_field)

    # ✅ If all required information is present
    if not missing_fields:
        compliance_status = "The NECHE compliance check is complete. The syllabus is compliant and all required information is present."
    else:
        # ✅ Format missing fields list
        missing_fields_str = ", ".join(missing_fields)

        # ✅ Compliance message
        compliance_status = f"The NECHE compliance check is complete. The syllabus is not compliant. Here are the missing information: {missing_fields_str}."

        # Add specific message for the credit hour link
        if credit_hour_field in missing_fields:
            compliance_status += " Missing link to the federal definition of a credit hour. Here is the link: https://catalog.unh.edu/undergraduate/academic-policies-procedures/credit-hour-policy/"

    print(f"🔍 Compliance Check Debug: {compliance_status}")  # Debugging Output

    return {
        "compliant": not missing_fields,
        "compliance_check": compliance_status,  # ✅ Ensuring the correct message is used
        "missing_fields": missing_fields
    }
import re

def format_text_as_bullets(text):
    """
    Converts numbered lists (1., 2., 3.) into bullet points.
    Ensures readable formatting.
    """
    formatted_text = []
    sentences = text.split("\n")

    for sentence in sentences:
        sentence = sentence.strip()
        
        if sentence:
            # ✅ Remove numbers (1., 2., 3.) at the beginning
            sentence = re.sub(r"^\d+\.\s*", "• ", sentence)  # Changes "1. Example" → "• Example"
            formatted_text.append(sentence)  
    
    return "\n".join(formatted_text)
import json
from langchain.schema import HumanMessage


def extract_course_information(text):
    """
    Extracts structured course and instructor details in JSON format.
    Ensures full syllabus details are captured.
    """
    # ✅ Format text into bullet points before passing it to the LLM
    formatted_text = format_text_as_bullets(text)

    prompt = f"""
    You are an AI assistant specializing in NECHE syllabus compliance.
    
    **TASK:** Extract ALL relevant course and instructor details from the given text in a structured JSON format.
    - Ensure ALL fields are included.
    - If information is missing, return `"Not Found"` explicitly.
    - If paragraphs are long, break them into bullet points.
    - If information is in tables or lists, extract them properly.
    - For **Department or Program Affiliation**, only extract the actual department or program name.
    - Ignore any mention of **"University of New Hampshire"**, **"UNH"**, **"Manchester"**, or other **institution names**.

    **JSON Structure:**
    {{
    "Instructor Name": "",
    "Title or Rank": "",
    "Department or Program Affiliation": "",
    "Preferred Contact Method": "",
    "Email Address": "",
    "Phone Number": "",
    "Office Address": "",
    "Office Hours": "",
    "Location (Physical or Remote)": "",
    "Course Learning Outcomes": "",
    "Credit Hour Workload": "",
    "Coursework Types & Submission Methods": "",
    "Grading Procedures & Final Grade Scale": "",
    "Assignment Deadlines & Policies": "",
    "Course Description": "",
    "Course Format": "",
    "Course Topics and Schedule": "",
    "Sensitive Course Content": "",
    "Required/recommended textbook (or other source for course reference information)": "",
    "Other required/recommended materials (e.g., software, clicker remote, etc.)": "",
    "Technical Requirements": "",
    "Attendance": "",
    "Academic integrity/plagiarism/AI": "",
    "Program Accreditation Info": "",
    "Course Number and Title": "",
    "Number of Credits/Units (include a link to the federal definition of a credit hour)": "",
    "Modality/Meeting Time and Place": "",
    "Semester/Term (and start/end dates)": "",
    "Course Prerequisites": "",
    "Simultaneous 700/800 Course Designation": "",
    "University Requirements": "",
    "Teaching Assistants (Names and Contact Information)": ""
    }}

    **Full Extracted Text:**
    {formatted_text}

    **Return ONLY the JSON object. Do NOT add any explanations.**
    """

    response = llm.invoke([HumanMessage(content=prompt)])
    raw_text = response.content.strip()

    # ✅ Ensure JSON format is valid before parsing
    if not raw_text.startswith("{"):
        raw_text = raw_text[raw_text.find("{"):]
    if not raw_text.endswith("}"):
        raw_text = raw_text[:raw_text.rfind("}") + 1]

    try:
        extracted_info = json.loads(raw_text)

        # ✅ Standardizing extracted fields
        if "Professor's Email Address" in extracted_info:
            extracted_info["Email Address"] = extracted_info.pop("Professor's Email Address")
        if "Professor's Phone Number" in extracted_info:
            extracted_info["Phone Number"] = extracted_info.pop("Professor's Phone Number")

        # ✅ Cleaning up Department or Program Affiliation
        department_text = extracted_info.get("Department or Program Affiliation", "").lower()
        invalid_keywords = ["university of new hampshire", "unh", "manchester", "college", "school", "institute", "university"]
        if any(keyword in department_text for keyword in invalid_keywords):
            extracted_info["Department or Program Affiliation"] = "Not Found"

        # ✅ Convert all non-string values to strings
        for key, value in extracted_info.items():
            if not isinstance(value, str):
                extracted_info[key] = json.dumps(value)  # Convert lists/dictionaries to JSON strings

        print(f"📊 Extracted Course Information: {json.dumps(extracted_info, indent=2)}")  # Debugging Output
    except json.JSONDecodeError:
        extracted_info = {"error": "Failed to parse OpenAI response"}

    return extracted_info



from langchain.text_splitter import RecursiveCharacterTextSplitter

# ✅ Define the text splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,  # Adjust this value based on syllabus size
    chunk_overlap=200,
    separators=["\n\n", "\n", " "]
)

@app.route('/upload', methods=['POST'])
def upload_file():
    global latest_syllabus_info

    if 'file' not in request.files:
        return jsonify({"error": "❌ No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "❌ No selected file"}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    try:
        if filename.endswith('.pdf'):
            extracted_text = extract_text_from_pdf(file_path)
        elif filename.endswith('.docx'):
            extracted_text = extract_text_from_docx(file_path)
        else:
            return jsonify({"error": "❌ Unsupported file type"}), 400

        extracted_info = extract_course_information(extracted_text)

        # Ensure all required NECHE fields exist
        required_fields = [
            "Instructor Name", "Title or Rank", "Department or Program Affiliation",
            "Preferred Contact Method", "Email Address", "Phone Number",
            "Office Address", "Office Hours", "Location (Physical or Remote)",
            "Course Learning Outcomes", "Credit Hour Workload", "Coursework Types & Submission Methods",
            "Grading Procedures & Final Grade Scale", "Assignment Deadlines & Policies", "Course Description",
            "Course Format", "Course Topics and Schedule", "Sensitive Course Content",
            "Required/recommended textbook (or other source for course reference information)",
            "Other required/recommended materials (e.g., software, clicker remote, etc.)",
            "Technical Requirements", "Attendance", "Academic integrity/plagiarism/AI","Program Accreditation Info",
            "Course Number and Title", "Number of Credits/Units (include a link to the federal definition of a credit hour)",
            "Modality/Meeting Time and Place", "Semester/Term (and start/end dates)"
        ]

        # Optional fields
        optional_fields = [
            "Course Prerequisites",
            "Simultaneous 700/800 Course Designation",
            "University Requirements",
            "Teaching Assistants (Names and Contact Information)"
        ]

        # Fill missing fields with "Not Found" for required fields
        for field in required_fields:
            value = extracted_info.get(field, "").strip()
        if not value or value.lower() in ["n/a", "na", "not applicable", "none"]:
               extracted_info[field] = "Not Found"


        # Include optional fields only if they are present
        optional_info = {field: extracted_info[field] for field in optional_fields if field in extracted_info and extracted_info[field] != "Not Found"}

        # ✅ Flatten lists and dictionaries into plain text
        for key, value in extracted_info.items():
            # Convert lists to comma-separated strings
            if isinstance(value, list):
                extracted_info[key] = ", ".join(map(str, value))  # Ensure all elements are strings before joining
            # Convert dictionaries to space-separated strings of their values
            elif isinstance(value, dict):
                extracted_info[key] = " ".join(map(str, value.values()))  # Ensure all values are strings before joining
            # Convert other non-string types to strings
            elif not isinstance(value, str):
                extracted_info[key] = str(value)

        # Perform NECHE compliance check
        compliance_check_result = check_neche_compliance(extracted_info)

        # Update latest syllabus info
        latest_syllabus_info.clear()
        latest_syllabus_info.update(extracted_info)

        # Add optional fields to the response
        extracted_info.update(optional_info)

        return jsonify({
            "success": True,
            "message": f"✅ File uploaded successfully: {filename}",
            "extracted_information": extracted_info,
            "compliance_check": compliance_check_result["compliance_check"],
            "missing_fields": compliance_check_result["missing_fields"]
        })

    except Exception as e:
        return jsonify({"error": f"❌ Failed to process file: {str(e)}"}), 500 
    
# Chatbot API: Handles user queries
@app.route('/ask', methods=['POST'])
def ask():
    global latest_syllabus_info
    data = request.get_json()
    user_question = data.get('message', '').strip().lower()

    # Natural responses for greetings and casual questions
    casual_responses = {
        "hey": "Hey! How’s your day going?",
        "hello": "Hello! Hope you're having a great day.",
        "hi": "Hi there! How can I assist you today?",
        "how are you": "I'm doing great! Thanks for asking. How about you?",
        "what's up": "Not much, just here to assist with NECHE compliance! What’s up with you?",
        "who are you": "I'm your assistant for NECHE syllabus compliance. I help check syllabus requirements and guide you on accreditation standards.",
        "what do you do": "I assist with NECHE compliance by checking syllabi for required information. Let me know if you need help with that!"
    }

    # Check if user's question is casual/small talk
    if user_question in casual_responses:
        return jsonify({"response": casual_responses[user_question]})

    # NECHE compliance-related keywords
    neche_keywords = [
        "neche", "syllabus", "compliance", "instructor", "credit hours",
        "grading policy", "program SLOs", "assignments", "office hours",
        "submission", "deadlines", "policies", "assessment", "course objectives"
    ]

    # General inquiries about bot's purpose
    general_inquiries = [
        "how can you assist me", "what can you do for me", "tell me about yourself", "what is your purpose"
    ]

    is_neche_related = any(keyword in user_question for keyword in neche_keywords) or any(inquiry in user_question for inquiry in general_inquiries)

    if is_neche_related or latest_syllabus_info:
        prompt = f"""
        You are a **NECHE syllabus compliance chatbot**.
        🎯 **Your job:** Verify syllabus compliance, identify missing NECHE requirements, and guide users on necessary improvements.

        **User's Question:** {user_question}

        **Latest NECHE Compliance Information (from uploaded syllabus):**
        {json.dumps(latest_syllabus_info, indent=2)}

        **Response Guidelines:**
        - If the syllabus **is missing required elements**, list what is missing and how to correct it.
        - If the syllabus **meets NECHE compliance**, confirm compliance and summarize why.
        - **For general inquiries (e.g., "Tell me about yourself," "What is your purpose?"),** respond naturally and then transition into explaining that you specialize in NECHE compliance.
        - Keep responses **short, professional, and NECHE-focused**.
        """

    else:
        # Redirect ALL unrelated questions back to NECHE compliance
        prompt = """
        I specialize in NECHE syllabus compliance.
        I can check if your syllabus meets NECHE standards, identify missing elements, 
        and guide you on compliance improvements.

        Please ask about syllabus requirements, instructor details, grading policies, or coursework submissions.
        """

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return jsonify({"response": response.content})

    except Exception as e:
        return jsonify({"response": f"❌ OpenAI Error: {str(e)}"}), 500


# Serve frontend page
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)