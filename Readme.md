# 💚 AI-Powered Test Case & Playwright Script Generator

This project automates **test case generation** and **Playwright script creation** using AI.  
It leverages OpenAI's `autogen` library to generate test cases and Playwright automation scripts for web testing.

---

## **📌 Features**

✅ Automatically generates test cases using AI  
✅ Creates Playwright automation scripts in **JavaScript**  
✅ Uses OpenAI API to refine test cases and scripts  
✅ Supports **async execution** for faster processing

---

## **🛠️ Prerequisites**

Before installing this project, ensure you have the following:

### **1️⃣ Install Python (3.8+)**

- Check if Python is installed:
  ```sh
  python --version
  ```
- If not installed, download it from [python.org](https://www.python.org/downloads/).

### **2️⃣ Install Git**

- Check if Git is installed:
  ```sh
  git --version
  ```
- If not installed, download it from [git-scm.com](https://git-scm.com/downloads).

### **3️⃣ Install Node.js & npm (Required for Playwright)**

- Check if Node.js is installed:
  ```sh
  node -v
  npm -v
  ```
- If not installed, download it from [nodejs.org](https://nodejs.org/).

---

## **💾 Installation Guide**

Follow these steps to set up the project:

### **1️⃣ Clone the Repository**

```sh
git clone <your-repo-url>
cd <your-repo-name>
```

### **2️⃣ Create a Virtual Environment (Optional but Recommended)**

```sh
python -m venv venv
source venv/bin/activate  # For macOS/Linux
venv\Scripts\activate     # For Windows
```

### **3️⃣ Install Dependencies**

```sh
pip install -r requirements.txt
```

### **4️⃣ Install Playwright Browsers**

```sh
playwright install
```

### **5️⃣ Set Up API Keys**

1. Create a `.env` file in the project root directory.
2. Add your OpenAI API key:
   ```
   OPENAI_API_KEY=your-api-key-here
   ```

---

## **🚀 Running the Project**

Once setup is complete, run the project using:

```sh
python main.py
```

---

## **📂 Project Structure**

```
💽 project-root
├── config.py                   # Configuration file (Agents, API keys, Playwright settings)
├── main.py                      # Main entry point for generating test cases & scripts
├── playwright_generator.py      # Generates Playwright scripts using AI
├── PlaywrightScript.js          # Final Playwright script (automated test cases)
├── test_case_generator.py       # AI-powered test case generator
├── TestCases.txt                # Stores generated test cases
├── requirements.txt             # Python dependencies
├── README.md                    # Documentation (this file)
├── .env                         # API Key file (user-created)
```

---

## **📦 Dependencies**

The required Python libraries are in `requirements.txt`:

```txt
# Core Dependencies
playwright==1.42.0          # Browser automation for test execution
autogen==0.4.0              # AI agent-based test generation
python-dotenv==1.0.0        # Managing environment variables
openai==1.12.0              # OpenAI's Python SDK

# Optional Dependencies (for best practices & testing)
pytest==8.1.1               # Run Playwright tests with pytest
pytest-asyncio==0.23.6      # Support for async Playwright tests
pytest-playwright==0.4.2    # Pytest integration for Playwright

# Code Quality Tools (Optional but Recommended)
black==24.3.0               # Auto-format Python code
flake8==7.0.0               # Linter for checking Python syntax
```

To install them, run:

```sh
pip install -r requirements.txt
```

---

## **🛠️ Troubleshooting**

### **Common Issues & Fixes**

#### ❌ `ModuleNotFoundError: No module named 'playwright'`

✔ Solution: Run

```sh
pip install -r requirements.txt
```

#### ❌ `playwright install` command fails

✔ Solution: Run

```sh
playwright install --with-deps
```

#### ❌ `OPENAI_API_KEY` not found error

✔ Solution: Ensure you have set up your `.env` file correctly.

---

## **🤝 Contributing**

Contributions are welcome! Feel free to:

- **Report issues**
- **Suggest new features**
- **Submit pull requests**

To contribute, **fork the repository**, create a new branch, make your changes, and submit a **pull request**.

---

## **📚 License**

This project is licensed under the **MIT License**.

---

🚀 **Now your project is well-documented, fully installable, and GitHub-ready!**  
Would you like me to generate a **sample `.gitignore` file** as well? 😊
