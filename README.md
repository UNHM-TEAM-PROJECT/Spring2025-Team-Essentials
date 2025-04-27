# SPR2025-TEAM-ESSENTIALS

# NECHE Compliance Assistant Chatbot

## Overview
This chatbot allows users to upload individual PDFs, document (.docx) files, folders/zip files containing multiple PDFs and documents. It extracts the text from the uploaded files and checks for compliance with various requirements, including NECHE compliance, minimal syllabus requirements, and optional syllabus requirements. The chatbot uses AI-powered responses to answer user queries based on the extracted content. It integrates with OpenAI's GPT-4 and Chroma vector database for document search and interaction.

## Features
- PDF and .DOCX Upload & Text Extraction: Upload PDFs and extract text.
- Compliance Checking: Analyze the extracted text for specific compliance criteria.
- AI Chatbot: Ask questions related to the document's content and receive AI-powered responses.
- Document Vectorization: Uses Chroma to store and search document chunks for relevance to user queries.
- Email functionalilty: The use of reportlab to send emails out to those that needs to know their syallbus status!

## Technologies Stack 
###  Frontend
- HTML5 – Structure for the interactive chat interface.
- CSS3 – Custom styling for layout, responsiveness, and animation.
- Bootstrap – Responsive design framework.
- JavaScript – Client-side logic, chat rendering, speech-to-text, and file handling.
- Web Speech API – Voice input via microphone.

 ### Backend
- Python 3.10+ – Core language.
- Flask: Web framework for handling HTTP requests.
- pdfplumber: For extracting text from PDFs.
- Pytesseract: For OCR to extract text from images within PDFs.
- langchain: For embedding documents, storing vector representations, and generating AI-based responses.
- OpenAI GPT-4: For generating responses to user queries.
- Chroma: For storing document embeddings and performing similarity search.
- DocxDocument: for text extraction for documents.
- ReportLab: for email system functionalilty.

### Libraries & Utilities
- json – Formatting and response structure.
- multiprocessing – Speeding up PDF processing.
- os – File management.
- werkzeug – Safe file uploads.

## Directory Structure
- The project is organized as follows:

```
Spring2025-Team-Essentials/
|
├── .vscode/                     # VS Code configuration files
│   └── extensions.json          # Extensions configuration for the project
│
├── data/                       
│   ├── chatbot-bg.png           # Background image for the chatbot UI
│   └── ...                      # Additional static files
│
├── db/                          # Database-related files (if any)
│   └── ...                      # Placeholder for database files
│
├── templates/                   # HTML templates for the chatbot frontend
│   ├── index.html               # Main HTML file for the chatbot UI
│   └── ...                      
│
├── uploads/                     # Folder for storing uploaded files
│   └── ...                    
│
├── venv/                        # Python virtual environment
│   ├── bin/                     # Executables for the virtual environment
│   ├── lib/                     # Installed Python packages
│   │   └── python3.11/          # Python 3.11 site-packages
│   └── ...                      # Other virtual environment files
│
├── chat_history.json            # JSON file to store chatbot conversation history
├── chatbot.py                   # Main script to run the chatbot backend
├── conversation_memory.json     # JSON file to store chatbot memory
├── requirements.txt             # Python dependencies for the project
└── README.md                    # High-level project documentation

```

## Local Setup

