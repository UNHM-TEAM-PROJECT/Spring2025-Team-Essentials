"""

File: chatbot.py
Authors: 
Contributors: 
Date: 

"""

import os
from flask import Flask, request, jsonify, render_template
import pdfplumber
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain.memory import ConversationBufferMemory
import re
import json
from datetime import datetime
import hashlib
from langchain.chat_models import ChatOpenAI
from pymongo import MongoClient

# Flask app initialization
app = Flask(__name__)
# Route for rendering the homepage
@app.route('/')
def home():
    return render_template('index.html')

# Path to the JSON file for storing chat history and conversation memory
chat_history_file = 'chat_history.json'
conversation_memory_file = 'conversation_memory.json'

# OpenAI API key for accessing embeddings and language models
apikey = os.getenv("OPENAI_API_KEY")
# Initialize the chat history and conversation memory files if they don't exist
def initialize_chat_history_file():
    if not os.path.exists(chat_history_file):
        with open(chat_history_file, 'w') as file:
            json.dump([], file)
    if not os.path.exists(conversation_memory_file):
        with open(conversation_memory_file, 'w') as file:
            json.dump([], file)

# Load general chat history from a JSON file
def load_chat_history():
    if os.path.exists(chat_history_file):
        try:
            with open(chat_history_file, 'r') as file:
                data = json.load(file)
                return data if data else []
        except json.JSONDecodeError:
            return []
    return []

# Save general chat history to a JSON file
def save_chat_history(chat_history):
    with open(chat_history_file, 'w') as file:
        json.dump(chat_history, file, indent=4)

# Load conversation memory from a JSON file for persistent memory across sessions
def load_conversation_memory():
    if os.path.exists(conversation_memory_file):
        try:
            with open(conversation_memory_file, 'r') as file:
                data = json.load(file)
                return data if data else []
        except json.JSONDecodeError:
            return []
    return []

# Save conversation memory to a JSON file after each interaction
def save_conversation_memory(memory):
    with open(conversation_memory_file, 'w') as file:
        json.dump(memory, file, indent=4)

# Generate a consistent hash for a question
def get_question_hash(question):
    normalized_question = " ".join(question.lower().split())
    return hashlib.md5(normalized_question.encode()).hexdigest()

# Retrieve a cached response based on question hash
def get_cached_response(question_hash):
    chat_history = load_chat_history()
    for entry in chat_history:
        if entry.get("question_hash") == question_hash:
            return entry.get("bot_response")
    return None

# Save a new interaction to the chat history with question hash
def save_interaction_to_json(user_question, bot_response):
    chat_history = load_chat_history()
    question_hash = get_question_hash(user_question)
    new_chat = {
        "user_question": user_question,
        "bot_response": bot_response,
        "timestamp": datetime.now().isoformat(),
        "question_hash": question_hash
    }
    # Check if question exists and update if necessary
    for entry in chat_history:
        if entry.get("question_hash") == question_hash:
            entry.update(new_chat)
            break
    else:
        chat_history.append(new_chat)
    
    save_chat_history(chat_history)

# Extract text and table data from PDF using pdfplumber
def extract_text_from_pdf(pdf_path):
    text = ''
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ''  # Extract text from page
            text += page_text + "\n"  # Add newline for separation
            tables = page.extract_table()
            if tables:
                text += "\n\n" + "\n".join(
                    ["\t".join([str(cell) if cell is not None else '' for cell in row]) for row in tables if row]
                ) + "\n"
    return text

# Handle multiple PDFs in a directory
def extract_texts_from_multiple_pdfs(pdf_directory):
    documents = []
    for pdf_file in os.listdir(pdf_directory):
        if pdf_file.endswith(".pdf"):
            pdf_path = os.path.join(pdf_directory, pdf_file)
            pdf_text = extract_text_from_pdf(pdf_path)
            documents.append(Document(page_content=pdf_text, metadata={"source": pdf_file}))
    return documents

# Directory containing PDFs to be processed

pdf_directory = 'C:/Users/Punnulatha/Downloads/Team-essential/data'
documents = extract_texts_from_multiple_pdfs(pdf_directory)

# Split documents into chunks for better context management
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    separators=["\n\n", "\n", " "]
)

# Custom function to split documents based on weeks
def custom_split_documents_by_weeks(documents):
    chunks = []
    for doc in documents:
        if "<TABLE_START>" in doc.page_content:
            week_sections = re.split(r"(Week \d+)", doc.page_content)
            current_week = None
            
            for part in week_sections:
                week_match = re.match(r"Week \d+", part)
                if week_match:
                    current_week = part.strip()
                elif current_week:
                    chunks.append(Document(page_content=f"{current_week}\n{part.strip()}", metadata=doc.metadata))
        else:
            chunked_texts = text_splitter.split_text(doc.page_content)
            for chunk in chunked_texts:
                chunks.append(Document(page_content=chunk, metadata=doc.metadata))
    return chunks

# Split documents into chunks with table handling by weeks
texts = custom_split_documents_by_weeks(documents)

# Load OpenAI Embeddings for Semantic Search
embeddings = OpenAIEmbeddings(model="text-embedding-ada-002", openai_api_key=apikey)

# Create Chroma Index for Vector Store using OpenAI Embeddings
persist_directory = 'db'
if os.path.exists(persist_directory):
    os.system(f"rm -rf {persist_directory}")

db = Chroma.from_documents(documents=texts, embedding=embeddings, persist_directory=persist_directory)

# Create a retriever with OpenAI embeddings
retriever = db.as_retriever(search_type="similarity", search_kwargs={"k":10})

