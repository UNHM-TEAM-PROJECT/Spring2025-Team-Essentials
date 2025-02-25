# Automated Testing for Internship Chatbot

## Overview
The automated testing module is designed to evaluate the performance, accuracy, and relevance of the chatbot designed to assist students with internship-related queries. By running predefined test cases, it ensures the chatbot provides accurate, context-aware, and relevant answers to user queries. The testing process uses DeepEval, LangChain, and OpenAI's GPT-4 to measure metrics such as answer relevancy and faithfulness to the retrieved context.

The process involves the following key steps:

1. **Test Case Setup**: Each test case includes a question for the chatbot, an expected answer, and a retrieval context with relevant information the chatbot should use.
2. **Response Evaluation**: The chatbot's response is assessed for Answer Relevancy, which measures its relevance to the query, and Faithfulness, which checks its consistency with the provided context.
3. **Automated Execution**: The program sends questions from the test cases to the chatbot and responses are evaluated against the predefined metrics.

## Key Components

### Test Case Structure
Each test case consists of the following:
- **Question**: The input query for the chatbot.
- **Expected Answer**: The correct answer expected from the chatbot.
- **Retrieval Context**: Relevant information that the chatbot uses to formulate its response.

### Metrics Used
- **Answer Relevancy**: Measures how relevant the chatbot's response is to the user's query.
- **Faithfulness**: Ensures the chatbot's response aligns with the retrieval context without including inaccurate or extraneous information.

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
3. Verify the chatbot is accessible via its local HTTP link (http://127.0.0.1:8000/).


Once the chatbot is running, proceed with the steps below to execute automated testing.


## Running Automated Tests
1. Place the test cases in the test_cases list inside the test_rag.py file.

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
    - **Evaluation Results**: Saved to evaluation_results.json.
    - **Updated Test Cases**: Saved to updated_test_cases.json with added details like actual responses and evaluation metrics..



















