from dbtoolbox import QueryService


class DatabaseProfiler:
    """Schema introspection via the site's QueryService (bound parameters)."""

    def __init__(self, service: QueryService):
        self.service = service

    def get_table_schema(self, table_name: str):
        """Fetches column names and types for a specific table."""
        if "." in table_name:
            schema, table = table_name.split(".", 1)
        else:
            schema, table = "public", table_name

        sql = (
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        )
        results = self.service.execute(sql, params={"schema": schema, "table": table})

        if not results:
            return f"Table {schema}.{table} not found."

        schema_desc = [f"{row['column_name']} ({row['data_type']})" for row in results]
        return f"Schema for {schema}.{table}: " + ", ".join(schema_desc)

    def list_tables(self, schema="public"):
        """Lists all tables in a schema to help the Agent explore."""
        sql = (
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_type = 'BASE TABLE'"
        )
        results = self.service.execute(sql, params={"schema": schema})
        return [row["table_name"] for row in results]
