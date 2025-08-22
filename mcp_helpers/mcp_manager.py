from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import warnings
import sys

# Suppress any remaining warnings
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed transport.*")
warnings.filterwarnings("ignore", message=".*I/O operation on closed pipe.*")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

class WorkingMCPManager:
    """MCP Manager using official SDK"""
    
    def __init__(self):
        self.session = None
        self.available_tools = []
        self.stdio_context = None
        self.session_context = None
        
    async def start_server(self):
        """Start MCP Playwright server"""
        print("🚀 Starting MCP Playwright server...")
        
        try:
            server_params = StdioServerParameters(
                command="npx.cmd",
                args=["-y", "@playwright/mcp@latest"]
            )
            
            # Use async context managers properly
            self.stdio_context = stdio_client(server_params)
            read, write = await self.stdio_context.__aenter__()
            
            self.session_context = ClientSession(read, write)
            self.session = await self.session_context.__aenter__()
            
            # Initialize the session
            await self.session.initialize()
            
            # List tools
            tools_response = await self.session.list_tools()
            
            # Convert to existing format expected by your code
            self.available_tools = [
                {
                    'name': tool.name,
                    'description': tool.description or '',
                    'inputSchema': tool.inputSchema or {"type": "object", "properties": {}}
                }
                for tool in tools_response.tools
            ]
            
            print(f"✅ MCP server ready - Found {len(self.available_tools)} tools")
            return self.available_tools
            
        except Exception as e:
            print(f"❌ Failed to start MCP server: {e}")
            raise
        
    async def execute_tool(self, tool_name, arguments):
        """Execute MCP tool"""
        print(f"🔧 {tool_name}: {arguments}")
        
        try:
            result = await self.session.call_tool(tool_name, arguments)
            print("✅ Tool execution completed")
            
            # Convert SDK response to your expected format
            formatted_result = {
                "result": {
                    "content": []
                }
            }
            
            # Handle different content types from SDK
            if hasattr(result, 'content') and result.content:
                for item in result.content:
                    if hasattr(item, 'text'):
                        formatted_result["result"]["content"].append({"text": item.text})
                    else:
                        formatted_result["result"]["content"].append({"text": str(item)})
            
            # Print content for debugging (matching old behavior)
            for item in formatted_result["result"]["content"]:
                if "text" in item:
                    print(f"📄 {item['text']}")
            
            return formatted_result
            
        except Exception as e:
            print(f"❌ Tool call failed: {e}")
            return {"error": f"Tool execution failed: {str(e)}"}
        
    async def cleanup(self):
        """Clean up MCP session"""
        print("🛑 Closing MCP session...")
        try:
            if self.session_context:
                await self.session_context.__aexit__(None, None, None)
            if self.stdio_context:
                await self.stdio_context.__aexit__(None, None, None)
            print("✅ MCP session closed")
        except Exception as e:
            print(f"⚠️ Cleanup warning (ignored): {e}")
        finally:
            self.session = None
            self.session_context = None
            self.stdio_context = None