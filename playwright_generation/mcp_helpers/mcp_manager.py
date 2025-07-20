import asyncio
import json
import warnings
import sys

# Suppress Windows asyncio warnings
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message=".*unclosed transport.*")
warnings.filterwarnings("ignore", message=".*I/O operation on closed pipe.*")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

class WorkingMCPManager:
    """MCP Manager based on your working POC"""
    
    def __init__(self):
        self.process = None
        self.request_id = 0
        self.available_tools = []
        
    async def start_server(self):
        """Start MCP Playwright server"""
        print("🚀 Starting MCP Playwright server...")
        
        self.process = await asyncio.create_subprocess_shell(
            "npx -y @playwright/mcp@latest",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await asyncio.sleep(2)
        
        # Initialize
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-executor", "version": "1.0.0"}
        })
        
        # Get tools
        response = await self._send_request("tools/list")
        if response and "result" in response:
            self.available_tools = response["result"].get("tools", [])
            
        print(f"✅ MCP server ready - Found {len(self.available_tools)} tools")
        return self.available_tools
        
    async def execute_tool(self, tool_name, arguments):
        """Execute MCP tool"""
        print(f"🔧 {tool_name}: {arguments}")
        
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if result and "result" in result:
            print("✅ Tool execution completed")
            tool_result = result["result"]
            if isinstance(tool_result, dict) and "content" in tool_result:
                content = tool_result["content"]
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            print(f"📄 {item['text']}")
            return result
        else:
            print("❌ Tool call failed")
            return {"error": "Tool execution failed"}
        
    async def _send_request(self, method: str, params: dict = None):
        """Send JSON-RPC request"""
        self.request_id += 1
        request = {"jsonrpc": "2.0", "id": self.request_id, "method": method}
        if params:
            request["params"] = params
            
        self.process.stdin.write((json.dumps(request) + "\n").encode())
        await self.process.stdin.drain()
        
        response_data = b""
        while True:
            try:
                chunk = await asyncio.wait_for(self.process.stdout.read(1024), timeout=10)
                if not chunk:
                    break
                response_data += chunk
                
                lines = response_data.decode('utf-8', errors='ignore').split('\n')
                for line in lines[:-1]:
                    if line.strip():
                        try:
                            response = json.loads(line.strip())
                            if response.get('id') == self.request_id:
                                return response
                        except:
                            continue
                response_data = lines[-1].encode()
            except asyncio.TimeoutError:
                break
        return None
        
    async def cleanup(self):
        """Clean up MCP process"""
        if self.process:
            print("🛑 Terminating MCP subprocess...")
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
                print("✅ MCP process terminated")
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self.process.kill()
                    await self.process.wait()
                    print("✅ MCP process terminated")
                except ProcessLookupError:
                    pass
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                if self.process.stdout:
                    self.process.stdout.close()
                if self.process.stderr:
                    self.process.stderr.close()
            except Exception:
                pass
            self.process = None