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
def check_compliance(uploaded_pdf_text):
    """Check if all required compliance information is present in the extracted text."""
    missing_compliance_items = []
    lowercased_text = uploaded_pdf_text.lower()

    for item, patterns in required_compliance_items.items():
        found = False
        for pattern in patterns:
            # Use regex for pattern matching, including email and phone number
            if re.search(pattern.lower(), lowercased_text):
                print(f"Matched '{item}' with pattern: {pattern}")  # Debug: Print matched pattern
                found = True
                break
        if not found:
            print(f"Could not find '{item}' in the text.")  # Debug: Print missing item
            missing_compliance_items.append(item)

    # Debugging: Print missing compliance items
    print("\n----- Missing Compliance Items -----")
    print(missing_compliance_items)

    if missing_compliance_items:
        # Format the missing items with commas
        missing_items_str = ", ".join(missing_compliance_items)
        return {
            'compliant': False,
            'compliance_check': f"❌ Compliance: Missing the following information: {missing_items_str}."
        }
    else:
        return {
            'compliant': True,
            'compliance_check': "✔ Compliance: All required information is present."
        }

# Upload API: Handles file upload and processing
@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save the file securely
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # Debug: Verify file is saved
    if not os.path.exists(file_path):
        return jsonify({"error": "File failed to save"}), 500

    # Process the uploaded file
    try:
        extracted_text = extract_text_from_pdf(file_path)
        process_uploaded_pdf(file_path, filename)

        # Check compliance
        compliance_check_result = check_compliance(extracted_text)

        return jsonify({
            "success": True, 
            "message": f"✅ PDF uploaded successfully: {filename}",
            "compliance_check": compliance_check_result['compliance_check']
        })
    except Exception as e:
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500

# Retrieve relevant chunks using similarity search
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
    data = request.get_json()
    user_question = data.get('message', '').strip()

    # Validate input
    if not isinstance(user_question, str) or not user_question:
        return jsonify({"error": "Invalid question format."}), 400

    # Retrieve relevant context
    retrieval_context = retrieve_relevant_context(user_question)
    context = "\n".join(retrieval_context)

    # Generate response with retrieved context
    response = llm.invoke([HumanMessage(content=f"Context:\n{context}\n\nQuestion: {user_question}\nAnswer:")])
    answer = response.content if response else "No relevant answer found."

    return jsonify({"response": answer, "retrieval_context": retrieval_context})

# Serve frontend page
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)