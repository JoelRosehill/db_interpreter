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

            for table_name in tables:
                buffer.write(f"TABLE: {table_name}\n")
                self.cursor.execute(f"PRAGMA table_info({quote_identifier(table_name)});")
                for column in self.cursor.fetchall():
                    buffer.write(f"  - {column[1]} ({column[2]})\n")
                buffer.write("\n")

            return buffer.getvalue()

    def generate_sql_code(self):
        with self._lock:
            buffer = io.StringIO()
            buffer.write("--- GENERATED SQL CODE ---\n\n")

            self.cursor.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL ORDER BY name;"
            )
            tables = self.cursor.fetchall()

            for table_name, create_sql in tables:
                if table_name == "sqlite_sequence":
                    continue

                create_statement = create_sql.strip()
                if not create_statement.endswith(";"):
                    create_statement += ";"
                buffer.write(create_statement + "\n")

                quoted_table = quote_identifier(table_name)
                self.cursor.execute(f"SELECT * FROM {quoted_table}")
                rows = self.cursor.fetchall()

                if rows:
                    self.cursor.execute(f"PRAGMA table_info({quoted_table});")
                    columns = [col[1] for col in self.cursor.fetchall()]
                    quoted_columns = ", ".join(quote_identifier(col) for col in columns)

                    for row in rows:
                        values = ", ".join(sql_literal(value) for value in row)
                        buffer.write(f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({values});\n")

                buffer.write("\n")

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
