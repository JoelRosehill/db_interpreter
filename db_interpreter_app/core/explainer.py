def explain_sql_query(query):
    query = query.strip()
    if not query:
        return "Please enter a SQL query to explain."

    query_upper = query.upper()
    explanation = "This query "

    if query_upper.startswith("SELECT"):
        explanation += "retrieves data"

        select_part = query_upper.split("FROM")[0].replace("SELECT", "", 1).strip()
        if select_part == "*":
            explanation += " from all columns"
        elif "DISTINCT" in select_part:
            explanation += " with distinct values"
        else:
            explanation += " from specific columns"

        aggregate_tokens = ["COUNT(", "SUM(", "AVG(", "MIN(", "MAX("]
        if any(token in select_part for token in aggregate_tokens):
            explanation += " and aggregate calculations"

        if "FROM" in query_upper:
            from_part = query_upper.split("FROM", 1)[1]
            for clause in [" WHERE", " GROUP BY", " HAVING", " ORDER BY", " LIMIT"]:
                if clause in from_part:
                    from_part = from_part.split(clause, 1)[0]
            tables = [table.strip() for table in from_part.split(",") if table.strip()]
            if len(tables) == 1:
                explanation += f" from the '{tables[0]}' table"
            elif tables:
                quoted_tables = [f"'{table}'" for table in tables]
                explanation += f" from these tables: {', '.join(quoted_tables)}"

        if " JOIN " in query_upper or " JOIN\n" in query_upper:
            explanation += ", combining rows with a JOIN"
        if " WHERE " in query_upper:
            explanation += ", filtering rows"
        if " GROUP BY " in query_upper:
            explanation += ", grouping results"
        if " HAVING " in query_upper:
            explanation += ", filtering grouped results"
        if " ORDER BY " in query_upper:
            explanation += ", sorting output"
        if " LIMIT " in query_upper:
            explanation += ", and limiting the number of rows"

        return explanation + "."

    if query_upper.startswith("INSERT"):
        explanation += "adds new rows"
        if "INTO" in query_upper:
            after_into = query_upper.split("INTO", 1)[1].strip()
            table_name = after_into.split()[0] if after_into else ""
            table_name = table_name.strip("()")
            if table_name:
                explanation += f" into the '{table_name}' table"
        if "VALUES" in query_upper:
            explanation += " using explicit values"
        elif "SELECT" in query_upper:
            explanation += " by copying rows from another query"
        return explanation + "."

    if query_upper.startswith("UPDATE"):
        explanation += "modifies existing rows"
        after_update = query_upper.split("UPDATE", 1)[1].strip()
        table_name = after_update.split()[0] if after_update else ""
        table_name = table_name.strip("()")
        if table_name:
            explanation += f" in the '{table_name}' table"
        if " SET " in query_upper:
            explanation += ", changing selected columns"
        if " WHERE " in query_upper:
            explanation += " for rows that match the WHERE condition"
        else:
            explanation += ". Warning: there is no WHERE condition, so all rows are updated"
        return explanation + "."

    if query_upper.startswith("DELETE"):
        explanation += "removes rows"
        if "FROM" in query_upper:
            after_from = query_upper.split("FROM", 1)[1].strip()
            table_name = after_from.split()[0] if after_from else ""
            table_name = table_name.strip("()")
            if table_name:
                explanation += f" from the '{table_name}' table"
        if " WHERE " in query_upper:
            explanation += " for rows that match the WHERE condition"
        else:
            explanation += ". Warning: there is no WHERE condition, so all rows are deleted"
        return explanation + "."

    if query_upper.startswith("CREATE"):
        if "TABLE" in query_upper:
            return "This query creates a new table."
        if "INDEX" in query_upper:
            return "This query creates an index to improve lookup performance."
        if "VIEW" in query_upper:
            return "This query creates a view based on a SELECT statement."
        return "This query creates a new database object."

    if query_upper.startswith("DROP"):
        warning = " Warning: this cannot be undone."
        if "TABLE" in query_upper:
            return "This query drops a table and all data inside it." + warning
        if "INDEX" in query_upper:
            return "This query drops an index." + warning
        if "VIEW" in query_upper:
            return "This query drops a view." + warning
        return "This query drops a database object." + warning

    if query_upper.startswith("ALTER"):
        explanation = "This query alters an existing database object"
        if "ADD" in query_upper:
            explanation += " by adding a new part"
        elif "DROP" in query_upper:
            explanation += " by removing a part"
        elif "MODIFY" in query_upper:
            explanation += " by changing a definition"
        return explanation + "."

    if len(query) > 100:
        return "This query executes command text starting with: " + query[:100] + "..."
    return "This query executes command text: " + query
