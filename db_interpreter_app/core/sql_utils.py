import sqlite3


def quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    return "'" + str(value).replace("'", "''") + "'"
def split_sql_statements(sql_block):
    statements = []
    buffer = ""

    for char in sql_block:
        buffer += char
        if char == ";" and sqlite3.complete_statement(buffer):
            statement = buffer.strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            buffer = ""

    if buffer.strip():
        statements.append(buffer.strip())

    return statements