### Prerequisites
Ensure you have the following installed:
- Python 3.x
- pip
- Way to access the code(i.e code editor such as VS Code)
- SSH Key(in case the regular https gitclone doesn't work)
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
4. Set your OpenAI API key as an environment variable:

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
6. Usage:
   1. Place the PDF documents in the data/ directory.
   2. Change the path to your local directory:
     •Open the chatbot.py file.
     •Upload the pdf_directory variable to point to your local directory containing the PDFs, For example:
•pdf_directory = "your_local_path_to_pdfs_directory"
7. Run the chatbot:
```bash
python chatbot.py
```
8. Open your browser and navigate to:
```bash
http://127.0.0.1:8000/
```
### Test Case Structure

Each test case consists of the following:

**PDF**: The input query for the chatbot.

**Expected Criteria**: Checking for NECHE compliance.

**Retrieval Context**: Relevant information that the chatbot uses to formulate its evaluation of the PDF.

## System Architecture

This system helps check if a syllabus meets NECHE standards. It works like this:

### Main Parts

- **Frontend (Web Page)**  
  This is what the user sees. It lets the user upload a syllabus file (PDF or DOCX), shows results if it NECHE compliant or not , and allows chatbot interaction.

- **Backend (Python Flask App)**  
  This is the engine that handles uploads, extracts text, checks for NECHE fields, and creates a report.

- **Compliance Checker**  
  It looks through the syllabus content and tries to find important details like instructor name, office hours, grading policy, etc.

- **Chatbot with AI**  
  The chatbot lets users ask questions about the syllabus. It uses OpenAI (GPT-4) and Langchain to find relevant answers.

- **Test & Report System**  
  You can run test syllabus files and download reports to check how well the chatbot is doing. Reports are saved and reviewed.

---

### How It All Works (Data Flow)

1. A user uploads a syllabus file (it might be a pdf or document and also bulk files like zip folders)
2. The frontend sends it to the backend  
3. The backend reads the content and checks for required information  
4. The system shows results to the user (whether the pdf or the document is NECHE compliant or not)
5. A chatbot is available to ask syllabus-related questions  
6. A report can be viewed or downloaded

---

### Diagram

<img width="694" alt="flow diagram" src="https://github.com/user-attachments/assets/8533fc2b-0b71-494b-ba13-40b064dbd747" />

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

6. Create a new key pair (.pem file) during the instance setup.
7. Download and save the .pem file securely on your local machine. This file will be used for SSH access.
8. Add storage: Allocate at least 100GB.

9. Configure security group to allow the following:
      - Open ports 22 (SSH) and 8000 (HTTP).
      - Or make it accept all forms of traffic

10. Launch the instance.

### 3. Start the EC2 Instance
1. From EC2 Dashboard, select your instance
2. Click "Start Instance"
3. Wait for the instance state to become "Running"
4. Note the Public IPv4 address
   
### 4. Application Deployment
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

# Debug Scenarios

## Initial Installation

1. **Clone the repository**  
   - If cloning is not working properly, generate an SSH key and try using the SSH method:  
     ```bash
     git clone git@github.com:UNHM-TEAM-PROJECT/Spring2025-Team-Essentials.git
     cd Spring2025-Team-Essentials
     ```

2. **Create a virtual environment**  
   - This step is optional unless packages are not installing properly.  

3. **Install the required dependencies**  
   - The installation process may vary depending on the device.  
   - Compatibility issues may arise, so verify that most packages are installed.  
   - Debug by running the script and checking which dependencies are missing in the terminal.

---

## Deployment Installation

8. **Configure security group**  
   - Allow all forms of traffic for TCP to ensure changes to the HTTP address and port number are accepted.

4. **SSH Connection Setup**  
   - This step can be skipped by using the built-in EC2 terminal.  
   - Simply press the **"Connect"** button without modifying settings and proceed to the next step.  
   - This is a stylistic choice but is optional.

---

## Application Deployment

4. **Clone your repository from GitHub**  
   - Similar to the initial installation, use either HTTPS or SSH cloning.  
   - EC2 requires a separate SSH key for cloning via SSH.

5. **Install project dependencies**  
   - The EC2 Linux terminal may require different versions of dependencies listed in `requirements.txt`.  
   - Use `nano` or `vim` to edit `requirements.txt` if necessary.  
   - If issues persist, run the primary `chatbot.py` program to identify missing packages.

# Accessing the School Server, Cloning a Git Repository, and Running the Chatbot

These steps outline how to access the school server via VPN, generate an SSH key, add it to your GitHub account, clone a repository using SSH, install dependencies, and run a chatbot application.

**Prerequisites:**

* Access to the school's VPN.
* Access to the command prompt/terminal.
* Your school credentials.
* A GitHub account.
* Python 3 and pip3 installed.

**Steps:**

1.  **Connect to the School's VPN:**
    * Use the link provided: [https://td.usnh.edu/TDClient/60/Portal/KB/ArticleDet?ID=4787](https://td.usnh.edu/TDClient/60/Portal/KB/ArticleDet?ID=4787) to acquire and setup the school's VPN.
2.  **Access the School Server via SSH:**
    * Open your command prompt or terminal.
    * Connect to the server using the following command, replacing `username` with your school username:
        ```bash
        ssh username@whitemount.sr.unh.edu
        ```
    * Enter your school password when prompted.
3.  **Generate an SSH Key:**
    * In your command prompt or terminal, execute the following command:
        ```bash
        ssh-keygen -t rsa -b 4096 -C "your-email@example.com"
        ```
        * **Note:** Replace `"your-email@example.com"` with your actual email address.
    * Press Enter for all prompts to use the default settings (no passphrase, default file locations).
4.  **Verify SSH Key Generation:**
    * List the contents of the `.ssh` directory to confirm the key files were created:
        ```bash
        ls -al ~/.ssh
        ```
        * You should see `id_rsa` and `id_rsa.pub` files.
5.  **Copy the Public SSH Key:**
    * Display the contents of the public key file (`id_rsa.pub`) and copy the entire output:
        ```bash
        cat ~/.ssh/id_rsa.pub
        ```
6.  **Add the SSH Key to your GitHub Account:**
    * Go to your GitHub account settings.
    * Navigate to "SSH and GPG keys."
    * Click "New SSH key" or "Add SSH key."
    * Give your key a descriptive title.
    * Paste the copied SSH key into the "Key" field.
    * Click "Add SSH key"
7.  **Clone the Git Repository via SSH:**
    * Use the following command to clone the repository, replacing the repository URL with the one you want to clone:
        ```bash
        git clone git@github.com:UNHM-TEAM-PROJECT/Spring2025-Team-Essentials.git
        ```
    * If this is the first time you are connecting to github via ssh, you will be prompted to confirm the authenticity of the host. Type "yes" and press enter.
8.  **Navigate to the Repository:**
    * Once the clone is complete, navigate into the cloned repository using:
        ```bash
        cd Spring2025-Team-Essentials
        ```
9.  **Install Required Packages:**
    * Install the necessary Python packages listed in the `requirements.txt` file:
        ```bash
        pip3 install -r requirements.txt
        ```
10. **Run the Chatbot Application:**
    * Execute the chatbot script:
        ```bash
        python3 chatbot.py
        ```
        * **Note:** replace chatbot.py with the correct python file name.
11. **Install Additional Packages (If Needed):**
    * If the chatbot application encounters missing package errors, install the required packages using `pip3 install <package_name>`.
12. **Modify Imports (If Needed):**
    * If there are any errors relating to imports, modify the python files as needed, to correct the import statements.

**Important Notes:**

* Cloning via HTTPS may not function correctly due to changes implemented since 2021.
* Using SSH keys is the recommended and reliable method for cloning Git repositories in this environment.
* Make sure to keep your private key (`id_rsa`) secure. Do not share it with anyone.
* Pay close attention to any error messages during the installation and execution phases, as they will provide valuable information for troubleshooting.
* The python file name may not always be chatbot.py, so check the file name.

    




