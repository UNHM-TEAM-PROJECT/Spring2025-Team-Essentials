import json
import os
import re
import pdfplumber
import zipfile
import tempfile

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
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from email.mime.application import MIMEApplication
from io import BytesIO
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

latest_syllabus_info = {}

# Define the cache for extracted information
extracted_info_cache = {}

SENDER_EMAIL = "Essentials2025UNH@gmail.com"
SENDER_APP_PASSWORD = "prpa flfb znbk oglt"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Define the custom prompt template for friendly, conversational tone
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
    model="gpt-3.5-turbo",
    openai_api_key=OPENAI_API_KEY,
    temperature=0,
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
        db = None

initialize_chroma()

# Compliance Criteria: Key Information to Check
required_compliance_items = {
    "Title or Rank": [
        r"(?i)\b(professor|Professor|assistant professor|associate professor|full professor|senior lecturer|lecturer|instructor|adjunct|faculty|teaching fellow|grad assistant)\b",
        r"(?i)\b(ph\.?d|phd|dr\.||Professor|professor)\b",
        r"(?i)\b(professor\s+[a-zA-Z]+(?:\s+[a-zA-Z]+)*,\s*ph\.?d)\b",
        r"(?i)\b([a-zA-Z]+\s+[a-zA-Z]+(?:\s+[a-zA-Z]+)*\s*(professor|ph\.?d))\b",
    ],
    "Instructor Name": [
        r"(?i)\b(name|instructor|dr\.|mr\.|ms\.|mrs\.)[:\-]?\s*([a-zA-Z]+(?:\s+[a-zA-Z]+)+)(?=,|\s|$)",
        r"(?i)^[a-zA-Z]+(?:\s[a-zA-Z]+)+$"
    ],
    "Department or Program Affiliation": [
        r"(?i)\b(department|program|school|college|division|faculty|institute)\b\s*(of|for)?\s*[a-zA-Z]+",
        r"(?i)\b(affiliated with|affiliation|under)\b\s*[a-zA-Z\s]+",
    ],
    "Preferred Contact Method": [
        r"(contact method|preferred contact|contact information|office hours|email|phone)"
    ],
    "Professor's Email Address": [
        r"(?i)(email|E-mail|contact)\s*:\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?=.*(professor|instructor|faculty|contact))",
        r"(?i)(professor|instructor|faculty)\s*[:-]?\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?=\s*\(?(professor|instructor|faculty|contact)\)?)"
    ],
    "Professor's Phone Number": [
        r"(?i)(phone|office information|land line|office phone|contact|cell|direct)\s*[:\-]?\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        r"\(\d{3}\)\s*\d{3}[-.\s]?\d{4}(?=\s*\(?(office|phone|cell|contact|direct|land line)\)?)",
        r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b(?=.*(professor|phone|cell|instructor|office hours|land line|office information))",
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
        r"(?i)\b(course\s+learning\s+outcomes|student\s+learning\s+outcomes|SLOs|learning\s+objectives)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(students\s+will(?:\s+be\s+able\s+to)?)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
    ],
    "Credit Hour Workload": [
        r"(?i)\b(workload|credit\s+hour\s+expectations|credit\s+hours)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(minimum\s+45\s+hours\s+per\s+credit|total\s+workload|time\s+commitment|academic\s+work\s+requirement)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(course\s+workload|time\s+spent\s+per\s+credit\s+hour|study\s+hours\s+per\s+week)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(federal\s+definition\s+of\s+a\s+credit\s+hour|weekly\s+engagement\s+expectations)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Assignments & Delivery": [
        r"(?i)\b(assignments\s+&\s+delivery|types|graded\s+work)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(assignments|exams|projects|quizzes)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
    ],
    "Grading Procedures & Final Grade Scale": [
        r"(?i)\b(grading\s+procedures\s+&\s+final\s+grade\s+scale|graded\s+work)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(grade\s+scale|grading\s+policy)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
    ],
    "Assignment Deadlines & Policies": [
        r"(?i)\b(expectations\s+regarding\s+assignment\s+deadlines|assignment\s+deadlines\s+&\s+policies)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(deadlines|late\s+work)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
    ],
    "Course Number and Title": [
        r"(?i)\b(BIOL\s+414\s+LM2\s+Laboratory)\b",
        r"(?i)\b(course\s+number|course\s+title|course\s+name|course\s+code)\b\s*[:\-]?\s*([A-Z]+\s+\d+\.\w+\s+[^:]+)",
    ],
    "Number of Credits/Units (include a link to the federal definition of a credit hour)": [
        r"(?i)\b(credits|credit\s+hours|number\s+of\s+credits|units|federal\s+definition\s+of\s+a\s+credit\s+hour)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(credit\s+hour\s+policy)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Modality/Meeting Time and Place": [
        r"(?i)\b(modality|meeting\s+time|meeting\s+place|class\s+schedule|class\s+time|location|online|in-person|hybrid|remote|class\s+meeting)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Semester/Term (and start/end dates)": [
        r"(?i)\b(semester|term|start\s+date|end\s+date|academic\s+term|academic\s+year)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Program Accreditation Info": [
        r"(?i)\b(accreditation\s+requirements?|program\s+accreditation|additional\s+program\s+requirements)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(required\s+for\s+accreditation|meets\s+standards\s+of\s+.*accrediting\s+body)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(this\s+course\s+is\s+(designed|aligned)\s+to\s+meet\s+.*program\s+requirements)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(required\s+for\s+(ABET|ACEN|CACREP|AACSB|NCATE|CCNE|program-level\s+accreditation))\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(additional\s+information\s+(for|related\s+to)\s+program\s+accreditation)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Department/Program": [
        r"(?i)\b(department|program|school|college|division|faculty|institute)\b\s*(of|for)?\s*[a-zA-Z]+",
        r"(?i)\b(affiliated with|affiliation|under)\b\s*[a-zA-Z\s]+"
    ],
    "Format (e.g., lecture plus lab/discussion etc.)": [
        r"(?i)\b(course\s+format|class\s+format|mode\s+of\s+instruction|lecture\s+plus\s+lab|discussion\s+based|seminar|hybrid|in-person|online|laboratory)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Course Description (minimum course catalog description)": [
        r"(?i)\b(course\s+description|course\s+summary|course\s+overview|introduction\s+to\s+the\s+course)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(this\s+course\s+(covers|introduces|examines|explores|is\s+designed\s+to))\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Sequence of Course Topics and Important Dates": [
        r"(?i)\b(lab\s+schedule|course\s+schedule|sequence\s+of\s+course\s+topics)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(schedule\s+of\s+topics|important\s+dates)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Required/Recommended Textbook (or other source for course reference information)": [
        r"(?i)\b(required\s+texts?|textbooks?|recommended\s+books?|course\s+readings?|assigned\s+books?|learning\s+resources)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(this\s+course\s+uses|the\s+required\s+book\s+is|you\s+must\s+read|textbook\s+requirement)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Other Required/Recommended Materials (e.g., software, clicker remote, etc.)": [
        r"(?i)\b(required\s+materials|recommended\s+materials|course\s+materials|equipment|supplies|hardware|software|required\s+tools|resources\s+needed)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(you\s+will\s+need\s+to\s+bring|must\s+have\s+access\s+to|clicker|calculator|online\s+tools|learning\s+management\s+system|dissection\s+kits|lab\s+coats|protective\s+gear|lab\s+equipment|required\s+supplies|essential\s+materials)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(lab\s+coats|dissection\s+kits|safety\s+gear|required\s+tools|mandatory\s+equipment)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Technical Requirements": [
        r"(?i)\b(technical\s+requirements)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(students\s+must\s+have)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Attendance": [
        r"(?i)\b(attendance\s+policy|attendance\s+requirements|absence\s+policy|participation\s+and\s+attendance|class\s+preparation\s+and\s+attendance\s+policy)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(students\s+must\s+attend|mandatory\s+attendance|attendance\s+is\s+expected)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Academic Integrity/Plagiarism/AI": [
        r"(?i)\b(academic\s+honesty|academic\s+integrity|plagiarism)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(use\s+of\s+automated\s+writing\s+tools|ai\s+tools)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ],
    "Course Prerequisites": [
        r"(?i)\b(prerequisites?|pre[-\s]?reqs?)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(required\s+prior\s+coursework|prior\s+completion\s+of)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(you\s+must\s+have\s+(completed|taken)|must\s+complete|should\s+have\s+taken)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(this\s+course\s+(requires|assumes|expects)\s+(knowledge|completion|background|understanding)\s+of)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)",
        r"(?i)\b(students\s+should\s+be\s+(familiar|comfortable)\s+with)\b\s*[:\-]?\s*([\s\S]+?)(?=\n\n|\Z)"
    ]
}

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

import multiprocessing

def process_page(page):
    page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ''
    if not page_text:
        page_image = page.to_image(resolution=150).original
        page_text = pytesseract.image_to_string(Image.fromarray(page_image), config="--psm 3")
    return page_text

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

processed_results = {}  # 🔁 GLOBAL dictionary to store all file data

@app.route('/send_email', methods=['POST'])
def send_email():
    try:
        data = request.get_json()
        filename = data.get('filename')
        to_email = data.get('to', "SJ1203@usnh.edu")
        subject = data.get('subject', f'Syllabus Compliance Report - {filename}')
        body = data.get('body', '')

        if not filename or filename not in processed_results:
            return jsonify({"error": "No valid syllabus data to share. Please upload a file first."}), 400

        extracted_info = processed_results[filename]['extracted_information']

        required_fields = [
            "Instructor Name", "Title or Rank", "Department or Program Affiliation", "Preferred Contact Method",
            "Email Address", "Phone Number", "Office Address", "Office Hours", "Location (Physical or Remote)",
            "Course SLOs", "Credit Hour Workload", "Assignments & Delivery", "Grading Procedures & Final Grade Scale",
            "Assignment Deadlines & Policies"
        ]
        minimum_fields = [
            "Course Number and Title", "Number of Credits/Units (include a link to the federal definition of a credit hour)",
            "Modality/Meeting Time and Place", "Semester/Term (and start/end dates)", "Department/Program",
            "Format (e.g., lecture plus lab/discussion etc.)", "Course Description (minimum course catalog description)",
            "Sequence of Course Topics and Important Dates", "Required/Recommended Textbook (or other source for course reference information)",
            "Other Required/Recommended Materials (e.g., software, clicker remote, etc.)", "Technical Requirements",
            "Attendance", "Academic Integrity/Plagiarism/AI"
        ]
        optional_fields = [
            "Course Prerequisites", "Simultaneous 700/800 Course Designation", "University Requirements",
            "Teaching Assistants (Names and Contact Information)"
        ]
        all_fields = required_fields + minimum_fields + optional_fields

        # Course details parsing
        course_title_raw = extracted_info.get("Course Number and Title", "Not Found")
        course_id = ""
        course_name = course_title_raw
        if course_title_raw != "Not Found":
            parts = course_title_raw.split(" ")
            if len(parts) >= 2 and re.match(r'^[A-Z]{2,}\d{2,}', parts[0] + parts[1]):
                course_id = parts[0] + " " + parts[1]
                course_name = " ".join(parts[2:])
            else:
                course_id = course_title_raw
        semester = extracted_info.get("Semester/Term (and start/end dates)", "Not Found")
        if semester != "Not Found":
            semester = semester.split(" ")[0]
        instructor = extracted_info.get("Instructor Name", "Not Found")

        # Generate PDF with ReportLab
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=30, bottomMargin=30, leftMargin=30, rightMargin=30)
        elements = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=20, spaceAfter=10, alignment=1)  # Centered
        detail_style = ParagraphStyle('Detail', parent=styles['Normal'], fontSize=12, spaceAfter=6, alignment=1)  # Centered
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003591')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 14),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#f5f5f5')),
            ('BACKGROUND', (1, 1), (1, -1), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ])

        # Heading
        elements.append(Paragraph("Syllabus Compliance Report", title_style))

        # Course details
        course_details = []
        if course_id != "Not Found":
            course_details.append(f"Course ID: {course_id}")
        if course_name != "Not Found":
            course_details.append(f"Course Name: {course_name}")
        if semester != "Not Found":
            course_details.append(f"Semester: {semester}")
        if instructor != "Not Found":
            course_details.append(f"Instructor Name: {instructor}")

        if course_details:
            for detail in course_details:
                elements.append(Paragraph(detail, detail_style))
        else:
            elements.append(Paragraph("No course details available", detail_style))

        # Table
        table_data = [["Syllabus Items", "Syllabus Details"]]
        for field in all_fields:
            value = extracted_info.get(field, "Not Found")
            if field in optional_fields and value == "Not Found":
                continue
            field_label = field
            if field in required_fields:
                field_label = f"<b>{field}</b>"
            elif field in optional_fields:
                field_label = f"<i>{field}</i>"
            value_text = f"<font color=red><b>Not Found</b></font>" if value == "Not Found" else value.replace("\n", "<br />")
            table_data.append([Paragraph(field_label, styles['Normal']), Paragraph(value_text, styles['Normal'])])

        table = Table(table_data, colWidths=[180, 360])
        table.setStyle(table_style)
        elements.append(table)

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()

        # Send email
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        attachment = MIMEApplication(pdf_data, _subtype="pdf")
        attachment.add_header('Content-Disposition', 'attachment', filename=f"{filename}_NECHE_Report.pdf")
        msg.attach(attachment)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

        return jsonify({"success": True, "message": f"Email sent with {filename} NECHE report!"})

    except Exception as e:
        return jsonify({"error": f"Failed to send email: {str(e)}"}), 500

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
    Checks NECHE compliance by verifying required syllabus details and returns exact extracted text.
    """
    required_fields = [
        "Instructor Name", "Title or Rank", "Department or Program Affiliation", "Preferred Contact Method",
        "Email Address", "Phone Number", "Office Address", "Office Hours", "Location (Physical or Remote)",
        "Course SLOs", "Credit Hour Workload", "Assignments & Delivery", "Grading Procedures & Final Grade Scale",
        "Assignment Deadlines & Policies", "Course Number and Title",
        "Number of Credits/Units (include a link to the federal definition of a credit hour)",
        "Modality/Meeting Time and Place", "Semester/Term (and start/end dates)", "Department/Program",
        "Format (e.g., lecture plus lab/discussion etc.)", "Course Description (minimum course catalog description)",
        "Sequence of Course Topics and Important Dates", "Required/Recommended Textbook (or other source for course reference information)",
        "Other Required/Recommended Materials (e.g., software, clicker remote, etc.)", "Technical Requirements",
        "Attendance", "Academic Integrity/Plagiarism/AI"
    ]

    # Identify missing fields
    missing_fields = [field for field in required_fields if course_info.get(field) in ["Not Found", "", None]]

    # Build compliance message with exact extracted text
    compliance_message = "NECHE Compliance Check Results:\n"
    for field in required_fields:
        value = course_info.get(field, "Not Found")
        compliance_message += f"{field}: {value}\n"

    # Add missing fields summary if any
    if missing_fields:
        compliance_message += "\nThe syllabus is not compliant. Missing or incomplete information:\n"
        for field in missing_fields:
            compliance_message += f"- {field}\n"
    else:
        compliance_message += "\nThe syllabus is compliant with all required NECHE information present."

    # Special check for credit hour link
    credit_hour_field = "Number of Credits/Units (include a link to the federal definition of a credit hour)"
    if credit_hour_field in course_info:
        if "https://catalog.unh.edu/undergraduate/academic-policies-procedures/credit-hour-policy/" not in course_info[credit_hour_field]:
            if credit_hour_field not in missing_fields:
                missing_fields.append(credit_hour_field)
                compliance_message += "Missing link to the federal definition of a credit hour. Here is the link: https://catalog.unh.edu/undergraduate/academic-policies-procedures/credit-hour-policy/\n"

    print(f"🔍 Compliance Check Debug: {compliance_message}")
    return {
        "compliant": not missing_fields,
        "compliance_check": compliance_message,
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
    global extracted_info_cache
    formatted_text = format_text_as_bullets(text)
    
    # Generate a unique key for the document based on its content
    import hashlib
    doc_key = hashlib.md5(formatted_text.encode('utf-8')).hexdigest()
    
    # Check if the document has been processed before
    if doc_key in extracted_info_cache:
        print(f"Using cached extraction for document with key {doc_key}")
        return extracted_info_cache[doc_key]
    
    # Pre-extract with regex to assist LLM
    pre_extracted = {}
    for field, patterns in required_compliance_items.items():
        for pattern in patterns:
            match = re.search(pattern, formatted_text, re.MULTILINE | re.DOTALL)
            if match:
                print(f"✅ Match found for '{field}': {match.group()}")
                start = match.start()
                end = formatted_text.find("\n\n", start)
                if end == -1:
                    end = len(formatted_text)
                pre_extracted[field] = formatted_text[start:end].strip()
                print(f"🔍 Pre-extracted '{field}': {pre_extracted[field]}")
                break
    
        # Normalize "Title or Rank" to "Professor" if applicable
        if "Title or Rank" in pre_extracted:
            title_text = pre_extracted["Title or Rank"]
            if "professor" in title_text.lower() or "ph.d" in title_text.lower():
                pre_extracted["Title or Rank"] = "Professor"
        
        if field not in pre_extracted:
            pre_extracted[field] = "Not Found"

    prompt = f"""
You are a strict NECHE syllabus compliance inspector.

Your task is to extract all the following fields from the syllabus content exactly as written, without summarizing, modifying, or adding any phrases that reference other sections, such as "See," "Refer to," "Check," "Consult," "In the syllabus," "See Assignments section," "See Grading section," or similar. For each field:
- Return the exact text if found in the syllabus.
- Return "Not Found" if the field is completely missing or if the text contains any reference to another section.
- Output must be a clean JSON object — no extra comments or text.

Syllabus text:
{formatted_text}

Return JSON with these fields:
{json.dumps({
    "Instructor Name": "",
    "Title or Rank": "",
    "Department or Program Affiliation": "",
    "Preferred Contact Method": "",
    "Email Address": "",
    "Phone Number": "",
    "Office Address": "",
    "Office Hours": "",
    "Location (Physical or Remote)": "",
    "Course SLOs": "",
    "Credit Hour Workload": "",
    "Assignments & Delivery": "",
    "Grading Procedures & Final Grade Scale": "",
    "Assignment Deadlines & Policies": "",
    "Course Number and Title": "",
    "Number of Credits/Units (include a link to the federal definition of a credit hour)": "",
    "Modality/Meeting Time and Place": "",
    "Semester/Term (and start/end dates)": "",
    "Department/Program": "",
    "Format (e.g., lecture plus lab/discussion etc.)": "",
    "Course Description (minimum course catalog description)": "",
    "Sequence of Course Topics and Important Dates": "",
    "Required/Recommended Textbook (or other source for course reference information)": "",
    "Other Required/Recommended Materials (e.g., software, clicker remote, etc.)": "",
    "Technical Requirements": "",
    "Attendance": "",
    "Academic Integrity/Plagiarism/AI": "",
    "Course Prerequisites": "",
    "Simultaneous 700/800 Course Designation": "",
    "University Requirements": "",
    "Teaching Assistants (Names and Contact Information)": ""
}, indent=2)}
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    raw_text = response.content.strip()

    if not raw_text.startswith("{"):
        raw_text = raw_text[raw_text.find("{"):]
    if not raw_text.endswith("}"):
        raw_text = raw_text[:raw_text.rfind("}") + 1]
    
    try:
        extracted_info = json.loads(raw_text)
        # Post-process to ensure no vague responses
        all_fields = [
            "Instructor Name", "Title or Rank", "Department or Program Affiliation", "Preferred Contact Method",
            "Email Address", "Phone Number", "Office Address", "Office Hours", "Location (Physical or Remote)",
            "Course SLOs", "Credit Hour Workload", "Assignments & Delivery", "Grading Procedures & Final Grade Scale",
            "Assignment Deadlines & Policies", "Course Number and Title",
            "Number of Credits/Units (include a link to the federal definition of a credit hour)",
            "Modality/Meeting Time and Place", "Semester/Term (and start/end dates)", "Department/Program",
            "Format (e.g., lecture plus lab/discussion etc.)", "Course Description (minimum course catalog description)",
            "Sequence of Course Topics and Important Dates", "Required/Recommended Textbook (or other source for course reference information)",
            "Other Required/Recommended Materials (e.g., software, clicker remote, etc.)", "Technical Requirements",
            "Attendance", "Academic Integrity/Plagiarism/AI", "Course Prerequisites", "Simultaneous 700/800 Course Designation",
            "University Requirements", "Teaching Assistants (Names and Contact Information)"
        ]
        for field in all_fields:
            if field not in extracted_info or not extracted_info[field] or extracted_info[field].strip() == "":
                extracted_info[field] = "Not Found"
            else:
                # Check for vague responses and mark as "Not Found"
                value = extracted_info[field].lower()
                vague_phrases = ["refer to", "see the", "check the", "consult the", "in the syllabus", "see assignments section", "see grading section", "see", "see course description section", "see graded work section", "see class preparation and attendance policy section", "see lab schedule section", "see technical requirements section", "see academic honesty section"]
                if any(phrase in value for phrase in vague_phrases):
                    extracted_info[field] = "Not Found"
        
        # Normalize keys
        if "Professor's Email Address" in extracted_info:
            extracted_info["Email Address"] = extracted_info.pop("Professor's Email Address")
        if "Professor's Phone Number" in extracted_info:
            extracted_info["Phone Number"] = extracted_info.pop("Professor's Phone Number")
        
        # Sanitize department field
        department_text = extracted_info.get("Department or Program Affiliation", "").lower()
        if any(x in department_text for x in ["university", "unh", "manchester"]):
            extracted_info["Department or Program Affiliation"] = "Not Found"
        
        # Convert all values to strings and ensure no truncation
        for key, value in extracted_info.items():
            if not isinstance(value, str):
                extracted_info[key] = json.dumps(value)
            # Remove any trailing incomplete sentences
            extracted_info[key] = extracted_info[key].strip()
            if extracted_info[key].endswith("..."):
                extracted_info[key] = "Not Found"

        # Cache the extracted information
        extracted_info_cache[doc_key] = extracted_info

    except Exception as e:
        print("❌ Failed to parse response:", e)
        extracted_info = {"error": "Failed to parse OpenAI response"}
        extracted_info_cache[doc_key] = extracted_info

    return extracted_info

from langchain.text_splitter import RecursiveCharacterTextSplitter

# ✅ Define the text splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", " "]
)

@app.route('/upload', methods=['POST'])
def upload_file():
    global latest_syllabus_info, processed_results

    if 'file' not in request.files:
        print("⚠️ No file provided in request")
        return jsonify({"error": "No file provided"}), 400

    files = request.files.getlist('file')
    if not files or all(f.filename == '' for f in files):
        print("⚠️ No valid files selected")
        return jsonify({"error": "No selected file"}), 400

    results = []
    processed_results.clear()

    try:
        required_fields = [
            "Instructor Name", "Title or Rank", "Department or Program Affiliation",
            "Preferred Contact Method", "Email Address", "Phone Number",
            "Office Address", "Office Hours", "Location (Physical or Remote)",
            "Course SLOs", "Credit Hour Workload", "Assignments & Delivery",
            "Grading Procedures & Final Grade Scale", "Assignment Deadlines & Policies",
            "Course Number and Title", "Number of Credits/Units (include a link to the federal definition of a credit hour)",
            "Modality/Meeting Time and Place", "Semester/Term (and start/end dates)", "Department/Program",
            "Format (e.g., lecture plus lab/discussion etc.)", "Course Description (minimum course catalog description)",
            "Sequence of Course Topics and Important Dates", "Required/Recommended Textbook (or other source for course reference information)",
            "Other Required/Recommended Materials (e.g., software, clicker remote, etc.)", "Technical Requirements",
            "Attendance", "Academic Integrity/Plagiarism/AI"
        ]
        optional_fields = [
            "Course Prerequisites", "Simultaneous 700/800 Course Designation", "University Requirements",
            "Teaching Assistants (Names and Contact Information)"
        ]

        for file in files:
            filename = secure_filename(file.filename)
            if not allowed_file(filename):
                print(f"⚠️ Invalid file type for {filename}")
                continue

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            print(f"📄 Saved file: {filename}")

            if filename.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        zip_ref.extractall(temp_dir)
                        for root, _, zip_files in os.walk(temp_dir):
                            for name in zip_files:
                                if name.lower().endswith(('.pdf', '.docx')):
                                    inner_path = os.path.join(root, name)
                                    text = extract_text_from_pdf(inner_path) if name.endswith('.pdf') else extract_text_from_docx(inner_path)
                                    if not text:
                                        print(f"⚠️ No text extracted from {name}")
                                        continue
                                    print(f"📝 Extracted text from {name}: {text[:100]}...")
                                    extracted_info = extract_course_information(text)
                                    # Additional check for vague phrases
                                    vague_phrases = ["refer to", "see the", "check the", "consult the", "in the syllabus", "see assignments section", "see grading section", "see"]
                                    for field in required_fields + optional_fields:
                                        value = extracted_info.get(field, "").strip()
                                        if not value or value.lower() in ["n/a", "na", "not applicable", "none"] or any(phrase in value.lower() for phrase in vague_phrases):
                                            extracted_info[field] = "Not Found"
                                    for key, value in extracted_info.items():
                                        extracted_info[key] = str(value) if not isinstance(value, str) else value
                                    compliance = check_neche_compliance(extracted_info)
                                    processed_results[name] = {
                                        "extracted_information": extracted_info,
                                        "compliance_check": compliance["compliance_check"],
                                        "missing_fields": compliance["missing_fields"]
                                    }
                                    results.append({
                                        "filename": name,
                                        "extracted_information": extracted_info,
                                        "compliance_check": compliance["compliance_check"],
                                        "missing_fields": compliance["missing_fields"]
                                    })
                os.remove(file_path)
                continue

            if filename.endswith('.pdf'):
                extracted_text = extract_text_from_pdf(file_path)
            elif filename.endswith('.docx'):
                extracted_text = extract_text_from_docx(file_path)
            else:
                print(f"⚠️ Unsupported file type for {filename}")
                os.remove(file_path)
                continue

            if not extracted_text:
                print(f"⚠️ No text extracted from {filename}")
                os.remove(file_path)
                continue

            print(f"📝 Extracted text from {filename}: {extracted_text[:100]}...")
            extracted_info = extract_course_information(extracted_text)
            # Additional check for vague phrases
            vague_phrases = ["refer to", "see the", "check the", "consult the", "in the syllabus", "see assignments section", "see grading section", "see"]
            for field in required_fields + optional_fields:
                value = extracted_info.get(field, "").strip()
                if not value or value.lower() in ["n/a", "na", "not applicable", "none"] or any(phrase in value.lower() for phrase in vague_phrases):
                    extracted_info[field] = "Not Found"
            for key, value in extracted_info.items():
                extracted_info[key] = str(value) if not isinstance(value, str) else value
            compliance_check_result = check_neche_compliance(extracted_info)
            latest_syllabus_info.clear()
            latest_syllabus_info.update(extracted_info)
            processed_results[filename] = {
                "extracted_information": extracted_info,
                "compliance_check": compliance_check_result["compliance_check"],
                "missing_fields": compliance_check_result["missing_fields"]
            }
            results.append({
                "filename": filename,
                "extracted_information": extracted_info,
                "compliance_check": compliance_check_result["compliance_check"],
                "missing_fields": compliance_check_result["missing_fields"]
            })
            os.remove(file_path)

        if not results:
            print("⚠️ No valid files processed")
            return jsonify({"error": "No valid files processed inside the upload"}), 400

        return jsonify({
            "success": True,
            "message": f"Processed {len(results)} file(s) successfully",
            "results": results
        })

    except Exception as e:
        print(f"❌ Error processing upload: {str(e)}")
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500

@app.route('/ask', methods=['POST'])
def ask():
    global latest_syllabus_info
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "No message provided"}), 400

        message = data.get('message', '').strip().lower()

        # Casual responses for greetings and small talk
        casual_responses = {
            "hey": "Hey! How’s your day going?",
            "hello": "Hello! Hope you're having a great day.",
            "hi": "Hi there! How can I assist you today?",
            "how are you": "I'm doing great! Thanks for asking. How about you?",
            "what's up": "Not much, just here to assist with NECHE compliance! What’s up with you?",
            "who are you": "I'm your assistant for NECHE syllabus compliance. I help check syllabus requirements and guide you on accreditation standards.",
            "what do you do": "I assist with NECHE compliance by checking syllabi for required information. Let me know if you need help with that!"
        }

        # Handle casual greetings
        if message in casual_responses:
            return jsonify({"response": casual_responses[message]})

        # Handle professor-related questions
        if "who is the professor" in message or "professor's name" in message:
            professor_name = latest_syllabus_info.get("Instructor Name", "Not Found")
            if professor_name == "Not Found":
                return jsonify({"response": "No professor information found in the most recent syllabus. Please upload a valid syllabus."})
            return jsonify({"response": f"The professor listed in the most recent syllabus is {professor_name}."})

        # Handle compliance check questions
        if "is this syllabus compliant" in message:
            compliance_result = check_neche_compliance(latest_syllabus_info)
            return jsonify({"response": compliance_result["compliance_check"]})

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

        is_neche_related = any(keyword in message for keyword in neche_keywords) or any(inquiry in message for inquiry in general_inquiries)

        # Construct the prompt for other NECHE-related questions
        if is_neche_related or latest_syllabus_info:
            syllabus_summary = "\n".join([f"{k}: {v}" for k, v in latest_syllabus_info.items()])
            prompt = PROMPT_TEMPLATE + f"""
            Latest NECHE Compliance Information (from uploaded syllabus):
            {json.dumps(latest_syllabus_info, indent=2)}

            User's Question: {message}

            Response Guidelines:
            - Provide the exact extracted text from the syllabus for the requested field.
            - Do not use phrases like "Refer to the syllabus" or "See the syllabus."
            - If the information is missing, state "Not Found" for that field.
            - Keep responses short, professional, and NECHE-focused.
            """
        else:
            prompt = """
            I specialize in NECHE syllabus compliance.
            I can check if your syllabus meets NECHE standards, identify missing elements, 
            and guide you on compliance improvements.

            Please ask about syllabus requirements, instructor details, grading policies, or coursework submissions.
            """

        # Invoke LLM
        response = llm.invoke([HumanMessage(content=prompt)])
        return jsonify({"response": response.content.strip()})

    except Exception as e:
        print(f"Error processing question: {str(e)}")
        return jsonify({"error": f"Failed to process question: {str(e)}"}), 500
    
from flask import send_file, Flask, request, jsonify, render_template

@app.route("/download_all_reports_zip", methods=["GET"])
def download_all_reports_zip():
    zip_path = "/path/to/generated/NECHE_All_Reports.zip"  # Update this path accordingly
    return send_file(zip_path, as_attachment=True)

# Serve frontend page
@app.route('/', methods=['GET','POST'])
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8001)