# Playwright Test Generator

**Automatically generates complete Playwright test suites from simple text descriptions using AI and real browser automation.**

Give it a test case like "Login and edit user settings" → Get back working Playwright code with Page Object Models and tests.

## What This Tool Does

1. **You write** a simple test case in plain text
2. **AI executes** the test in a real browser to understand your app
3. **AI generates** professional Playwright code with Page Objects and tests
4. **You get** production-ready test files

## 30-Second Example

**Input** (`my_test.txt`):

```
Title: Edit User Profile
Steps:
1. Login to the application
2. Navigate to profile page
3. Update email address
4. Save changes
Expected:
Profile should show updated email
```

**Command**:

```bash
python runners/mcp_test_generator_simple.py my_test.txt
```

**Output** - Complete test files:

```
complete_tests/
├── pages/
│   ├── LoginPage.js       # Professional page objects
│   └── ProfilePage.js
└── tests/
    └── edit-profile.spec.js # Working Playwright test
```

## Prerequisites

Before you start, make sure you have:

- **Python 3.8+** installed
- **Node.js** installed (any recent version)
- **Azure OpenAI** access (or OpenAI API key)
- A web application to test

## Quick Setup

### 1. Clone and Install

```bash
git clone <repository>
cd playwright_generation
pip install -r requirements.txt
npm install -g @playwright/mcp
npx playwright install
```

### 2. Create Configuration File

Create `.env` file in the project root:

```env
# Required: AI Configuration
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_DEPLOYMENT_NAME=your_model_name
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Required: Your Application
APP_URL=https://your-app.com
APP_USERNAME=test_user
APP_PASSWORD=test_password

# Simple file-based tests (easiest to start)
TEST_CASE_SOURCE=file
```

### 3. Create Your First Test Case

Create `login_test.txt`:

```
ID: TC-LOGIN-001
Title: User Login Test
Steps:
1. Go to login page
2. Enter username and password
3. Click login button
Expected:
User should see dashboard
```

### 4. Generate Tests

```bash
python runners/mcp_test_generator_simple.py login_test.txt
```

### 5. Check Results

```bash
# Your generated files will be in:
complete_tests/pages/       # Page Object Models
complete_tests/tests/       # Test scripts
```

## What You Get

### Professional Page Objects

```javascript
// Generated: pages/LoginPage.js
export class LoginPage {
  constructor(page) {
    this.page = page;
  }

  async login(username, password) {
    await this.page.getByRole("textbox", { name: "Username" }).fill(username);
    await this.page.getByRole("textbox", { name: "Password" }).fill(password);
    await this.page.getByRole("button", { name: "Login" }).click();
  }
}
```

### Complete Test Scripts

```javascript
// Generated: tests/TC-LOGIN-001.spec.js
import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage.js";

const testCase = {
  url: "https://your-app.com",
  credentials: { username: "test_user", password: "test_password" },
};

test.beforeEach(async ({ page }) => {
  const loginPage = new LoginPage(page);
  await page.goto(testCase.url);
  await loginPage.login(
    testCase.credentials.username,
    testCase.credentials.password
  );
});

test("User Login Test", async ({ page }) => {
  // Test automatically generated based on your steps
  await expect(page).toHaveTitle(/Dashboard/);
});
```

## Test Case Formats

### Simple Text Files (Recommended)

```
Title: Your test description
Steps:
1. First action
2. Second action
3. Third action
Expected:
What should happen
```

### With Custom ID

```
ID: TC-CUSTOM-001
Title: Your test description
Steps:
1. First action
Expected:
What should happen
```

## Advanced Options

### Multiple Test Case Sources

Once comfortable with file-based tests, you can use enterprise sources:

**Azure Vector Search** (for semantic test case search):

```env
TEST_CASE_SOURCE=vector
AZURE_SEARCH_ENDPOINT=your_search_endpoint
AZURE_SEARCH_KEY=your_key
AZURE_SEARCH_INDEX_NAME=your_index
```

**Azure DevOps Test Plans** (for integrated DevOps workflows):

```env
TEST_CASE_SOURCE=azure_devops
AZURE_DEVOPS_ORG_URL=https://dev.azure.com/your-org
AZURE_DEVOPS_PROJECT=your-project
AZURE_DEVOPS_PAT=your_personal_access_token
```

