import os
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
    return text

# Text chunking strategy
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
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
        process_uploaded_pdf(file_path, filename)
    except Exception as e:
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500

    return jsonify({
        "success": True, 
        "message": f"✅ PDF uploaded successfully: {filename}"
    })

# Retrieve relevant chunks using similarity search
def retrieve_relevant_context(query):
    if db is None:
        return []
    
    results = db.similarity_search(query, k=5)
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
    response = llm.invoke([HumanMessage(content=f"{context}\n\nUser Question: {user_question}")])
    answer = response.content if response else "No relevant answer found."

    return jsonify({"response": answer, "retrieval_context": retrieval_context})

# Serve frontend page
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)