#  Set up conversational memory and load past memory
previous_memory = load_conversation_memory()
memory = ConversationBufferMemory(
    memory_key="chat_history", 
    return_messages=True
)
for item in previous_memory:
    # Load past messages into memory
    memory.chat_memory.add_user_message(item["user"])
    memory.chat_memory.add_ai_message(item["assistant"])

# Define the custom prompt template for friendly, conversational tone
PROMPT_TEMPLATE = """
You are an AI assistant for UNH's computing internship courses. Your tone should be friendly and natural, like a conversation with a professor or teaching assistant, ensuring students feel comfortable and supported in their inquiries.

Key Context Rules:
For greeeting:
1.Only respond with a greeting if the user's message is a greeting or they're starting a new conversation. For example: 
   "Hello! I am the internship chatbot for UNH. How may I assist you today?"
   Otherwise, respond directly to their question.

2. For subsequent messages in the same conversation, focus on answering the specific question without repeating greetings.

3. For out-of-context questions:
   Respond with: "Sorry, I don’t have information about that question. Feel free to ask me anything related to the UNH internship program."

4. Answer Format:
   - Keep responses brief and focused (2-3 sentences maximum for technical concepts).
   - Avoid using bold asterix (`*`) or styled formatting in your answers. Present all information in plain text.
   - Include course codes when relevant.
   - Provide contact information when appropriate.
   - Maintain a friendly, conversational tone as if speaking to a student in person.

5. Response Topics:
   - Details of internship courses (COMP690, COMP890, COMP891, COMP892, COMP893) and credit requirements.
   - Steps for registration, instructor permission, and handling late registration due to mid-semester internship offers.
   - Weekly log requirements, final report structure, and hours needed per credit.
   - CPT/OPT authorization steps and required documents for F-1 students.
   - Attendance policies and rules for excused absences and late submissions.
   - Career resources, including resume coaching, Handshake, and online job portals.
   - Use of Scrum and Agile project management frameworks in internships.
   - Formatting and grading criteria for the final report submission.
   - UNH policies on academic integrity and confidentiality reporting.
   - Support services for international students and confidential counseling resources.
   - Access to library resources, research assistance, and study spaces.

6. Context Awareness:
   - Use {chat_history} to track recent user interactions from the current session.
   - Identify follow-up questions by recognizing pronouns (e.g., "she," "her," "it," "this," "that","their","them") or references to earlier responses.
   - Dynamically link follow-up questions to the relevant parts of the conversation.

   Example:
   - User: "Who is the professor?"
     Assistant: "Professor Karen Jin is the Faculty Internship Coordinator."
   - User: "What's her email?"
     Assistant: "Professor Jin's email is karen.jin@unh.edu."

7. Enhance Conversational Tone:
   - Avoid robotic phrasing like "Answer:". Instead, respond naturally with the relevant information.
   - Do not prepend words like "Response:" or "Answer:" before the actual response.
   - Use positive language and encouragement to support students in their internship journey.
    
8. For specific course-related inquiries, provide detailed responses including:
   - Course codes and credits.
   - Faculty internship coordinator contact information.
   - Registration procedures for internship courses.

Previous interactions with the user:
{chat_history}

Context related to the question:
{context}

Current Question:
{question}

Response Guidelines:
1. Be concise and direct.
2. Maintain a helpful, friendly, and professional tone.
3. Keep answers focused on the internship program.
4. Include relevant course numbers.
5. Verify all prerequisites.
6. Only provide information from official documents.
7. Check if the question references previous context.
8. If yes, connect to relevant previous information.

Remember: Always keep responses concise, directly related to the internship program, approachable, and conversational.
"""

# Initialize the open AI LLM Model
llm = ChatOpenAI(
    model="gpt-4-turbo",
    openai_api_key=apikey,
    temperature=0,
    top_p=1
)

from langchain.schema import HumanMessage
# API route to handle user questions

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    user_question = data.get('message', '').strip()  # Ensure a default empty string
    
    # Ensure user_question is a string
    if not isinstance(user_question, str) or not user_question:
        return jsonify({"error": "Invalid question format."}), 400

    question_hash = get_question_hash(user_question)
    
    # Check for a cached response for identical questions
    cached_response = get_cached_response(question_hash)
    if cached_response:
        return jsonify({"response": cached_response, "retrieval_context": []})

    # Retrieve relevant context directly using similarity_search
    relevant_docs = db.similarity_search(user_question, **retriever.search_kwargs)
    retrieval_context = [doc.page_content for doc in relevant_docs]
    context = "\n".join(retrieval_context)

    # Load conversation memory to populate chat history
    conversation_memory_data = load_conversation_memory()

    # Dynamically populate chat history from conversation memory
    chat_history = "\n".join([
        f"User: {item['user']}\nAssistant: {item['assistant']}" 
        for item in conversation_memory_data
    ])

    # Use the custom prompt template
    prompt_text = PROMPT_TEMPLATE.format(
        context=context,
        chat_history=chat_history,
        question=user_question
    )

    # Generate a new response using the formatted prompt with HumanMessage and invoke
    response = llm.invoke([HumanMessage(content=prompt_text)])
    answer = response.content if response else "No answer found"

    # Save the interaction to conversation memory (limit to last 5 interactions)
    conversation_memory_data.append({"user": user_question, "assistant": answer})
    conversation_memory_data = conversation_memory_data[-5:]  # Keep only the last 5 interactions
    save_conversation_memory(conversation_memory_data)

    # Save the interaction to chat history
    save_interaction_to_json(user_question, answer)

    # Return both the chatbot response and the retrieval context for testing
    return jsonify({"response": answer, "retrieval_context": retrieval_context})

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    file = request.files['file']
    file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    return jsonify({'success': True, 'message': 'PDF uploaded successfully'})

if __name__ == '__main__':
    initialize_chat_history_file()
    app.run(debug=True, host='0.0.0.0', port=80)