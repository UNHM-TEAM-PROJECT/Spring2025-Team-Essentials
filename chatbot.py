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
}





# Function to extract text from PDFs
def extract_text_from_pdf(pdf_path):
    text = ''
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ''
                if not page_text:  # Fallback to OCR if no text is extracted
                    page_image = page.to_image(resolution=300).original
                    page_text = pytesseract.image_to_string(Image.fromarray(page_image))
                text += page_text + "\n"

                # Extract tables as text
                tables = page.extract_table()
                if tables:
                    text += "\n\n" + "\n".join(
                        ["\t".join([str(cell) if cell is not None else '' for cell in row]) for row in tables if row]
                    ) + "\n"
    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {str(e)}")
        raise
    print(f"Extracted text from {pdf_path}:\n{text[:1000]}...")  # Debug: Print first 1000 chars
    return text

# Text chunking strategy
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,  # Reduced chunk size
    chunk_overlap=200,
    separators=["\n\n", "\n", " "]
)

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
def check_neche_compliance(professor_info):
    """
    Checks NECHE compliance by verifying that required professor details are provided.
    Required fields for compliance:
    - Email Address
    - Phone Number
    - Title or Rank
    - Department or Program Affiliation
    """
    missing_fields = []
    
    if not professor_info.get('Professor\'s Email Address') or professor_info['Professor\'s Email Address'] == "Not Found":
        missing_fields.append("Professor's Email Address")
    
    if not professor_info.get('Professor\'s Phone Number') or professor_info['Professor\'s Phone Number'] == "Not Found":
        missing_fields.append("Professor's Phone Number")
    
    if not professor_info.get('Title or Rank') or professor_info['Title or Rank'] == "Not Found":
        missing_fields.append("Title or Rank")
    
    if not professor_info.get('Department or Program Affiliation') or professor_info['Department or Program Affiliation'] == "Not Found":
        missing_fields.append("Department or Program Affiliation")
    
    compliance_status = "NECHE Compliant: All required information is present." if not missing_fields else f"Not NECHE Compliant: Missing the following information: {', '.join(missing_fields)}."
    
    return {
        "compliant": not missing_fields,
        "compliance_check": compliance_status,
        "missing_fields": missing_fields
    }



def extract_course_information(text):
    """
    Uses OpenAI to extract structured course and instructor details in JSON format.
    """
    prompt = f"""
    Extract the following course and instructor details from this text in a structured JSON format.

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
    "Location (Physical or Remote)": ""
    }}

    Text:
    {text}

    **Return only the JSON object. Do not add any extra text.**
    """

    response = llm.invoke([HumanMessage(content=prompt)])

    raw_text = response.content.strip()

    # Ensure OpenAI response is enclosed in `{}` for valid JSON
    if not raw_text.startswith("{"):
        raw_text = raw_text[raw_text.find("{"):]
    if not raw_text.endswith("}"):
        raw_text = raw_text[:raw_text.rfind("}") + 1]

    try:
        extracted_info = json.loads(raw_text)  # Convert response to JSON
    except json.JSONDecodeError:
        extracted_info = {"error": "Failed to parse OpenAI response"}

    return extracted_info


# Upload API: Handles file upload and processing
# Global variable to store the latest syllabus information
latest_syllabus_info = {}

@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    global latest_syllabus_info  # Ensure we update this global variable

    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    if not os.path.exists(file_path):
        return jsonify({"error": "File failed to save"}), 500

    try:
        # Extract text from the uploaded PDF
        extracted_text = extract_text_from_pdf(file_path)

        # Process the PDF and store embeddings
        process_uploaded_pdf(file_path, filename)

        # Extract structured course/instructor details
        extracted_info = extract_course_information(extracted_text)

        # Check NECHE compliance
        compliance_check_result = check_neche_compliance(extracted_info)

        # 🔹 **Ensure the latest syllabus info is correctly updated**
        latest_syllabus_info.clear()  # **Clear old data**
        latest_syllabus_info.update(extracted_info)  # **Update with new syllabus details**

        return jsonify({
            "success": True, 
            "message": f"✅ PDF uploaded successfully: {filename}",
            "extracted_information": extracted_info,  
            "compliance_check": compliance_check_result["compliance_check"],
            "missing_fields": compliance_check_result["missing_fields"]
        })

    except Exception as e:
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500


def retrieve_relevant_context(query):
    if db is None:
        return []
    
    results = db.similarity_search(query, k=10)  # Increase k to retrieve more chunks
    print(f"Retrieved context for query '{query}': {results}")  # Debug: Log retrieved chunks
    return [doc.page_content for doc in results]

# OpenAI Chat Model
llm = ChatOpenAI(
    model="gpt-4-turbo",
    openai_api_key=OPENAI_API_KEY,
    temperature=0,
    top_p=1
)

# Chatbot API: Handles user queries
@app.route('/ask', methods=['POST'])
def ask():
    global latest_syllabus_info  # Always fetch the latest uploaded syllabus
    data = request.get_json()
    user_question = data.get('message', '').strip().lower()

    # Predefined NECHE-specific responses
    predefined_responses = {
        "how can you help me": "I assist with NECHE compliance by checking if a syllabus meets the required guidelines.",
        "what do you do": "I verify whether a syllabus follows NECHE compliance requirements and identify any missing elements.",
        "what is your purpose": "I ensure that uploaded syllabi comply with NECHE standards by checking for necessary elements like instructor details, office hours, and contact information."
    }

    if user_question in predefined_responses:
        return jsonify({"response": predefined_responses[user_question]})

    # 🔹 **Retrieve the latest instructor information**
    if "who is the professor" in user_question or "who is the instructor" in user_question:
        instructor_name = latest_syllabus_info.get("Instructor Name", "Not Found")
        return jsonify({"response": f"The instructor listed in the most recent syllabus is {instructor_name}."})

    if "what is their email" in user_question or "professor's email" in user_question:
        email = latest_syllabus_info.get("Professor's Email Address", "Not Found")
        instructor_name = latest_syllabus_info.get("Instructor Name", "The professor")
        return jsonify({"response": f"{instructor_name}'s email is {email}."})

    if "what is their phone number" in user_question or "professor's phone" in user_question:
        phone_number = latest_syllabus_info.get("Professor's Phone Number", "Not Found")
        instructor_name = latest_syllabus_info.get("Instructor Name", "The professor")
        return jsonify({"response": f"{instructor_name}'s phone number is {phone_number}."})

    # Otherwise, use OpenAI response
    response = llm.invoke([
        HumanMessage(content=f"{PROMPT_TEMPLATE}\n\nUser Question: {user_question}")
    ])

    return jsonify({"response": response.content})


# Serve frontend page
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8005)