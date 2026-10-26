"""
Test Agent Module - For ADK Eval Testing

Exports individual agents instead of the full orchestrator
for unit-testing tool usage behavior.
"""
import sys
from pathlib import Path

# Add 'backend' directory to Python path for imports
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from google.adk.agents import LlmAgent
from revive_agent.tools import (
    list_tables_in_schema_tool,
    get_schema_tool,
    get_ontology_tool,
)

MODEL_NAME = "gemini-2.0-flash"

# DS-Agent for testing tool usage
root_agent = LlmAgent(
    name="DSAgent",
    model=MODEL_NAME,
    description="Data Scientist Agent - Analyzes context and proposes execution plans",
    instruction="""You are a Data Scientist Agent (DS-Agent) for testing.

## Your Role
Use tools to gather context based on user queries.

## Tools Available
- get_ontology_tool(): Get business data model
- list_tables_in_schema_tool(schema_name): List tables in a schema
- get_schema_tool(table_name): Get table columns/types

## IMPORTANT: Be Proactive with Tools
- If user mentions a table name → call get_schema_tool()
- If user mentions a schema name → call list_tables_in_schema_tool()
- If user mentions "ontology" → call get_ontology_tool()

After calling tools, briefly summarize what you found.
""",
    tools=[list_tables_in_schema_tool, get_schema_tool, get_ontology_tool],
)
