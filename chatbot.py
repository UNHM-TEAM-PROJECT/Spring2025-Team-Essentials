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
    model="gpt-4-turbo",  # Ensure you are using a valid OpenAI model
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
    "Course SLOs": [
        r"(?i)\b(course\s+learning\s+outcomes|student\s+learning\s+outcomes|SLOs)\b.*",
        r"(?i)\b(learning\s+objectives|outcomes|course\s+objectives|expected\s+learning\s+outcomes)\b.*",
        r"(?i)\b(this\s+course\s+aims\s+to|upon\s+successful\s+completion|students\s+will\s+be\s+able\s+to)\b.*",
        r"(?i)\b(key\s+competencies|learning\s+goals|by\s+the\s+end\s+of\s+this\s+course|core\s+learning\s+outcomes)\b.*"
    ],
    "Program SLOs": [
        r"(?i)\b(program\s+learning\s+outcomes|program\s+level\s+SLOs|PLOs)\b.*",
        r"(?i)\b(program\s+objectives|program\s+outcomes|degree\s+competencies|expected\s+program\s+outcomes)\b.*",
        r"(?i)\b(graduates\s+of\s+this\s+program\s+will|program\s+completion\s+requirements)\b.*",
        r"(?i)\b(by\s+completing\s+this\s+program|students\s+will\s+demonstrate|program\s+competencies)\b.*"
    ],
    "Credit Hour Workload": [
        r"(?i)\b(workload|credit\s+hour\s+expectations|credit\s+hours)\b.*",
        r"(?i)\b(minimum\s+45\s+hours\s+per\s+credit|total\s+workload|time\s+commitment|academic\s+work\s+requirement)\b.*",
        r"(?i)\b(course\s+workload|time\s+spent\s+per\s+credit\s+hour|study\s+hours\s+per\s+week)\b.*",
        r"(?i)\b(federal\s+definition\s+of\s+a\s+credit\s+hour|weekly\s+engagement\s+expectations)\b.*"
    ],
    "Assignments & Delivery": [
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
    ]
}









# Function to extract text from PDFs
def extract_text_from_pdf(pdf_path):
    text = ''
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ''

                # If no text extracted, use OCR
                if not page_text:
                    print(f"🔹 No direct text found on page {page.page_number}, using OCR...")
                    page_image = page.to_image(resolution=300).original
                    page_text = pytesseract.image_to_string(Image.fromarray(page_image), config="--psm 6")

                text += page_text + "\n"

    except Exception as e:
        print(f"⚠️ Error processing PDF: {str(e)}")
        return None

    return text if text.strip() else None  # Return None if text extraction fails

# Function to process an uploaded PDF
def process_uploaded_pdf(file_path, file_name):
    global db
    try:
        extracted_text = extract_text_from_pdf(file_path)
        print(f"Extracted text from {file_name}: {extracted_text[:100]}...")  # Debug: Print first 100 chars
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
        "Professor's Email Address",
        "Professor's Phone Number",
        "Office Address",
        "Office Hours",
        "Location (Physical or Remote)",
        "Course SLOs",
        "Program SLOs",
        "Credit Hour Workload",
        "Assignments & Delivery",
        "Grading Procedures & Final Grade Scale",
        "Assignment Deadlines & Policies"
    ]
    
    missing_fields = [field for field in required_fields if not course_info.get(field) or course_info[field] in ["Not Found", ""]]
    
    compliance_status = " NECHE Compliant: All required information is present." if not missing_fields else f" Not NECHE Compliant. Missing:\n" + "\n".join([f"- {field}" for field in missing_fields])

    print(f"🔍 Compliance Check Debug: {compliance_status}")  # Debugging Output

    return {
        "compliant": not missing_fields,
        "compliance_check": compliance_status,
        "missing_fields": missing_fields
    }


