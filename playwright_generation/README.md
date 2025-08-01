# Playwright Test Generator

An AI-powered tool that automatically generates Playwright Page Object Models and test scripts using MCP (Model Context Protocol) automation and LangGraph workflows.

## Overview

This tool combines MCP browser automation with AI agents to create complete Playwright test suites. It can fetch test cases from Azure Vector Search or load them from local text files, executes them using MCP automation to capture real browser interactions, then uses a 6-step AI workflow to generate production-ready Page Object Models and test scripts.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Azure Vector  │    │  MCP Playwright │    │   6-Step AI     │
│   Search / File │───▶│   Automation    │───▶│   Workflow      │
│  (Test Cases)   │    │ (Real Browser)  │    │ (POM + Tests)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Project Structure

```
playwright_generation/
├── runners/
│   └── mcp_test_generator_simple.py    # Main entry point
├── agents/
│   ├── agent_config.py                 # LangChain agent configuration
│   └── agent_prompts.py                # System prompts for agents
├── common/
│   └── vector_retrieval.py             # Azure Vector Search integration
├── mcp_helpers/
│   └── mcp_manager.py                  # MCP server communication
├── orchestration/
│   └── extraction_utils.py             # Response parsing utilities
└── prompts/
    ├── pom_generator_prompt.txt         # Page Object Model generation prompt
    ├── pom_critic_prompt.txt            # POM critique prompt
    ├── test_generator_prompt.txt        # Test script generation prompt
    └── test_critic_prompt.txt           # Test script critique prompt
```

## Requirements

### Environment Variables

Create a `.env` file with the following variables:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=your_openai_endpoint
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Azure Search Configuration (only required for vector mode)
AZURE_SEARCH_ENDPOINT=your_search_endpoint
AZURE_SEARCH_KEY=your_search_key
AZURE_SEARCH_INDEX_NAME=your_index_name

# Test Case Source Configuration
# Options: vector (Azure Vector Search) or file (local text files)
TEST_CASE_SOURCE=vector

# Application Under Test
APP_URL=your_application_url
APP_USERNAME=your_test_username
APP_PASSWORD=your_test_password
```

### Dependencies

```bash
pip install langchain-openai
pip install langgraph
pip install azure-search-documents
pip install azure-core
pip install openai
pip install python-dotenv
```

### System Requirements

- Node.js (for MCP Playwright server)
- Python 3.8+
- Playwright browsers installed

## Usage

### Vector Database Mode (Default)

Set your `.env` file:

```env
TEST_CASE_SOURCE=vector
```

Generate a complete test suite for a specific test case from Azure Vector Search:

```bash
python playwright_generation\runners\mcp_test_generator_simple.py TC-SAMPLE-001
```

### File-Based Mode

Set your `.env` file:

```env
TEST_CASE_SOURCE=file
```

Create a test case file with the following format:

**Example: `my_test.txt`**

```
Title: Sample Test Case Title
Steps:
1. Navigate to the application login page.
2. Enter valid credentials and login.
3. Navigate to the target feature.
4. Perform the required action.
5. Verify the expected result is displayed.
Expected:
The action is completed successfully and the expected result is visible.
```

**Optional ID field** (if not specified, defaults to 'TC-FILE-001'):

```
ID: TC-SAMPLE-001
Title: Sample Test Case Title
Steps:
1. Navigate to the application login page.
2. Enter valid credentials and login.
3. Navigate to the target feature.
4. Perform the required action.
5. Verify the expected result is displayed.
Expected:
The action is completed successfully and the expected result is visible.
```

Then run:

```bash
python playwright_generation\runners\mcp_test_generator_simple.py my_test.txt
```

### With Custom Output Directory

```bash
python playwright_generation\runners\mcp_test_generator_simple.py TC-SAMPLE-001 my_custom_output
# or
python playwright_generation\runners\mcp_test_generator_simple.py my_test.txt my_custom_output
```

## Test Case File Format

When using `TEST_CASE_SOURCE=file`, create text files with the following structure:

```
Title: Your test case title
Steps:
1. First step description
2. Second step description
3. Third step description
Expected:
Expected results description
```

**Optional fields:**

- `ID: your-custom-id` - If not provided, defaults to 'TC-FILE-001'

**Supported file extensions:** Any text file (.txt, .md, etc.)

## Workflow Steps

### 1. Test Case Retrieval

- **Vector Mode**: Fetches test case from Azure Vector Search by ID
- **File Mode**: Loads test case from local text file and parses content
- Retrieves test steps, expected results, and metadata

### 2. MCP Automation

- Starts MCP Playwright server
- Executes test case using AI-driven browser automation
- Captures real browser interactions and selectors
- Saves execution log for analysis

### 3. Selector Extraction

- Parses MCP execution log
- Extracts Playwright locators (getByRole, getByText, etc.)
- Uses LLM to clean and structure selector data

### 4. 6-Step AI Workflow

1. **Generate POM** - Creates Page Object Models from selectors
2. **Critique POM** - Reviews and identifies improvement areas
3. **Improve POM** - Applies critique feedback to enhance POMs
4. **Generate Test** - Creates test scripts using improved POMs
5. **Critique Test** - Reviews test script for best practices
6. **Improve Test** - Finalizes production-ready test script

## Output Structure

```
complete_tests/
├── pages/
│   ├── LoginPage.js                    # Login page object
│   ├── FeaturePage.js                  # Feature-specific page object
│   └── BasePage.js                     # Common page functionality
├── tests/
│   └── TC-SAMPLE-001.spec.js           # Complete test script (named using ID from test case)
├── TC-SAMPLE-001_selectors.json        # Extracted selectors
└── TC-SAMPLE-001_mcp_execution_log.json # MCP automation log
```

**Note**: Output files are named using the ID from the test case content, not the input filename.

## Generated Code Features

### Page Object Models

- ES6 module syntax with named exports
- Modern Playwright locators (getByRole, getByText, getByLabel)
- Parameterized methods (no hardcoded values)
- Error handling and robust selectors

### Test Scripts

- Single test blocks (no describe wrappers)
- beforeEach hooks for login/setup
- Parameterized test data via testCase object
- Arrange-Act-Assert pattern
- ES6 imports with .js extensions

## Example Generated Code

### Page Object

```javascript
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

