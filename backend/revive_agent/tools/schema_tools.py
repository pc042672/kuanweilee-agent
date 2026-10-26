"""Schema exploration tools — database introspection."""

from revive_agent.tools._infra import get_profiler


def list_tables_in_schema_tool(schema_name: str) -> list[str]:
    """
    Lists tables in a specific schema.
    Use this when you know the schema to explore (e.g., 'report', 'public').

    Args:
        schema_name: The schema to list tables from (e.g., 'report', 'public')

    Returns:
        List of table names in the specified schema.
    """
    return get_profiler().list_tables(schema=schema_name)


def get_schema_tool(table_name: str) -> str:
    """
    Retrieves the schema (columns and types) for a specific table.
    Args:
        table_name: The name of the table (e.g., 'public.orders').
    """
    return get_profiler().get_table_schema(table_name)