import json
from langchain.schema import HumanMessage
def extract_course_information(text):
    """
    Extracts structured course and instructor details in JSON format.
    """
    prompt = f"""
    Extract the following course and instructor details from this text in a structured JSON format.
    Ensure **Grading Procedures & Final Grade Scale** and **Assignment Deadlines & Policies** are included.

    JSON Structure:
    {{
    "Instructor Name": "",
    "Title or Rank": "",
    "Department or Program Affiliation": "",
    "Preferred Contact Method": "",
    "Professor's Email Address": "",
    "Professor's Phone Number": "",
    "Office Address": "",
    "Office Hours": "",
    "Location (Physical or Remote)": "",
    "Course SLOs": "",
    "Program SLOs": "",
    "Credit Hour Workload": "",
    "Assignments & Delivery": "",
    "Grading Procedures & Final Grade Scale": "",
    "Assignment Deadlines & Policies": ""
    }}

    Text:
    {text}

    **Return only the JSON object. No extra explanations. If a required field is missing, return `"Not Found"` explicitly.**
    """

    response = llm.invoke([HumanMessage(content=prompt)])
    raw_text = response.content.strip()

    # Ensure JSON format is valid
    if not raw_text.startswith("{"):
        raw_text = raw_text[raw_text.find("{"):]
    if not raw_text.endswith("}"):
        raw_text = raw_text[:raw_text.rfind("}") + 1]

    try:
        extracted_info = json.loads(raw_text)
        print(f"📊 Extracted Course Information: {json.dumps(extracted_info, indent=2)}")  # Debug: Print extracted info
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

@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
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
        extracted_text = extract_text_from_pdf(file_path)
        extracted_info = extract_course_information(extracted_text)

        # Ensure all required NECHE fields exist
        required_fields = [
            "Instructor Name", "Title or Rank", "Department or Program Affiliation",
            "Preferred Contact Method", "Professor's Email Address", "Professor's Phone Number",
            "Office Address", "Office Hours", "Location (Physical or Remote)",
            "Course SLOs", "Program SLOs", "Credit Hour Workload", "Assignments & Delivery",
            "Grading Procedures & Final Grade Scale", "Assignment Deadlines & Policies"
        ]
        
        # Fill missing fields with "Not Found"
        for field in required_fields:
            if field not in extracted_info or not extracted_info[field]:
                extracted_info[field] = "Not Found"

        # Perform NECHE compliance check
        compliance_check_result = check_neche_compliance(extracted_info)

        # Update latest syllabus info
        latest_syllabus_info.clear()
        latest_syllabus_info.update(extracted_info)

        return jsonify({
            "success": True,
            "message": f"✅ PDF uploaded successfully: {filename}",
            "extracted_information": extracted_info,
            "compliance_check": compliance_check_result["compliance_check"],
            "missing_fields": compliance_check_result["missing_fields"]
        })

    except Exception as e:
        return jsonify({"error": f"❌ Failed to process PDF: {str(e)}"}), 500


# Chatbot API: Handles user queries

@app.route('/ask', methods=['POST'])
def ask():
    global latest_syllabus_info
    data = request.get_json()
    user_question = data.get('message', '').strip()

    # If user asks about NECHE compliance, make it strict
    neche_keywords = [
        "neche", "syllabus", "compliance", "instructor", "credit hours",
        "grading policy", "program SLOs", "assignments", "office hours"
    ]

    is_neche_related = any(keyword in user_question.lower() for keyword in neche_keywords)

    # **1️⃣ If the question is about NECHE, use the NECHE-specific prompt**
    if is_neche_related:
        prompt = f"""
        You are a **friendly AI assistant** that helps users with **NECHE syllabus compliance**.
        🎯 **Your job:** Check syllabus requirements, explain NECHE policies, and answer compliance-related questions.
        
        **User's Question:** {user_question}
        """
    
    # **2️⃣ If it's a general question, let OpenAI answer naturally**
    else:
        prompt = f"""
        You are a **friendly AI assistant**. Answer like a helpful, conversational chatbot.
        - Keep responses **short, engaging, and natural**.
        - If the user asks casual questions like "How are you?" respond in a friendly way.
        - If asked about NECHE compliance, answer accurately.
        
        **User's Question:** {user_question}
        """

    try:
        response = llm.invoke([
            HumanMessage(content=prompt)
        ])

        return jsonify({"response": response.content})

    except Exception as e:
        return jsonify({"response": f"❌ OpenAI Error: {str(e)}"}), 500



# Serve frontend page
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)