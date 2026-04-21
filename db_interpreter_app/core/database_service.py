import io
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

from .constants import (
    DEFAULT_DB_FILE,
    MODE_NOSQL,
    MODE_PYMYSQL,
    MODE_SQL,
    QUERY_HISTORY_LIMIT,
    SAFE_PYTHON_BUILTINS,
)
from .explainer import explain_sql_query
from .sql_utils import quote_identifier, split_sql_statements, sql_literal


TRANSACTION_PREFIXES = ("COMMIT", "ROLLBACK", "BEGIN", "SAVEPOINT")


class MockPyMySQL:
    def __init__(self, connection):
        self.connection = connection

    def connect(self, **kwargs):
        return self.connection


class DatabaseService:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or os.getcwd()).resolve()
        self._lock = threading.RLock()

        self.current_db_file = DEFAULT_DB_FILE
        self.conn = None
        self.cursor = None

        self.query_history = []
        self.last_select_columns = []
        self.last_select_rows = []

        self._connect(self.current_db_file)

    def _connect(self, db_name):
        db_path = self.base_dir / db_name
        db_path.touch(exist_ok=True)

        if self.conn is not None:
            self.conn.close()

        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.current_db_file = db_name

    def _normalize_db_name(self, name):
        if name is None:
            raise ValueError("Database name is required.")

        clean_name = os.path.basename(name.strip())
        if not clean_name:
            raise ValueError("Database name cannot be empty.")

        if clean_name in {".", ".."}:
            raise ValueError("Invalid database name.")

        if not clean_name.endswith(".db"):
            clean_name += ".db"

        return clean_name

    def _add_to_history(self, query):
        if query in self.query_history:
            self.query_history.remove(query)

        self.query_history.insert(0, query)
        self.query_history = self.query_history[:QUERY_HISTORY_LIMIT]

    def list_databases(self):
        with self._lock:
            files = sorted(path.name for path in self.base_dir.glob("*.db"))
            if DEFAULT_DB_FILE not in files:
                files.append(DEFAULT_DB_FILE)
            return files

    def get_tables(self):
        with self._lock:
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            return [name for (name,) in self.cursor.fetchall() if name != "sqlite_sequence"]

    def get_bootstrap_state(self):
        with self._lock:
            return {
                "currentDb": self.current_db_file,
                "databases": self.list_databases(),
                "tables": self.get_tables(),
                "history": list(self.query_history),
            }

    def switch_database(self, name):
        with self._lock:
            new_db = self._normalize_db_name(name)
            if new_db == self.current_db_file:
                return self.get_bootstrap_state()

            if self.conn.in_transaction:
                raise RuntimeError("Pending transaction detected. Commit or rollback before switching databases.")

            self._connect(new_db)
            self.last_select_columns = []
            self.last_select_rows = []
            state = self.get_bootstrap_state()
            state["status"] = f"Switched to database: {new_db}"
            return state

    def create_database(self, name):
        with self._lock:
            new_db = self._normalize_db_name(name)

            if self.conn.in_transaction:
                raise RuntimeError("Pending transaction detected. Commit or rollback before creating databases.")

            self._connect(new_db)
            self.last_select_columns = []
            self.last_select_rows = []

            state = self.get_bootstrap_state()
            state["status"] = f"Created and switched to database: {new_db}"
            return state

    def execute(self, mode, code, autocommit=True):
        with self._lock:
            mode = (mode or MODE_SQL).strip()

            if mode == MODE_SQL:
                return self._execute_sql(code, autocommit)
            if mode == MODE_NOSQL:
                return self._execute_nosql(code, autocommit)
            if mode == MODE_PYMYSQL:
                return self._execute_python_mock(code, autocommit)

            raise ValueError(f"Unsupported mode: {mode}")

    def _execute_sql(self, code, autocommit):
        start = time.perf_counter()
        statements = split_sql_statements((code or "").strip())
        if not statements:
            raise ValueError("Please enter at least one SQL statement.")

        output_lines = []
        table_columns = []
        table_rows = []
        row_count = None

        try:
            for statement in statements:
                self.cursor.execute(statement)

                statement_upper = statement.strip().upper()
                if statement and not statement_upper.startswith(TRANSACTION_PREFIXES):
                    self._add_to_history(statement)

                if self.cursor.description:
                    rows = self.cursor.fetchall()
                    columns = [desc[0] for desc in self.cursor.description]

                    table_columns = columns
                    table_rows = rows
                    row_count = len(rows)

                    if not rows:
                        output_lines.append("(No results found)")
                else:
                    preview = statement[:60] + ("..." if len(statement) > 60 else "")
                    if self.cursor.rowcount >= 0:
                        row_count = self.cursor.rowcount
                        output_lines.append(f"Executed: {preview} (rows affected: {self.cursor.rowcount})")
                    else:
                        output_lines.append(f"Executed: {preview}")

            if autocommit and self.conn.in_transaction:
                self.conn.commit()
                status = "Autocommit: ON (last run committed)"
            elif not autocommit:
                status = "Autocommit: OFF (pending transaction)"
            else:
                status = "Executed successfully"

            self.last_select_columns = table_columns
            self.last_select_rows = table_rows

            return {
                "ok": True,
                "mode": MODE_SQL,
                "status": status,
                "output": "\n".join(output_lines),
                "columns": table_columns,
                "rows": table_rows,
                "rowCount": row_count,
                "history": list(self.query_history),
                "tables": self.get_tables(),
                "executionMs": int((time.perf_counter() - start) * 1000),
            }
        except Exception:
            if autocommit and self.conn.in_transaction:
                self.conn.rollback()
            raise

    def _execute_nosql(self, code, autocommit):
        start = time.perf_counter()
        lines = [(line or "").strip() for line in (code or "").splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            raise ValueError("Please enter at least one NoSQL command.")

        output_lines = []
        table_columns = []
        table_rows = []
        inserted_count = 0
        row_count = None

        try:
            for line in lines:
                find_match = re.fullmatch(r"db\.(\w+)\.find\((.*)\)\s*;?", line)
                if find_match:
                    table_name = find_match.group(1)
                    self.cursor.execute(f"SELECT * FROM {quote_identifier(table_name)}")
                    rows = self.cursor.fetchall()
                    columns = [desc[0] for desc in self.cursor.description]

                    table_columns = columns
                    table_rows = rows
                    row_count = len(rows)

                    if not rows:
                        output_lines.append(f"No documents found in {table_name}.")
                    else:
                        for row in rows:
                            doc = dict(zip(columns, row))
                            output_lines.append(json.dumps(doc, ensure_ascii=True))
                    continue

                insert_match = re.fullmatch(r"db\.(\w+)\.insertOne\((.*)\)\s*;?", line)
                if insert_match:
                    table_name = insert_match.group(1)
                    data = json.loads(insert_match.group(2))

                    if not isinstance(data, dict) or not data:
                        raise ValueError("insertOne() requires a non-empty JSON object.")

                    columns = list(data.keys())
                    quoted_columns = ", ".join(quote_identifier(col) for col in columns)
                    placeholders = ", ".join("?" for _ in columns)
                    values = tuple(data[col] for col in columns)

                    self.cursor.execute(
                        f"INSERT INTO {quote_identifier(table_name)} ({quoted_columns}) VALUES ({placeholders})",
                        values,
                    )
                    inserted_count += 1
                    row_count = inserted_count
                    output_lines.append(f"Inserted document into {table_name}.")
                    continue

                output_lines.append(f"Command not recognized by mock engine: {line}")

            if inserted_count and autocommit and self.conn.in_transaction:
                self.conn.commit()
                status = "NoSQL run committed"
            elif inserted_count and not autocommit:
                status = "NoSQL run pending commit"
            else:
                status = "NoSQL run completed"

            self.last_select_columns = table_columns
            self.last_select_rows = table_rows

            return {
                "ok": True,
                "mode": MODE_NOSQL,
                "status": status,
                "output": "\n".join(output_lines),
                "columns": table_columns,
                "rows": table_rows,
                "rowCount": row_count,
                "history": list(self.query_history),
                "tables": self.get_tables(),
                "executionMs": int((time.perf_counter() - start) * 1000),
            }
        except Exception:
            if autocommit and self.conn.in_transaction:
                self.conn.rollback()
            raise

    def _execute_python_mock(self, code, autocommit):
        start = time.perf_counter()
        output_lines = []

        def mock_print(*args):
            output_lines.append(" ".join(str(arg) for arg in args))

        local_env = {
            "pymysql": MockPyMySQL(self.conn),
            "print": mock_print,
        }
        safe_globals = {"__builtins__": SAFE_PYTHON_BUILTINS}

        clean_code = re.sub(r"^\s*import\s+pymysql\s*$", "", code or "", flags=re.MULTILINE)
        exec(clean_code, safe_globals, local_env)

        if autocommit and self.conn.in_transaction:
            self.conn.commit()
            status = "PyMySQL mock committed"
        elif not autocommit and self.conn.in_transaction:
            status = "PyMySQL mock pending commit"
        else:
            status = "PyMySQL mock completed"

        return {
            "ok": True,
            "mode": MODE_PYMYSQL,
            "status": status,
            "output": "\n".join(output_lines) if output_lines else "Python script completed.",
            "columns": [],
            "rows": [],
            "rowCount": None,
            "history": list(self.query_history),
            "tables": self.get_tables(),
            "executionMs": int((time.perf_counter() - start) * 1000),
        }

    def explain(self, query):
        with self._lock:
            return explain_sql_query(query or "")

    def view_schema(self):
        with self._lock:
            buffer = io.StringIO()
            buffer.write("--- DATABASE SCHEMA ---\n\n")

            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = [name for (name,) in self.cursor.fetchall() if name != "sqlite_sequence"]

            if not tables:
                buffer.write("Your database is empty. Create a table first!\n")
                return buffer.getvalue()

            relationship_lines = []

            for table_name in tables:
                buffer.write(f"TABLE: {table_name}\n")

                self.cursor.execute(f"PRAGMA table_info({quote_identifier(table_name)});")
                columns = self.cursor.fetchall()

                primary_key_columns = [col[1] for col in sorted(columns, key=lambda col: col[5]) if col[5] > 0]

                if primary_key_columns:
                    buffer.write(f"  Primary Key: {', '.join(primary_key_columns)}\n")
                else:
                    buffer.write("  Primary Key: (none)\n")

                buffer.write("  Columns:\n")
                for column in columns:
                    _, column_name, column_type, not_null, default_value, pk_order = column

                    tags = []
                    if pk_order > 0:
                        if len(primary_key_columns) > 1:
                            tags.append(f"PK#{pk_order}")
                        else:
                            tags.append("PK")
                    if not_null:
                        tags.append("NOT NULL")
                    if default_value is not None:
                        tags.append(f"DEFAULT {default_value}")

                    extra = f" [{' | '.join(tags)}]" if tags else ""
                    buffer.write(f"    - {column_name} ({column_type}){extra}\n")

                self.cursor.execute(f"PRAGMA foreign_key_list({quote_identifier(table_name)});")
                fk_rows = self.cursor.fetchall()

                if not fk_rows:
                    buffer.write("  Foreign Keys: (none)\n")
                else:
                    buffer.write("  Foreign Keys:\n")

                    foreign_key_groups = {}
                    for row in fk_rows:
                        fk_id, seq, target_table, source_col, target_col, on_update, on_delete, match_rule = row
                        foreign_key_groups.setdefault(fk_id, []).append(
                            {
                                "seq": seq,
                                "target_table": target_table,
                                "source_col": source_col,
                                "target_col": target_col,
                                "on_update": on_update,
                                "on_delete": on_delete,
                                "match_rule": match_rule,
                            }
                        )

                    for fk_id in sorted(foreign_key_groups):
                        group_rows = sorted(foreign_key_groups[fk_id], key=lambda item: item["seq"])
                        target_table = group_rows[0]["target_table"]
                        source_cols = [item["source_col"] for item in group_rows]
                        target_cols = [item["target_col"] for item in group_rows]

                        source_label = ", ".join(source_cols)
                        target_label = ", ".join(target_cols)
                        on_update = group_rows[0]["on_update"]
                        on_delete = group_rows[0]["on_delete"]
                        match_rule = group_rows[0]["match_rule"]

                        buffer.write(
                            f"    - ({source_label}) -> {target_table}.({target_label}) "
                            f"[ON UPDATE {on_update}, ON DELETE {on_delete}, MATCH {match_rule}]\n"
                        )

                        relationship_lines.append(
                            f"{table_name}.({source_label}) -> {target_table}.({target_label})"
                        )

                buffer.write("\n")

            buffer.write("--- PK/FK CONNECTIONS ---\n")
            if relationship_lines:
                for line in relationship_lines:
                    buffer.write(f"- {line}\n")
            else:
                buffer.write("No foreign key relationships found.\n")

            return buffer.getvalue()

    def _get_table_definitions(self):
        self.cursor.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL ORDER BY name;"
        )
        table_definitions = {}
        for table_name, create_sql in self.cursor.fetchall():
            if table_name == "sqlite_sequence":
                continue
            table_definitions[table_name] = create_sql
        return table_definitions

    def _sort_tables_by_fk_dependencies(self, table_names):
        table_set = set(table_names)
        dependencies = {}

        for table_name in table_names:
            self.cursor.execute(f"PRAGMA foreign_key_list({quote_identifier(table_name)});")
            fk_rows = self.cursor.fetchall()

            referenced_tables = {
                row[2]
                for row in fk_rows
                if row[2] in table_set and row[2] != table_name
            }
            dependencies[table_name] = referenced_tables

        remaining = {name: set(values) for name, values in dependencies.items()}

        ordered = []
        ready = sorted(name for name in table_names if not remaining[name])

        while ready:
            current = ready.pop(0)
            ordered.append(current)

            for candidate in table_names:
                if current in remaining[candidate]:
                    remaining[candidate].remove(current)
                    if not remaining[candidate] and candidate not in ordered and candidate not in ready:
                        ready.append(candidate)
            ready.sort()

        unresolved = sorted(name for name in table_names if name not in ordered)
        return ordered + unresolved, unresolved

    def _get_table_columns(self, table_name):
        self.cursor.execute(f"PRAGMA table_info({quote_identifier(table_name)});")
        return self.cursor.fetchall()

    def _collect_foreign_key_violations(self):
        self.cursor.execute("PRAGMA foreign_key_check;")
        fk_violations = []

        for child_table, rowid, parent_table, fk_id in self.cursor.fetchall():
            self.cursor.execute(f"PRAGMA foreign_key_list({quote_identifier(child_table)});")
            fk_rows = [row for row in self.cursor.fetchall() if row[0] == fk_id]
            fk_rows.sort(key=lambda row: row[1])

            source_columns = [row[3] for row in fk_rows]
            target_columns = [row[4] for row in fk_rows]

            source_values = []
            if rowid is not None:
                child_columns = [col[1] for col in self._get_table_columns(child_table)]
                self.cursor.execute(f"SELECT * FROM {quote_identifier(child_table)} WHERE rowid = ?", (rowid,))
                child_row = self.cursor.fetchone()
                if child_row is not None:
                    child_map = dict(zip(child_columns, child_row))
                    source_values = [child_map.get(col) for col in source_columns]

            fk_violations.append(
                {
                    "child_table": child_table,
                    "rowid": rowid,
                    "parent_table": parent_table,
                    "source_columns": source_columns,
                    "target_columns": target_columns,
                    "source_values": source_values,
                }
            )

        return fk_violations

    def _format_fk_violation_message(self, fk_violations):
        lines = [
            "Cannot generate SQL because source data contains broken foreign-key references.",
            "Fix these rows first, then run Generate SQL again:",
        ]

        for issue in fk_violations:
            child_table = issue["child_table"]
            rowid = issue["rowid"]
            parent_table = issue["parent_table"]
            source_columns = issue["source_columns"]
            target_columns = issue["target_columns"]
            source_values = issue["source_values"]

            if source_values:
                pairs = ", ".join(
                    f"{column}={sql_literal(value)}"
                    for column, value in zip(source_columns, source_values)
                )
            else:
                pairs = ", ".join(source_columns)

            row_label = f"rowid {rowid}" if rowid is not None else "rowid unknown"
            lines.append(
                f"- {child_table} ({row_label}): ({pairs}) references missing "
                f"{parent_table}.({', '.join(target_columns)})"
            )

        return "\n".join(lines)

    def _fetch_rows_for_export(self, table_name):
        quoted_table = quote_identifier(table_name)
        columns_info = self._get_table_columns(table_name)
        column_names = [col[1] for col in columns_info]
        pk_columns = [col[1] for col in sorted(columns_info, key=lambda col: col[5]) if col[5] > 0]

        if pk_columns:
            order_by = ", ".join(quote_identifier(col) for col in pk_columns)
            self.cursor.execute(f"SELECT * FROM {quoted_table} ORDER BY {order_by}")
            return column_names, self.cursor.fetchall()

        try:
            self.cursor.execute(f"SELECT * FROM {quoted_table} ORDER BY rowid")
            return column_names, self.cursor.fetchall()
        except sqlite3.OperationalError:
            self.cursor.execute(f"SELECT * FROM {quoted_table}")
            return column_names, self.cursor.fetchall()

    def generate_sql_code(self):
        with self._lock:
            fk_violations = self._collect_foreign_key_violations()
            if fk_violations:
                raise ValueError(self._format_fk_violation_message(fk_violations))

            buffer = io.StringIO()
            buffer.write("-- GENERATED SQL CODE --\n\n")

            table_definitions = self._get_table_definitions()
            if not table_definitions:
                buffer.write("-- No tables found.\n")
                return buffer.getvalue()

            table_names = sorted(table_definitions)
            ordered_tables, unresolved = self._sort_tables_by_fk_dependencies(table_names)

            if unresolved:
                unresolved_list = ", ".join(unresolved)
                buffer.write(f"-- Cyclic FK dependencies detected for: {unresolved_list}\n")
                buffer.write("-- Using deferred FK checks so transaction validates only at commit.\n\n")

            buffer.write("PRAGMA foreign_keys = ON;\n")
            buffer.write("PRAGMA defer_foreign_keys = ON;\n")
            buffer.write("BEGIN TRANSACTION;\n\n")

            buffer.write("-- 1. CREATE TABLES (parent -> child order)\n")
            for table_name in ordered_tables:
                create_sql = table_definitions[table_name]
                create_statement = create_sql.strip()
                if not create_statement.endswith(";"):
                    create_statement += ";"
                buffer.write(create_statement + "\n\n")

            buffer.write("-- 2. INSERT DATA (parent -> child order)\n")
            for table_name in ordered_tables:
                quoted_table = quote_identifier(table_name)
                columns, rows = self._fetch_rows_for_export(table_name)

                if not rows:
                    continue

                quoted_columns = ", ".join(quote_identifier(col) for col in columns)

                for row in rows:
                    values = ", ".join(sql_literal(value) for value in row)
                    buffer.write(f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({values});\n")

                buffer.write("\n")

            buffer.write("COMMIT;\n")
            buffer.write("PRAGMA defer_foreign_keys = OFF;\n")
            buffer.write("PRAGMA foreign_keys = ON;\n")

            return buffer.getvalue()

    def nuke_database(self):
        with self._lock:
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [name for (name,) in self.cursor.fetchall() if name != "sqlite_sequence"]

            for table_name in tables:
                self.cursor.execute(f"DROP TABLE {quote_identifier(table_name)};")

            if self.conn.in_transaction:
                self.conn.commit()

            self.last_select_columns = []
            self.last_select_rows = []

            return {
                "status": "Database reset complete.",
                "tables": self.get_tables(),
            }

    def commit(self):
        with self._lock:
            if self.conn.in_transaction:
                self.conn.commit()
                return "Transaction committed."
            return "No pending transaction to commit."

    def rollback(self):
        with self._lock:
            if self.conn.in_transaction:
                self.conn.rollback()
                return "Transaction rolled back."
            return "No pending transaction to roll back."

    def close(self):
        with self._lock:
            if self.conn is not None:
                self.conn.close()
                self.conn = None
                self.cursor = None
