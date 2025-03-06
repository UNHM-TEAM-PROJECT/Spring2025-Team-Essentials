# SPR2025-TEAM-ESSENTIALS

# NECHE Compliance Assistant Chatbot

## Overview
This chatbot allows users to upload PDFs, extracts the text, checks for NECHE compliance based on predefined criteria (such as instructor name, title, department, contact details, etc.), and uses AI-powered responses to user queries based on the extracted content. It integrates with OpenAI's GPT-4 and Chroma vector database for document search and interaction.

## Features
- PDF Upload & Text Extraction: Upload PDFs and extract text.
- Compliance Checking: Analyze the extracted text for specific compliance criteria.
- AI Chatbot: Ask questions related to the document's content and receive AI-powered responses.
- Document Vectorization: Uses Chroma to store and search document chunks for relevance to user queries.

## Technologies Used
- Flask: Web framework for handling HTTP requests.
- pdfplumber: For extracting text from PDFs.
- Pytesseract: For OCR to extract text from images within PDFs.
- langchain: For embedding documents, storing vector representations, and generating AI-based responses.
- OpenAI GPT-4: For generating responses to user queries.
- Chroma: For storing document embeddings and performing similarity search.

## Setup

### Prerequisites
Ensure you have the following installed:
- Python 3.x
- pip
- Way to access the code(i.e code editor such as VS Code)
- SSH Key(in case the regular gitclone doesn't work)
- Allocate more than a 5gbs of space, in relation to cloning and downloading necessary packages

### Installation Steps
1. Clone the repository:
```bash
git clone https://github.com/UNHM-TEAM-PROJECT/Spring2025-Team-Essentials.git
cd Spring2025-Team-Essentials
```
2. Create a virtual environment:
```bash
python -m venv venv
# on Mac/linux: source venv/bin/activate 
# On Windows: venv\Scripts\activate
(depends in the scenraio that packages aren't installing properly)
```
3. Install the required dependencies:
   pip install -r requirements.txt 
5. Set your OpenAI API key as an environment variable:

Linux/MacOS:
```bash
export OPENAI_API_KEY="your-openai-api-key"
echo $OPENAI_API_KEY  # To verify the key is exported correctly
```
Windows:
```bash
set OPENAI_API_KEY="your-openai-api-key"
echo %OPENAI_API_KEY%  # To verify the key is exported correctly
```
5. Usage:
   1. Place the PDF documents in the data/ directory.
   2. Change the path to your local directory:
     •Open the chatbot.py file.
     •Upload the pdf_directory variable to point to your local directory containing the PDFs, For example:
•pdf_directory = "your_local_path_to_pdfs_directory"
3. Run the chatbot:
```bash
python chatbot.py
```
4. Open your browser and navigate to:
```bash
http://127.0.0.1:8000/
```
5. Ask pdf related questions, e.g., “What is the professor's phone number?"

## Automated Testing for Compliance Chatbot
## Overview
The automated testing module is designed to evaluate the performance, accuracy, and relevance of the chatbot designed to assist students with internship-related queries. By running predefined test cases, it ensures the chatbot provides accurate, context-aware, and relevant answers to user queries.

The process involves the following key steps:

**Test Case Setup**: Each test case for the pdf in this iteration includes the necessary creitera for a question for a syallbus.

**Response Evaluation**: The chatbot's response is assessed for Answer Relevancy, which measures its relevance to the query, and Faithfulness, which checks its consistency with the provided context.

**Automated Execution**: The program sends pdf from the test cases to the chatbot are evaluated.

## Key Components

### Test Case Structure

Each test case consists of the following:

**PDF**: The input query for the chatbot.

**Expected Criteria**: Checking for NECHE compliance.

**Retrieval Context**: Relevant information that the chatbot uses to formulate its evaluation of the PDF.

## How to Perform Automated Testing
## Installation and Setup
### Prerequisites
- Python 3.8+
- OpenAI API Key
- Requests Library
  
Ensure the following steps are completed from the main repository's README.md:

1.Clone the repository and install the required dependencies.

2.Run the chatbot by executing python chatbot.py.

3.Verify the chatbot is accessible via its local HTTP link (http://127.0.0.1:8000/).

Once the chatbot is running, proceed with the steps below to execute automated testing.

## Running Automated Tests
1.Place the test cases pdf files in the automated testing/Syllabi_sp2025.

2.Set your OpenAI API key as an environment variable:

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
3. Run the automated test script: ```bash python test_rag.py

4. Outputs:
   
- **Evaluation Results**: Saved in the outputs/compliance reports folder each pdf json report that is uploaded into the Syllabi_sp2025 folder.

# Deploying Chatbot to AWS

This guide provides step-by-step instructions for deploying applications on Amazon Web Services (AWS). It covers the entire process from account creation to application deployment using EC2 instances.

## Prerequisites
- Basic knowledge of AWS services.
- Installed tools:
  - AWS CLI
  - Python 3.8+
  - Virtual environment tools (e.g., `venv` or `virtualenv`)
  - MobaXTerm or an SSH client for server access.

## Steps to Deploy

### 1. Create an AWS Account
1. Go to the [AWS website](https://aws.amazon.com/).
2. Click "Create an AWS Account".
3. Follow the steps to sign up, including:
   - Adding payment information.
   - Verifying your email and phone number.
4. Log in to AWS using your credentials.

### 2. Launch an EC2 Instance
1. Go to the AWS Management Console and open the EC2 Dashboard.
2. Click Launch Instance.
3. Configure the instance:
      - Choose an Amazon Machine Image (AMI): Select Amazon Linux 2.
4. Select an instance type: Use t3.2xlarge or similar for performance.

5. Create a new key pair (.pem file) during the instance setup.
6. Download and save the .pem file securely on your local machine. This file will be used for SSH access.
7. Add storage: Allocate at least 100GB.

8. Configure security group to allow the following:
      - Open ports 22 (SSH) and 80 (HTTP).

9. Launch the instance.

### 3. Start the EC2 Instance
1. From EC2 Dashboard, select your instance
2. Click "Start Instance"
3. Wait for the instance state to become "Running"
4. Note the Public IPv4 address

### 4. SSH Connection Setup
1. Download MobaXterm on windows:
   - Visit the official MobaXterm website: https://mobaxterm.mobatek.net/.
   - Download the "Home Edition" (Installer version or Portable version).
   - Open the downloaded .exe file.
   - Follow the on-screen instructions to install the application.
   - Once installed, open MobaXterm from the Start Menu or Desktop Shortcut.

2. Click "Session" → "New Session"
3. Select "SSH"
4. Configure SSH session:
      - Enter Public IPv4 address in "Remote host"
      - Check "Specify username" and enter "ec2-user"
      - In "Advanced SSH settings", use "Use private key" and select your .pem file
5. Then you will be logged into AWS Linux terminal.

### 5. Application Deployment
1. In AWS Linux terminal, switch to root user:
   ```bash
   sudo su
   ```
2. Update system packages:
   ```bash
   sudo yum update -y
   ```
3. Install necessary tools:
   ```bash
   sudo yum install git -y
   sudo yum install python3-pip -y
   ```
4. Clone your repository from Github:
   ```bash
   git clone https://github.com/UNHM-TEAM-PROJECT/Spring2025-Team-Essentials.git
   cd Spring2025-Team-Essentials
   ```

5. Install project dependencies:
   ```bash
   pip install -r requirements.txt
   ```
6. Update the chatbot.py file with the following:
   - Navigate to the data folder.
      ```bash
      cd data
      pwd
      ```
   - Then you will get the data directory path where PDFs are located. Copy this path and save it.
7. Now go back to Chatbot.py file and open that file using:
   ```bash
      nano chatbot.py or
      vi chatbot.py
      ```
8. Now chatbot.py file is opened, then go to insert mode typing "i".

9. Find the pdf_directory variable and change the PDF path to copied path in the step 6.
   - pdf_directory  = "Path you have copied from Step 6"

10. Click on Esc button to exit from insert mode and type :wq to save and exit the file.

11. Set the OpenAI API key in the AWS terminal:
      ```bash
      export OPENAI_API_KEY="your_openai_api_key"
      ```
12. Run the Application:
      ```bash
      python3 chatbot.py
      ```

13. Ensure the application is running, and open any browser: 
   - Navigate to `http://<public-ip>:8000/` in your browser.

   - Start interacting with the chatbot.

-Debug scenarios
Intial Installation:
   1.Clone the repository:
      If not cloning properly, get an ssh key and try this method to access
      git clone git@github.com:UNHM-TEAM-PROJECT/Spring2025-Team-Essentials.git
      cd Spring2025-Team-Essentials
   2. Create a virtual environment:
      depends in the scenraio that packages aren't installing properly, but this part is not entirely necessary, but only 
      if there are problems with installation.
   3. Install the required dependencies:
      This is the one with varations that depends on device. There isn't a clear scenario to get it to work since most packages tend to change on compatablilty, but if you can verify that most of the packages are installed and debug through running the script and 
      checking what the terminal says is missing.
 Deployment Installation:
   8. Configure security group to allow the following:
      You can put all the security group confugurations to accept all forms of traffic for TCP, just a way to ensure that it accepts any changes to the HTTP address and port number.
   4. SSH Connection Setup
      This part can be skipped and be subsituted for the provided terminal that they EC2 uses by pushing the "Connect" button and not making any changes to the settings, proceed to the next major step. It's more for stylistic purposes, but it's up to you.
 Application Deployment
    4. Clone your repository from Github:
       A similar scenario, to the intial installation debug scenario, that requires other the normal github clone or the ssh github clone, but requires to get another key for the EC2 as well.
    5. Install project dependencies:
       A similar problem as well, that the EC2 linux terminal will require diffrent versions of the packages in requirements.txt, but using nano and vim to make changes to the requiremnets.txt will be necessary, if the problem contiunes, and take a similar apporach in 
       running the primary chatbot.py program to check which packages are missing.
    




