# Automated Testing for Internship Chatbot

## Overview
The automated testing module is designed to evaluate the performance, accuracy, and relevance of the chatbot designed to assist students with internship-related queries. By running predefined test cases, it ensures the chatbot provides accurate, context-aware, and relevant answers to user queries. The testing process uses DeepEval, LangChain, and OpenAI's GPT-4 to measure metrics such as answer relevancy and faithfulness to the retrieved context.

The process involves the following key steps:

1. **Test Case Setup**: Each test case for the pdf in this iteration includes the necessary creitera for a question for a syallbus 
2. **Response Evaluation**: The chatbot's response is assessed for Answer Relevancy, which measures its relevance to the query, and Faithfulness, which checks its consistency with the provided context.
3. **Automated Execution**: The program sends pdf from the test cases to the chatbot are evaluated.

## Key Components

### Test Case Structure
Each test case consists of the following:
- **PDF**: The input query for the chatbot.
- **Expected Criteria**: Checking for NECHE compliance.
- **Retrieval Context**: Relevant information that the chatbot uses to formulate its evaluation of the PDF.

## How to Perform Automated Testing

## Installation and Setup

### Prerequisites
- Python 3.8+
- OpenAI API Key
- DeepEval
- Requests Library

Ensure the following steps are completed from the main repository's README.md:
1. Clone the repository and install the required dependencies.
2. Run the chatbot by executing python chatbot.py.
3. Verify the chatbot is accessible via its local HTTP link (http://127.0.0.1:80/).


Once the chatbot is running, proceed with the steps below to execute automated testing.


## Running Automated Tests
1. Place the test cases pdf files in the automated testing/Syllabi_sp2025.

2. Set your OpenAI API key as an environment variable:
   - **Linux/MacOS**:
     ```bash
     export OPENAI_API_KEY="your-openai-api-key"
     echo $OPENAI_API_KEY  # To verify the key is exported correctly
     ```
   - **Windows**:
     ```cmd
     set OPENAI_API_KEY="your-openai-api-key"
     echo %OPENAI_API_KEY%  # To verify the key is exported correctly
     ```
4. Run the automated test script:
    ```bash
    python test_rag.py
5. Outputs:
    - **Evaluation Results**: Saved in the outputs/compliance reports folder each pdf json report that is uploaded into the Syllabi_sp2025 folder.



