### Custom Output Directory

```bash
python runners/mcp_test_generator_simple.py my_test.txt custom_output_folder
```

## How It Works (The Magic Behind It)

1. **Browser Automation**: Uses MCP (Model Context Protocol) to actually interact with your web app in a real browser
2. **AI Analysis**: AI agents analyze the browser interactions to understand your app's structure
3. **Code Generation**: 6-step AI workflow creates optimized Page Object Models and tests
4. **Validation**: Built-in validation ensures generated code actually works

```
Text Description → Real Browser Actions → AI Analysis → Working Playwright Code
```

## Common Issues & Solutions

### "Failed to start MCP server"

```bash
# Make sure Node.js is installed
node --version

# Install MCP globally
npm install -g @playwright/mcp

# Check if port 3000 is free
```

### "Test case validation failed"

Check your test case file has all required sections:

- Title: (description)
- Steps: (numbered list)
- Expected: (what should happen)

### "No test files generated"

1. Check your `.env` file has correct app URL and credentials
2. Make sure your app is accessible
3. Check the generated log files for errors

### "Import errors in generated tests"

The generated tests use ES6 modules. Make sure your `playwright.config.js` supports ES6:

```javascript
// playwright.config.js
export default {
  // your config
};
```

## Architecture Overview

For those interested in the technical details:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Test Case     │    │  MCP Browser    │    │   AI Workflow   │
│   (Text File)   │───▶│   Automation    │───▶│   (6 Steps)     │
│                 │    │ (Real Browser)  │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │                       │
                               ├── Captures Actions    ├── Generates POMs
                               ├── Takes Screenshots   ├── Creates Tests
                               └── Records Selectors   └── Validates Code
```

### The 6-Step AI Process

1. **Generate Page Objects** - Creates page object models from browser interactions
2. **Critique Page Objects** - Reviews and suggests improvements
3. **Improve Page Objects** - Applies feedback and optimizations
4. **Generate Tests** - Creates test scripts using the page objects
5. **Critique Tests** - Reviews test quality and structure
6. **Improve Tests** - Finalizes production-ready test code

## Project Structure

```
playwright_generation/
├── runners/
│   └── mcp_test_generator_simple.py    # Main script (start here)
├── agents/                             # AI agent configuration
├── common/                             # Shared utilities
├── models/                             # Data validation
├── orchestration/                      # Workflow management
└── prompts/                           # AI prompts
```

## Requirements

**Python Packages** (auto-installed with `pip install -r requirements.txt`):

```
pydantic==2.11.7
langchain-openai
langgraph
azure-search-documents
mcp
python-dotenv
```

**System Requirements**:

- Python 3.8 or higher
- Node.js (any recent version)
- 2GB+ RAM (for browser automation)
- Internet connection (for AI API calls)

## Support & Troubleshooting

### Debug Information

When something goes wrong, check these generated files:

- `{test-id}_mcp_execution_log.json` - Browser automation log
- `{test-id}_pom_step1_generate.txt` - Page object generation
- Console output for step-by-step progress

### Getting Help

1. Check the troubleshooting section above
2. Look at the generated log files for specific errors
3. Verify your `.env` configuration
4. Make sure your test application is accessible

### Test Your Setup

```bash
# Verify dependencies
python -c "from common.validation_helpers import check_dependencies; check_dependencies()"

# Test Azure DevOps connection (if using)
python -c "import asyncio; from common.azure_devops_client import test_azure_devops_connection; asyncio.run(test_azure_devops_connection())"
```

## Example Test Cases

### Simple Login Test

```
Title: User can login successfully
Steps:
1. Navigate to login page
2. Enter valid credentials
3. Click login button
Expected:
User should be redirected to dashboard
```

### E-commerce Checkout

```
Title: User can complete purchase
Steps:
1. Login to account
2. Add product to cart
3. Proceed to checkout
4. Enter payment information
5. Complete purchase
Expected:
Order confirmation should be displayed
```

### Form Submission

```
Title: User can submit contact form
Steps:
1. Navigate to contact page
2. Fill out contact form
3. Submit form
Expected:
Success message should appear
```

This tool generates production-ready Playwright tests with proper Page Object Models, making your test automation robust and maintainable.
