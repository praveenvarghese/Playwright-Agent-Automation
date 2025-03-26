"""
Playwright test automation generator.
This module automatically generates Playwright tests from test cases using POM pattern.
"""

from .generator import generate_scripts_for_feature, generate_script_for_test_case
from .utils import format_console_output, create_playwright_config, get_page_objects
from .script_manager import get_all_test_scripts

__all__ = [
    'generate_scripts_for_feature',
    'generate_script_for_test_case',
    'format_console_output',
    'create_playwright_config',
    'get_page_objects',
    'get_all_test_scripts'
]