### Test Script

```javascript
import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage.js";

const testCase = {
  url: "https://example.com",
  username: "testuser",
  password: "password123",
  expectedTitle: "Dashboard",
};

test.beforeEach(async ({ page }) => {
  const loginPage = new LoginPage(page);
  await page.goto(testCase.url);
  await loginPage.login(testCase.username, testCase.password);
});

test("User can access dashboard after login", async ({ page }) => {
  await expect(page).toHaveTitle(testCase.expectedTitle);
});
```

## AI Agents

The system uses 4 specialized AI agents:

- **POM Generator** - Creates Page Object Models from browser interactions
- **POM Critic** - Reviews and suggests improvements for POMs
- **Test Generator** - Creates test scripts using best practices
- **Test Critic** - Reviews and optimizes test scripts

## Configuration

### Agent Configuration

Agents are configured in `agents/agent_config.py` with:

- Azure OpenAI integration
- Custom system prompts
- Error handling and retry logic

### Prompt Engineering

System prompts are stored in `prompts/` directory:

- Specialized prompts for each agent type
- Best practices and coding standards
- Output format specifications

## Troubleshooting

### Common Issues

**Module not found errors:**

- Ensure you're running from the project root directory
- Check that all dependencies are installed

**MCP server connection issues:**

- Verify Node.js is installed
- Check that port 3000 is available
- Ensure Playwright browsers are installed

**Azure connection errors (Vector mode only):**

- Verify all Azure credentials in .env file
- Check network connectivity to Azure services
- Validate API keys and endpoints

**File not found errors (File mode):**

- Ensure the test case file exists in the current working directory
- Check file path and extension
- Verify file permissions

**Empty output files:**

- Check MCP execution log for errors
- Verify test case format (for file mode) or existence (for vector mode)
- Review agent responses for parsing issues

### Debug Mode

Enable debug logging by checking the generated files:

- `{ID}_mcp_execution_log.json` - MCP automation details
- `{ID}_selectors.json` - Extracted selectors
- Console output for step-by-step progress

## Contributing

When modifying the codebase:

1. Keep the 6-step workflow intact
2. Maintain ES6 module compatibility
3. Preserve parameterized test patterns
4. Test with both vector and file-based modes
5. Validate generated code syntax
