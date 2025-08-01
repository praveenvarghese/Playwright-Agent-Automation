# Playwright Test Generator

An AI-powered tool that automatically generates Playwright Page Object Models and test scripts using MCP (Model Context Protocol) automation and LangGraph workflows.

## Overview

This tool combines MCP browser automation with AI agents to create complete Playwright test suites. It fetches test cases from Azure Vector Search, executes them using MCP automation to capture real browser interactions, then uses a 6-step AI workflow to generate production-ready Page Object Models and test scripts.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Azure Vector  │    │  MCP Playwright │    │   6-Step AI     │
│     Search      │───▶│   Automation    │───▶│   Workflow      │
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

# Azure Search Configuration
AZURE_SEARCH_ENDPOINT=your_search_endpoint
AZURE_SEARCH_KEY=your_search_key
AZURE_SEARCH_INDEX_NAME=your_index_name

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

### Basic Usage

Generate a complete test suite for a specific test case:

```bash
python playwright_generation\runners\mcp_test_generator_simple.py TC-ENV-001
```

### With Custom Output Directory

```bash
python playwright_generation\runners\mcp_test_generator_simple.py TC-ENV-001 my_custom_output
```

## Workflow Steps

### 1. Test Case Retrieval

- Fetches test case from Azure Vector Search by ID
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
│   ├── EnvironmentPage.js              # Environment management page object
│   └── BasePage.js                     # Common page functionality
├── tests/
│   └── TC-ENV-001.spec.js              # Complete test script
├── TC-ENV-001_selectors.json           # Extracted selectors
└── TC-ENV-001_mcp_execution_log.json   # MCP automation log
```

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

**Azure connection errors:**

- Verify all Azure credentials in .env file
- Check network connectivity to Azure services
- Validate API keys and endpoints

**Empty output files:**

- Check MCP execution log for errors
- Verify test case exists in Azure Vector Search
- Review agent responses for parsing issues

### Debug Mode

Enable debug logging by checking the generated files:

- `TC-XXX-XXX_mcp_execution_log.json` - MCP automation details
- `TC-XXX-XXX_selectors.json` - Extracted selectors
- Console output for step-by-step progress

## Contributing

When modifying the codebase:

1. Keep the 6-step workflow intact
2. Maintain ES6 module compatibility
3. Preserve parameterized test patterns
4. Test with real Azure Vector Search data
5. Validate generated code syntax
