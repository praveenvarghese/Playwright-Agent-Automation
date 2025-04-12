"""
Utility functions for Playwright test automation.
"""

import os
import re


def format_console_output(message_type, message):
    """
    Format console output with colors and icons.
    
    Args:
        message_type (str): Type of message ('info', 'success', 'warning', 'error')
        message (str): The message text
        
    Returns:
        str: Formatted message
    """
    # Icons
    icons = {
        'info': '🔹',
        'success': '✅',
        'warning': '⚠️',
        'error': '❌'
    }
    
    # Get the icon
    icon = icons.get(message_type.lower(), '•')
    
    # Return formatted message
    return f"{icon} {message}"


def camel_to_snake(name):
    """
    Convert CamelCase to snake_case.
    
    Args:
        name (str): CamelCase string
        
    Returns:
        str: snake_case string
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def snake_to_camel(name):
    """
    Convert snake_case to CamelCase.
    
    Args:
        name (str): snake_case string
        
    Returns:
        str: CamelCase string
    """
    components = name.split('_')
    return ''.join(x.title() for x in components)


def extract_feature_code(feature_id):
    """
    Extract feature code from a feature ID.
    
    Args:
        feature_id (str): Feature ID (e.g., FEAT-ENV-001)
        
    Returns:
        str: Feature code (e.g., ENV)
    """
    parts = feature_id.split('-')
    if len(parts) >= 2:
        return parts[1]
    return "unknown"


def sanitize_filename(name):
    """
    Sanitize a string to be used as a filename.
    
    Args:
        name (str): String to sanitize
        
    Returns:
        str: Sanitized string
    """
    # Replace invalid characters
    s = re.sub(r'[\\/*?:"<>|]', "", name)
    # Replace spaces with underscores
    s = re.sub(r'\s+', "_", s)
    return s


def get_playright_config_path():
    """
    Get the path to the Playwright config file.
    
    Returns:
        str: Path to the Playwright config file
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 
                           "..", "playwright_tests", "playwright.config.js"))


def create_playwright_config():
    """
    Create a basic Playwright configuration file if it doesn't exist.
    
    Returns:
        bool: True if created, False if already exists or creation failed
    """
    config_path = get_playright_config_path()
    
    # If config already exists, don't overwrite it
    if os.path.exists(config_path):
        return False
    
    try:
        # Create the tests directory
        tests_dir = os.path.dirname(config_path)
        os.makedirs(tests_dir, exist_ok=True)
        
        # Basic Playwright config content
        config_content = """// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * @see https://playwright.dev/docs/test-configuration
 */
module.exports = defineConfig({
  testDir: './tests',
  /* Maximum time one test can run for. */
  timeout: 30 * 1000,
  expect: {
    /**
     * Maximum time expect() should wait for the condition to be met.
     * For example in `await expect(locator).toHaveText();`
     */
    timeout: 5000
  },
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Maximum time each action such as `click()` can take. Defaults to 0 (no limit). */
    actionTimeout: 0,
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',
    /* Capture screenshots on failure */
    screenshot: 'only-on-failure',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
"""
        
        # Write the config file
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
            
        return True
    except Exception as e:
        print(f"Error creating Playwright config: {str(e)}")
        return False

def get_page_object_methods(page_objects):
    """
    Extract all available methods from the page objects.
    
    Args:
        page_objects (list): List of page object names
        
    Returns:
        str: Formatted string listing all available methods for each page object
    """
    import os
    import re

    pages_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "playwright_tests", "pages"))
    methods_text = []
    
    for page_name in page_objects:
        page_path = os.path.join(pages_dir, f"{page_name}.js")
        if os.path.exists(page_path):
            methods = []
            try:
                with open(page_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Extract methods using regex
                method_matches = re.finditer(r'async\s+(\w+)\s*\([^)]*\)\s*\{', content)
                for match in method_matches:
                    method_name = match.group(1)
                    if method_name != 'constructor':
                        # Try to extract parameters
                        params_match = re.search(r'async\s+' + method_name + r'\s*\(([^)]*)\)', content)
                        params = params_match.group(1).strip() if params_match else ""
                        methods.append(f"{method_name}({params})")
            
            except Exception as e:
                methods.append(f"Error extracting methods: {str(e)}")
            
            methods_text.append(f"## {page_name}\n" + "\n".join([f"- {m}" for m in methods]))
    
    return "\n\n".join(methods_text)

def get_page_objects():
    """
    Get a list of all page objects in the project.
    
    Returns:
        list: List of page object names
    """
    pages_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 
                               "..", "playwright_tests", "pages"))
    
    # If pages directory doesn't exist, return empty list
    if not os.path.exists(pages_dir):
        return []
    
    # Find all page object files
    page_objects = []
    for file in os.listdir(pages_dir):
        if file.endswith(".js") and not file.startswith("_"):
            page_name = os.path.splitext(file)[0]
            if page_name not in page_objects:
                page_objects.append(page_name)
    
    return page_objects