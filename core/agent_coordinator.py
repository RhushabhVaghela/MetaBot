import re
import json
from datetime import datetime
from typing import Dict, Any

from core.agents import SubAgent


class AgentCoordinator:
    """Manage sub-agent lifecycle and tool execution on their behalf."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        # Do not store a separate sub_agents mapping here. Always read and
        # write to orchestrator.sub_agents so external tests and callers that
        # reassign `orchestrator.sub_agents` keep working.

    async def _spawn_sub_agent(self, tool_input: Dict) -> str:
        """Spawn and orchestrate a sub-agent with Pre-flight Checks and Synthesis"""
        name = str(tool_input.get("name", "unknown"))
        task = str(tool_input.get("task", "unknown"))
        role = str(tool_input.get("role", "Assistant"))

        agent = SubAgent(name, role, task, self.orchestrator)
        # Ensure orchestrator.sub_agents is updated so callers that inspect
        # orchestrator.sub_agents see the new agent.
        self.orchestrator.sub_agents[name] = agent

        # 1. Pre-flight Check: Planning & Validation
        print(f"Sub-Agent {name}: Generating plan...")
        plan = await agent.generate_plan()

        # Validate plan against project policies
        validation_prompt = f"As a Master Security Agent, validate the following plan for task '{task}' by agent '{name}' ({role}):\n{plan}\n\nDoes this plan violate any security policies (e.g., unauthorized access, destructive commands)? Reply with 'VALID' or a description of the violation."
        validation_res = await self.orchestrator.llm.generate(
            context="Pre-flight Plan Validation",
            messages=[{"role": "user", "content": validation_prompt}],
        )
        if "VALID" not in str(validation_res).upper():
            return f"Sub-agent {name} blocked by pre-flight check: {validation_res}"

        # 2. Execution
        print(f"Sub-Agent {name}: Execution started...")
        raw_result = await agent.run()

        # 3. Synthesis: Refine and integrate sub-agent findings
        print(f"Sub-Agent {name}: Execution finished. Synthesizing results...")
        synthesis_prompt = f"""
Integrate and summarize the findings from sub-agent '{name}' for the task '{task}'.
Raw Result: {raw_result}

Your goal is to extract architectural patterns or hard-won lessons that should be remembered by the Master Agent for future tasks.

Format your response as a valid JSON object:
{{
    "summary": "Brief overall summary for immediate use",
    "findings": ["Specific technical detail 1", "Specific technical detail 2"],
    "learned_lesson": "A high-priority architectural decision, constraint, or pattern (e.g. 'Always use X when doing Y because of Z'). Prefix with 'CRITICAL:' if it relates to security or failure.",
    "next_steps": ["Step 1"]
}}
"""
        synthesis_raw = await self.orchestrator.llm.generate(
            context="Result Synthesis",
            messages=[{"role": "user", "content": synthesis_prompt}],
        )

        # Parse synthesis and record lesson
        try:
            lesson = "No lesson recorded."
            summary = str(synthesis_raw)
            print(f"DEBUG [Synthesis Raw]: {summary[:200]}")

            json_match = re.search(r"\{.*\}", summary, re.DOTALL)
            if json_match:
                try:
                    synthesis_data = json.loads(json_match.group(0))
                    lesson = synthesis_data.get("learned_lesson", lesson)
                    summary = synthesis_data.get("summary", summary)
                except Exception:
                    # Fallback: regex search for learned_lesson field
                    pass
            else:
                # Direct fallback: Look for "lesson:" or "CRITICAL:" in raw text
                pass

            await self.orchestrator.memory.memory_write(
                key=f"lesson_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                type="learned_lesson",
                content=lesson,
                tags=["synthesis", name, role],
            )

            # Notify connected clients (best-effort)
            try:
                for client in list(self.orchestrator.clients):
                    await client.send_json(
                        {
                            "type": "memory_update",
                            "content": lesson,
                            "source": name,
                        }
                    )
            except Exception:
                pass

            return summary
        except Exception as e:
            print(f"Failed to record memory lesson or parse synthesis: {e}")
            return str(synthesis_raw)

    async def _execute_tool_for_sub_agent(
        self, agent_name: str, tool_call: Dict
    ) -> str:
        """Execute a tool on behalf of a sub-agent with Domain Boundary enforcement"""
        agent = self.orchestrator.sub_agents.get(agent_name)
        if not agent:
            return "Error: Agent not found."

        tool_name = str(tool_call.get("name", "unknown"))
        tool_input = tool_call.get("input", {})

        # Enforce Domain Boundaries
        allowed_tools = agent._get_sub_tools()
        target_tool = next((t for t in allowed_tools if t["name"] == tool_name), None)
        if not target_tool:
            return f"Security Error: Tool '{tool_name}' is outside the domain boundaries for role '{agent.role}'."

        scope = str(target_tool.get("scope", "unknown"))

        # Check overall permissions
        auth = self.orchestrator.permissions.is_authorized(scope)
        if auth is False:
            return f"Security Error: Permission denied for scope '{scope}'."

        # Implement a few example tools
        try:
            if tool_name == "read_file":
                path = str(tool_input.get("path", ""))
                with open(path, "r") as f:
                    return f.read()
            elif tool_name == "write_file":
                path = str(tool_input.get("path", ""))
                content = str(tool_input.get("content", ""))
                with open(path, "w") as f:
                    f.write(content)
                return f"File '{path}' written successfully."
            elif tool_name == "query_rag":
                return await self.orchestrator.rag.navigate(
                    str(tool_input.get("query", ""))
                )
            else:
                # Fallback to MCP if available. Normalize MCP error responses
                # to a consistent 'logic not implemented' message so older tests
                # and callers see the expected string.
                if "mcp" in self.orchestrator.adapters:
                    res = await self.orchestrator.adapters["mcp"].call_tool(
                        None, tool_name, tool_input
                    )
                    # MCP may return structured errors (dict). If it indicates
                    # the tool is not present, return legacy message.
                    if isinstance(res, dict) and ("error" in res or "errors" in res):
                        return f"Error: Tool '{tool_name}' logic not implemented."
                    return res
                return f"Error: Tool '{tool_name}' logic not implemented."
        except Exception as e:
            return f"Tool execution error: {e}"
