from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import warnings
import sys
import time

# Suppress warnings
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed transport.*")
warnings.filterwarnings("ignore", message=".*I/O operation on closed pipe.*")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

class WorkingMCPManager:
    """Enhanced MCP Manager with better error handling and session management"""
    
    def __init__(self):
        self.session = None
        self.available_tools = []
        self.stdio_context = None
        self.session_context = None
        self.server_started = False
        self.retry_count = 0
        self.max_retries = 3
        
    async def start_server(self):
        """Start MCP Playwright server with retry logic"""
        print("🚀 Starting MCP Playwright server...")
        
        while self.retry_count < self.max_retries:
            try:
                server_params = StdioServerParameters(
                    command="npx.cmd",
                    args=["-y", "@playwright/mcp@latest"],
                    env={"PLAYWRIGHT_BROWSERS_PATH": "0"}  # Use system browsers
                )
                
                # Use async context managers properly
                self.stdio_context = stdio_client(server_params)
                read, write = await self.stdio_context.__aenter__()
                
                self.session_context = ClientSession(read, write)
                self.session = await self.session_context.__aenter__()
                
                # Initialize the session with timeout
                await asyncio.wait_for(self.session.initialize(), timeout=30.0)
                
                # List tools
                tools_response = await self.session.list_tools()
                
                # Convert to existing format
                self.available_tools = [
                    {
                        'name': tool.name,
                        'description': tool.description or '',
                        'inputSchema': tool.inputSchema or {"type": "object", "properties": {}}
                    }
                    for tool in tools_response.tools
                ]
                
                self.server_started = True
                print(f"✅ MCP server ready - Found {len(self.available_tools)} tools")
                
                # Print available tools for debugging
                print("🔧 Available tools:")
                for tool in self.available_tools:
                    print(f"  - {tool['name']}: {tool['description']}")
                
                return self.available_tools
                
            except Exception as e:
                self.retry_count += 1
                print(f"❌ Server start attempt {self.retry_count} failed: {e}")
                
                if self.retry_count < self.max_retries:
                    print(f"🔄 Retrying in 2 seconds...")
                    await self.cleanup()  # Clean up before retry
                    await asyncio.sleep(2)
                else:
                    print(f"💥 Failed to start server after {self.max_retries} attempts")
                    raise
        
    async def execute_tool(self, tool_name, arguments):
        """Execute MCP tool with enhanced error handling and retries"""
        print(f"🔧 Executing {tool_name}: {arguments}")
        
        if not self.server_started or not self.session:
            raise Exception("MCP server not started or session not available")
        
        # Add intelligent waits based on tool type
        if tool_name == "navigate_to":
            print("⏳ Pre-navigation wait...")
            await asyncio.sleep(1)
        elif tool_name == "click_element":
            print("⏳ Pre-click wait for element readiness...")
            await asyncio.sleep(2)
        elif tool_name == "type_text":
            print("⏳ Pre-type wait...")
            await asyncio.sleep(1)
        elif tool_name == "browser_snapshot":
            print("⏳ Pre-snapshot wait for page settle...")
            await asyncio.sleep(2)
        
        max_tool_retries = 2
        tool_retry = 0
        
        while tool_retry < max_tool_retries:
            try:
                # Add timeout for tool execution
                result = await asyncio.wait_for(
                    self.session.call_tool(tool_name, arguments), 
                    timeout=60.0
                )
                
                print("✅ Tool execution completed")
                
                # Convert SDK response to expected format
                formatted_result = {
                    "result": {
                        "content": [],
                        "success": True,
                        "tool": tool_name,
                        "arguments": arguments
                    }
                }
                
                # Handle different content types from SDK
                if hasattr(result, 'content') and result.content:
                    for item in result.content:
                        if hasattr(item, 'text'):
                            formatted_result["result"]["content"].append({"text": item.text})
                        elif hasattr(item, 'data'):
                            # Handle binary data (like images)
                            formatted_result["result"]["content"].append({"data": item.data})
                        else:
                            formatted_result["result"]["content"].append({"text": str(item)})
                else:
                    # Handle case where there's no content
                    formatted_result["result"]["content"].append({"text": "Tool executed successfully"})
                
                # Print content for debugging (limit output size)
                for item in formatted_result["result"]["content"]:
                    if "text" in item:
                        text = item['text']
                        # Limit output for very long responses
                        if len(text) > 1000:
                            print(f"📄 {text[:500]}...[truncated]...{text[-200:]}")
                        else:
                            print(f"📄 {text}")
                    elif "data" in item:
                        print("📄 [Binary data received]")
                
                # Add intelligent waits after tool execution based on tool type
                if tool_name == "navigate_to":
                    print("⏳ Post-navigation wait for page load...")
                    await asyncio.sleep(5)
                elif tool_name == "click_element":
                    print("⏳ Post-click wait for page transition...")
                    await asyncio.sleep(3)
                elif tool_name == "type_text":
                    print("⏳ Post-type wait...")
                    await asyncio.sleep(1)
                
                return formatted_result
                
            except asyncio.TimeoutError:
                tool_retry += 1
                print(f"⏱️ Tool execution timeout (attempt {tool_retry}/{max_tool_retries})")
                if tool_retry >= max_tool_retries:
                    return {"error": f"Tool execution timed out after {max_tool_retries} attempts"}
                await asyncio.sleep(1)
                
            except Exception as e:
                tool_retry += 1
                print(f"❌ Tool execution error (attempt {tool_retry}/{max_tool_retries}): {e}")
                
                if tool_retry >= max_tool_retries:
                    return {"error": f"Tool execution failed after {max_tool_retries} attempts: {str(e)}"}
                
                # Check if session is still alive
                if not await self.check_session_health():
                    print("🔄 Session appears dead, attempting restart...")
                    try:
                        await self.start_server()
                    except:
                        return {"error": "Failed to restart MCP session"}
                
                await asyncio.sleep(1)
    
    async def check_session_health(self):
        """Check if MCP session is still healthy"""
        try:
            if not self.session:
                return False
            
            # Try to list tools as a health check
            await asyncio.wait_for(self.session.list_tools(), timeout=5.0)
            return True
        except:
            return False
    
    async def reset_browser_session(self):
        """Reset browser session to ensure clean state"""
        print("🔄 Resetting browser session...")
        try:
            # Close any existing browser contexts
            result = await self.execute_tool("reset_browser", {})
            if "error" not in result:
                print("✅ Browser session reset")
                return True
        except:
            pass
        
        # If reset tool doesn't exist or fails, try navigation to ensure clean state
        try:
            result = await self.execute_tool("navigate_to", {"url": "about:blank"})
            if "error" not in result:
                print("✅ Browser navigated to blank page")
                return True
        except:
            pass
        
        return False
        
    async def cleanup(self):
        """Enhanced cleanup with better error handling"""
        print("🛑 Cleaning up MCP session...")
        
        cleanup_errors = []
        
        try:
            if self.session_context:
                await asyncio.wait_for(
                    self.session_context.__aexit__(None, None, None), 
                    timeout=5.0
                )
        except Exception as e:
            cleanup_errors.append(f"Session cleanup: {e}")
        
        try:
            if self.stdio_context:
                await asyncio.wait_for(
                    self.stdio_context.__aexit__(None, None, None), 
                    timeout=5.0
                )
        except Exception as e:
            cleanup_errors.append(f"Stdio cleanup: {e}")
        
        # Reset state
        self.session = None
        self.session_context = None
        self.stdio_context = None
        self.server_started = False
        
        if cleanup_errors:
            print(f"⚠️ Cleanup warnings (ignored): {'; '.join(cleanup_errors)}")
        else:
            print("✅ MCP session cleaned up successfully")
    
    async def get_browser_state(self):
        """Get current browser state for debugging"""
        try:
            result = await self.execute_tool("browser_snapshot", {})
            return result.get("result", {}).get("content", [])
        except:
            return []
    
    def get_tool_by_name(self, tool_name):
        """Get tool definition by name"""
        return next((tool for tool in self.available_tools if tool['name'] == tool_name), None)