import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import csv
import time
import re
import json
import os

# Database language modes
MODE_SQL = "SQL"
MODE_NOSQL = "NoSQL"
MODE_PYMYSQL = "PyMySQL"

current_mode = MODE_SQL
last_select_results = []  # Stores last SELECT query results for export

# ---------------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------------
# This creates a local dummy database file in your folder.
conn = sqlite3.connect("study_database.db")
cursor = conn.cursor()

# Global variables for tracking state
query_history = []  # Stores last 10 queries
last_select_results = []  # Stores last SELECT query results for export
current_db_file = "study_database.db"  # Track current database file

# List of SQL keywords for autocompletion
SQL_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE", 
    "CREATE", "TABLE", "DROP", "ALTER", "JOIN", "INNER", "LEFT", 
    "RIGHT", "OUTER", "ON", "GROUP BY", "ORDER BY", "HAVING",
    "UNION", "INTERSECT", "EXCEPT", "VALUES", "SET", "INTO",
    "COMMIT", "ROLLBACK", "BEGIN", "TRANSACTION", "SAVEPOINT",
    "DISTINCT", "AS", "NOT", "NULL", "AND", "OR", "LIKE", "BETWEEN", 
    "IN", "EXISTS", "CASE", "WHEN", "THEN", "ELSE", "END"
]

class SyntaxHighlightingText(tk.Text):
    def __init__(self, *args, **kwargs):
        tk.Text.__init__(self, *args, **kwargs)
        self.tag_configure("keyword", foreground="#0000FF", font=("Courier", 10, "bold"))
        self.tag_configure("operator", foreground="#FF0000")
        self.tag_configure("string", foreground="#008000")
        # --- AUTOCOMPLETE STATE ---
        self.tag_configure("ghost", foreground="grey")
        self.matches = []
        self.match_index = 0
        self.ghost_start = None
        self.ghost_length = 0
        
        # Key bindings for autocomplete
        self.bind("<KeyPress>", self.on_key_press)
        self.bind("<KeyRelease>", self.on_key_release)
        self.bind("<Tab>", self.on_tab)
        
    def clear_ghost(self):
        """Removes the grey suggestion text."""
        if self.ghost_start:
            self.delete(self.ghost_start, f"{self.ghost_start}+{self.ghost_length}c")
            self.ghost_start = None
            self.ghost_length = 0

    def get_current_word_info(self):
        """Gets the word immediately before the cursor."""
        line_start = self.index("insert linestart")
        insert_pos = self.index("insert")
        text_before = self.get(line_start, insert_pos)
        
        # Regex to find the word immediately to the left of the cursor
        match = re.search(r'\b([a-zA-Z_]+)$', text_before)
        if match:
            word = match.group(1)
            start_index = f"insert-{len(word)}c"
            return word, start_index
        return None, None

    def show_suggestion(self):
        """Finds and displays the grey ghost text suffix."""
        self.clear_ghost()
        word, start_index = self.get_current_word_info()
        
        if not word:
            self.matches = []
            return

        # Find matching keywords from SQL_KEYWORDS list
        self.matches = [kw for kw in SQL_KEYWORDS if kw.upper().startswith(word.upper()) and len(kw) > len(word)]
        
        if self.matches:
            self.match_index = 0
            match_word = self.matches[0]
            
            # Match the user's case (e.g., if they type 'inse', suggest 'rt' instead of 'RT')
            if word.islower():
                match_word = match_word.lower()
                
            suggestion = match_word[len(word):]
            
            # Insert ghost text
            insert_pos = self.index("insert")
            self.insert(insert_pos, suggestion, "ghost")
            self.ghost_start = insert_pos
            self.ghost_length = len(suggestion)
            
            # Move cursor back to before the ghost text so the user can keep typing normally
            self.mark_set("insert", insert_pos)
            
    def on_key_press(self, event):
        """Clears ghost text before actual typing happens."""
        # If typing normal characters, clear ghost so it doesn't get pushed forward
        if event.keysym not in ('Tab', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R'):
            self.clear_ghost()
            
        # Prevent default Tab spacing if we are currently looking at suggestions
        if event.keysym == 'Tab' and self.matches:
            return "break"

    def on_key_release(self, event):
        """Triggers the suggestion logic after typing."""
        # Reset cycling if user navigates away or types a separator
        if event.keysym in ('space', 'Return', 'Left', 'Right', 'Up', 'Down'):
            self.matches = []
            self.clear_ghost()
            return
            
        # Ignore modifier keys and Tab (Tab is handled separately)
        if event.keysym in ('Tab', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R'):
            return

        self.show_suggestion()

    def on_tab(self, event):
        """Handles accepting the autocomplete and cycling to next options."""
        if not self.matches:
            return None # Allow normal tab behavior (indenting)

        if self.ghost_start:
            # 1st Tab Press: Accept the current ghost text
            self.clear_ghost()
            word, start_index = self.get_current_word_info()
            
            match_word = self.matches[self.match_index]
            if word.islower():
                match_word = match_word.lower()
            
            completion = match_word[len(word):]
            self.insert("insert", completion)
            # Cursor automatically moves to the end of the newly inserted word
        else:
            # 2nd+ Tab Press: Cycle to the next suggestion in the list
            current_word, start_index = self.get_current_word_info()
            if not current_word:
                self.matches = []
                return "break"

            # Increment index and wrap around
            self.match_index = (self.match_index + 1) % len(self.matches)
            next_match = self.matches[self.match_index]
            
            if current_word.islower():
                next_match = next_match.lower()

            # Replace the currently accepted word with the next option
            self.delete(start_index, "insert")
            self.insert("insert", next_match)

        return "break" # Prevent default tab behavior
        
    def highlight(self, event=None):
        """Color-code SQL keywords in the text."""
        # Remove existing tags
        for tag in ["keyword", "operator", "string"]:
            self.tag_remove(tag, "1.0", tk.END)
        
        content = self.get("1.0", tk.END)
        
        # SQL keywords to highlight
        keywords = [
            "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE", 
            "CREATE", "TABLE", "DROP", "ALTER", "JOIN", "INNER", "LEFT", 
            "RIGHT", "OUTER", "ON", "GROUP BY", "ORDER BY", "HAVING",
            "UNION", "INTERSECT", "EXCEPT", "VALUES", "SET", "INTO",
            "COMMIT", "ROLLBACK", "BEGIN", "TRANSACTION", "SAVEPOINT"
        ]
        
        # Highlight keywords (case insensitive)
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            for match in re.finditer(pattern, content, re.IGNORECASE):
                start = f"1.0 + {match.start()} chars"
                end = f"1.0 + {match.end()} chars"
                self.tag_add("keyword", start, end)
        
        # Highlight operators
        operators = ["=", ">", "<", ">=", "<=", "!=", "<>", "+", "-", "*", "/", "%"]
        for op in operators:
            start = "1.0"
            while True:
                pos = self.search(op, start, tk.END, regexp=False)
                if not pos:
                    break
                end = f"{pos}+{len(op)}c"
                self.tag_add("operator", pos, end)
                start = end
        
        # Highlight strings (single and double quoted)
        for quote in ["'", '"']:
            start = "1.0"
            while True:
                pos = self.search(quote, start, tk.END, regexp=False)
                if not pos:
                    break
                # Find matching closing quote
                search_start = f"{pos}+1c"
                end_pos = self.search(quote, search_start, tk.END, regexp=False)
                if not end_pos:
                    break
                end = f"{end_pos}+1c"
                self.tag_add("string", pos, end)
                start = end
        
        # Highlight strings (single and double quoted)
        for quote in ["'", '"']:
            start = "1.0"
            while True:
                pos = self.search(quote, start, tk.END, regexp=False)
                if not pos:
                    break
                # Find matching closing quote
                search_start = f"{pos}+1c"
                end_pos = self.search(quote, search_start, tk.END, regexp=False)
                if not end_pos:
                    break
                end = f"{end_pos}+1c"
                self.tag_add("string", pos, end)
                start = end
        
    def highlight(self, event=None):
        # Remove existing tags
        for tag in ["keyword", "operator", "string", "error_bg"]:
            self.tag_remove(tag, "1.0", tk.END)
        
        content = self.get("1.0", tk.END)
        
        # SQL keywords to highlight
        keywords = [
            "SELECT", "FROM", "WHERE", "INSERT", "UPDATE", "DELETE", 
            "CREATE", "TABLE", "DROP", "ALTER", "JOIN", "INNER", "LEFT", 
            "RIGHT", "OUTER", "ON", "GROUP BY", "ORDER BY", "HAVING",
            "UNION", "INTERSECT", "EXCEPT", "VALUES", "SET", "INTO",
            "COMMIT", "ROLLBACK", "BEGIN", "TRANSACTION", "SAVEPOINT"
        ]
        
        # Highlight keywords (case insensitive)
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            for match in re.finditer(pattern, content, re.IGNORECASE):
                start = f"1.0 + {match.start()} chars"
                end = f"1.0 + {match.end()} chars"
                self.tag_add("keyword", start, end)
        
        # Highlight operators
        operators = ["=", ">", "<", ">=", "<=", "!=", "<>", "+", "-", "*", "/", "%"]
        for op in operators:
            start = "1.0"
            while True:
                pos = self.search(op, start, tk.END, regexp=False)
                if not pos:
                    break
                end = f"{pos}+{len(op)}c"
                self.tag_add("operator", pos, end)
                start = end
        
        # Highlight strings (single and double quoted)
        for quote in ["'", '"']:
            start = "1.0"
            while True:
                pos = self.search(quote, start, tk.END, regexp=False)
                if not pos:
                    break
                # Find matching closing quote
                search_start = f"{pos}+1c"
                end_pos = self.search(quote, search_start, tk.END, regexp=False)
                if not end_pos:
                    break
                end = f"{end_pos}+1c"
                self.tag_add("string", pos, end)
                start = end

# ---------------------------------------------------------
# APPLICATION LOGIC
# ---------------------------------------------------------
def execute_sql_block():
    """Executes the block of SQL from the input box."""
    # Get all text from the input box
    sql_block = text_input.get("1.0", tk.END).strip()
    
    # Clear the output box
    text_output.delete("1.0", tk.END)
    # Clear grid view if exists
    try:
        result_tree.delete(*result_tree.get_children())
    except:
        pass  # Tree might not exist yet
    
    if not sql_block:
        text_output.insert(tk.END, "Please enter some SQL commands first.")
        return
    
    # Auto-semicolon feature: Add semicolon if missing at end of block
    if sql_block and not sql_block.endswith(';'):
        sql_block += ';'
    
    start_time = time.time()
    
    try:
        # Split the block by ';' to handle multiple commands at once
        statements = [s.strip() for s in sql_block.split(';') if s.strip()]
        
        # Store results for potential CSV export
        global last_select_results
        last_select_results = []
        
        for stmt in statements:
            # Handle autocommit mode
            if not autocommit_mode.get() and not stmt.upper().startswith(('BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT')):
                # In manual mode, we don't auto-commit DML/DDL unless in a transaction
                pass
            
            # Feature 5: Parameterized Queries Support
            raw_params = param_input.get().strip()
            if raw_params and "?" in stmt:
                # Convert comma-separated string to tuple
                param_tuple = tuple(p.strip() for p in raw_params.split(","))
                cursor.execute(stmt, param_tuple)
            else:
                cursor.execute(stmt)
            
            # Log to history if it's a meaningful query
            if stmt.strip() and not stmt.upper().startswith(('COMMIT', 'ROLLBACK', 'BEGIN', 'SAVEPOINT')):
                add_to_history(stmt)
            
            # If it's a SELECT statement, fetch and display the results
            if stmt.upper().startswith("SELECT"):
                rows = cursor.fetchall()
                last_select_results = rows  # Store for CSV export
                
                if not rows:
                    text_output.insert(tk.END, "  -> (No results found)\n")
                else:
                    # Get column names
                    column_names = [description[0] for description in cursor.description]
                    
                    # Feature 2: Grid View Implementation
                    # Configure treeview with columns
                    result_tree["columns"] = column_names
                    result_tree["show"] = "headings"
                    
                    # Configure column headings
                    for col in column_names:
                        result_tree.heading(col, text=col)
                        result_tree.column(col, width=100)
                    
                    # Insert data rows
                    for row in rows:
                        result_tree.insert("", tk.END, values=row)
                    
                    # Switch to grid view for SELECT results
                    text_output.pack_forget()  # Hide text output
                    result_tree.pack(fill=tk.BOTH, expand=True)  # Show grid view
            else:
                # For non-SELECT statements, show text output
                result_tree.pack_forget()  # Hide grid view
                text_output.pack(fill=tk.BOTH, expand=True)  # Show text output
                text_output.insert(tk.END, f"Executed: {stmt[:50]}{'...' if len(stmt) > 50 else ''}\n")
        
        # Commit if in autocommit mode
        if autocommit_mode.get():
            conn.commit()
            text_output.insert(tk.END, "\n✅ Block executed successfully and committed.\n")
        else:
            text_output.insert(tk.END, "\n✅ Block executed successfully. (Manual mode - remember to commit)\n")
        
        # Update execution time
        end_time = time.time()
        execution_time_ms = int((end_time - start_time) * 1000)
        time_label.config(text=f"Last query: {execution_time_ms} ms")
        
    except Exception as e:
        # Rollback if in autocommit mode and error occurs
        if autocommit_mode.get():
            conn.rollback()
            text_output.insert(tk.END, f"\n❌ ERROR: {e}\n(Rolled back due to autocommit mode)")
        else:
            text_output.insert(tk.END, f"\n❌ ERROR: {e}")
        
        # Feature 6: Error Highlighting
        text_input.tag_add("error_bg", "1.0", tk.END)
        
        # Show text output for errors
        result_tree.pack_forget()  # Hide grid view
        text_output.pack(fill=tk.BOTH, expand=True)  # Show text output

def add_to_history(query):
    """Add query to history, maintaining last 10 unique queries."""
    global query_history
    # Avoid duplicates
    if query in query_history:
        query_history.remove(query)
    # Add to front
    query_history.insert(0, query)
    # Keep only last 10
    if len(query_history) > 10:
        query_history = query_history[:10]
    # Update history display
    update_history_display()

def update_history_display():
    """Update the history listbox with current history."""
    history_listbox.delete(0, tk.END)
    for query in query_history:
        # Show truncated query in listbox
        display_query = query[:50] + ('...' if len(query) > 50 else '')
        history_listbox.insert(tk.END, display_query)

def load_query_from_history(event):
    """Load selected query from history into input box."""
    selection = history_listbox.curselection()
    if selection:
        index = selection[0]
        query = query_history[index]
        text_input.delete("1.0", tk.END)
        text_input.insert(tk.END, query)

def view_schema():
    """Fetches and displays the table structures and their columns."""
    text_output.delete("1.0", tk.END)
    text_output.insert(tk.END, "--- DATABASE SCHEMA ---\n\n")
    
    try:
        # Query SQLite's internal master table to find all created tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            text_output.insert(tk.END, "Your database is empty. Create a table first!")
            return
        
        for table in tables:
            table_name = table[0]
            # Ignore SQLite's internal sequence table
            if table_name == "sqlite_sequence": 
                continue
                
            text_output.insert(tk.END, f"📦 TABLE: {table_name}\n")
            
            # PRAGMA table_info returns the column structures for a specific table
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            for col in columns:
                # col format: (cid, name, type, notnull, default_value, primary_key)
                col_name = col[1]
                col_type = col[2]
                text_output.insert(tk.END, f"   - {col_name} ({col_type})\n")
            text_output.insert(tk.END, "\n")
            
    except Exception as e:
        text_output.insert(tk.END, f"❌ ERROR: {e}")

def export_to_csv():
    """Export last SELECT results to CSV file."""
    if not last_select_results:
        messagebox.showwarning("Export Warning", "No SELECT query results to export. Run a SELECT query first.")
        return
    
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        title="Save query results as CSV"
    )
    
    if not file_path:
        return  # User cancelled
    
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Write header if we have column names from last query
            # We need to get column names from the last executed SELECT
            # For simplicity, we'll just write the data
            for row in last_select_results:
                writer.writerow(row)
        
        messagebox.showinfo("Export Success", f"Results exported successfully to:\n{file_path}")
    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export CSV:\n{e}")

def load_sql_file():
    """Load SQL from a file into the input box."""
    file_path = filedialog.askopenfilename(
        filetypes=[("SQL files", "*.sql"), ("All files", "*.*")],
        title="Open SQL file"
    )
    
    if not file_path:
        return  # User cancelled
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        text_input.delete("1.0", tk.END)
        text_input.insert(tk.END, content)
        
        # Update status
        status_label.config(text=f"Loaded: {file_path.split('/')[-1]}")
    except Exception as e:
        messagebox.showerror("Load Error", f"Failed to load SQL file:\n{e}")

def clear_output():
    """Clear the output box."""
    text_output.delete("1.0", tk.END)

def toggle_autocommit():
    """Toggle autocommit mode and update button states."""
    if autocommit_mode.get():
        commit_button.config(state="disabled")
        rollback_button.config(state="disabled")
        status_label.config(text="Autocommit: ON")
    else:
        commit_button.config(state="normal")
        rollback_button.config(state="normal")
        status_label.config(text="Autocommit: OFF (Manual)")

def commit_transaction():
    """Manually commit transaction."""
    try:
        conn.commit()
        messagebox.showinfo("Transaction", "Transaction committed successfully.")
        status_label.config(text="Last action: Committed")
    except Exception as e:
        messagebox.showerror("Transaction Error", f"Failed to commit:\n{e}")

def rollback_transaction():
    """Manually rollback transaction."""
    try:
        conn.rollback()
        messagebox.showinfo("Transaction", "Transaction rolled back successfully.")
        status_label.config(text="Last action: Rolled back")
    except Exception as e:
        messagebox.showerror("Transaction Error", f"Failed to rollback:\n{e}")

def explain_query():
    """Provide plain English explanation of SQL query."""
    query = text_input.get("1.0", tk.END).strip()
    if not query:
        messagebox.showinfo("Explain Mode", "Please enter a SQL query to explain.")
        return
    
    # Clean up the query for explanation
    query_upper = query.upper().strip()
    
    # Start building explanation
    explanation = "This query "
    
    # Handle different SQL command types
    if query_upper.startswith("SELECT"):
        explanation += "retrieves data"
        
        # Extract SELECT clause
        select_part = query_upper.split("FROM")[0].replace("SELECT", "", 1).strip()
        if select_part == "*":
            explanation += " all columns"
        elif "DISTINCT" in select_part:
            explanation += " distinct values"
            # Remove DISTINCT for further processing
            select_part = select_part.replace("DISTINCT", "", 1).strip()
        else:
            explanation += " the specified columns"
        
        # Check for aggregates
        agg_functions = ["COUNT(", "SUM(", "AVG(", "MIN(", "MAX("]
        has_agg = any(agg in select_part for agg in agg_functions)
        if has_agg:
            explanation += " with aggregate calculations"
        
        # FROM clause
        if "FROM" in query_upper:
            from_part = query_upper.split("FROM")[1]
            # Get the table part before any WHERE, GROUP BY, etc.
            for clause in [" WHERE", " GROUP BY", " HAVING", " ORDER BY", " LIMIT"]:
                if clause in from_part:
                    from_part = from_part.split(clause)[0]
            tables = [t.strip() for t in from_part.split(",")]
            if len(tables) == 1:
                explanation += f" from the '{tables[0]}' table"
            else:
                table_names = [f"'{t}'" for t in tables]
                explanation += f" from the tables: {', '.join(table_names)}"
                
                # Check for JOINs
                join_types = [" INNER JOIN", " LEFT JOIN", " RIGHT JOIN", " FULL JOIN", " JOIN"]
                if any(jt in query_upper for jt in join_types):
                    explanation += " using JOIN operations to combine related data"
        
        # WHERE clause
        if " WHERE " in query_upper:
            explanation += ", filtering rows based on specified conditions"
        
        # GROUP BY clause
        if " GROUP BY " in query_upper:
            explanation += ", grouping results"
        
        # HAVING clause
        if " HAVING " in query_upper:
            explanation += ", filtering groups based on conditions"
        
        # ORDER BY clause
        if " ORDER BY " in query_upper:
            explanation += ", sorting the results"
        
        # LIMIT clause
        if " LIMIT " in query_upper:
            explanation += ", limiting the number of returned rows"
        
        explanation += "."
    
    elif query_upper.startswith("INSERT"):
        explanation += "inserts new data"
        
        # Find table name
        into_index = query_upper.find("INTO")
        if into_index != -1:
            after_into = query_upper[into_index + 4:].strip()
            # Get table name (first word before parentheses or whitespace)
            table_part = after_into.split()[0] if after_into.split() else ""
            # Clean table name (remove parentheses if present)
            table_part = table_part.strip("()")
            if table_part:
                explanation += f" into the '{table_part}' table"
        
        # Check if it's INSERT ... VALUES or INSERT ... SELECT
        if "VALUES" in query_upper:
            explanation += ", adding new row(s) with specified values"
        elif "SELECT" in query_upper:
            explanation += ", copying data from another query"
        
        explanation += "."
    
    elif query_upper.startswith("UPDATE"):
        explanation += "modifies existing data"
        
        # Find table name
        update_index = query_upper.find("UPDATE")
        if update_index != -1:
            after_update = query_upper[update_index + 6:].strip()
            table_part = after_update.split()[0] if after_update.split() else ""
            table_part = table_part.strip("()")
            if table_part:
                explanation += f" in the '{table_part}' table"
        
        # SET clause
        if " SET " in query_upper:
            explanation += ", updating specific columns"
        
        # WHERE clause
        if " WHERE " in query_upper:
            explanation += ", but only for rows matching certain conditions"
        else:
            explanation += " ⚠️ WARNING: No WHERE condition - this will update ALL rows in the table!"
        
        explanation += "."
    
    elif query_upper.startswith("DELETE"):
        explanation += "removes data"
        
        # Find table name
        from_index = query_upper.find("FROM")
        if from_index != -1:
            after_from = query_upper[from_index + 4:].strip()
            table_part = after_from.split()[0] if after_from.split() else ""
            table_part = table_part.strip("()")
            if table_part:
                explanation += f" from the '{table_part}' table"
        
        # WHERE clause
        if " WHERE " in query_upper:
            explanation += ", deleting only rows that match specific conditions"
        else:
            explanation += " ⚠️ WARNING: No WHERE condition - this will delete ALL rows in the table!"
        
        explanation += "."
    
    elif query_upper.startswith("CREATE"):
        explanation += "creates a new database object"
        
        if "TABLE" in query_upper:
            explanation += " (specifically a new table)"
        elif "INDEX" in query_upper:
            explanation += " (specifically a new index to improve query performance)"
        elif "VIEW" in query_upper:
            explanation += " (specifically a new virtual table based on a query)"
        
        explanation += "."
    
    elif query_upper.startswith("DROP"):
        explanation += "deletes a database object"
        
        if "TABLE" in query_upper:
            explanation += " (specifically a table and all its data)"
        elif "INDEX" in query_upper:
            explanation += " (specifically an index)"
        elif "VIEW" in query_upper:
            explanation += " (specifically a view)"
        
        explanation += " ⚠️ WARNING: This operation cannot be undone!"
    
    elif query_upper.startswith("ALTER"):
        explanation += "modifies an existing database object"
        
        if "ADD" in query_upper:
            explanation += ", adding a new column or constraint"
        elif "DROP" in query_upper:
            explanation += ", removing a column or constraint"
        elif "MODIFY" in query_upper:
            explanation += ", changing a column's definition"
        
        explanation += "."
    
    else:
        explanation = f"This query executes the command: {query[:100]}{'...' if len(query) > 100 else ''}"
    
    messagebox.showinfo("Query Explanation", explanation)

# ---------------------------------------------------------
# NEW FEATURES: MOCKING ENGINES & UTILS
# ---------------------------------------------------------
class MockPyMySQL:
    def connect(self, **kwargs):
        return conn

def execute_nosql_mock(code):
    text_output.delete("1.0", tk.END)
    text_output.insert(tk.END, "--- NoSQL Mock Execution ---\n")
    try:
        lines = code.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            find_match = re.match(r'db\.(\w+)\.find\((.*)\)', line)
            if find_match:
                table = find_match.group(1)
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                cols = [description[0] for description in cursor.description]
                for r in rows:
                    doc = dict(zip(cols, r))
                    text_output.insert(tk.END, json.dumps(doc, indent=2) + "\n")
                continue
            insert_match = re.match(r'db\.(\w+)\.insertOne\((.*)\)', line)
            if insert_match:
                table = insert_match.group(1)
                data = json.loads(insert_match.group(2))
                cols = ', '.join(data.keys())
                placeholders = ', '.join(['?'] * len(data))
                vals = tuple(data.values())
                cursor.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", vals)
                conn.commit()
                text_output.insert(tk.END, f"Inserted document into {table}.\n")
                continue
            text_output.insert(tk.END, f"Command not recognized by mock engine: {line}\n")
    except Exception as e:
        text_output.insert(tk.END, f"❌ NoSQL Mock Error: {e}")

def execute_python_mock(code):
    text_output.delete("1.0", tk.END)
    text_output.insert(tk.END, "--- Python PyMySQL Mock Execution ---\n")
    def mock_print(*args):
        text_output.insert(tk.END, " ".join(str(a) for a in args) + "\n")
    local_env = {'pymysql': MockPyMySQL(), 'print': mock_print}
    try:
        clean_code = code.replace("import pymysql", "")
        exec(clean_code, {}, local_env)
        text_output.insert(tk.END, "\n✅ Python Script Completed.")
    except Exception as e:
        text_output.insert(tk.END, f"\n❌ Python Error: {e}")

def nuke_database():
    if messagebox.askyesno("NUKE DATABASE", "Are you sure? This will permanently delete ALL tables and data!"):
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            for table in tables:
                if table[0] != "sqlite_sequence":
                    cursor.execute(f"DROP TABLE {table[0]};")
            conn.commit()
            text_output.delete("1.0", tk.END)
            text_output.insert(tk.END, "💥 DATABASE NUKED. All tables dropped.\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to nuke: {e}")

def generate_code_from_tables():
    text_output.delete("1.0", tk.END)
    text_output.insert(tk.END, "--- GENERATED SQL CODE ---\n\n")
    try:
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for t in tables:
            table_name = t[0]
            if table_name == "sqlite_sequence":
                continue
            text_output.insert(tk.END, f"{t[1]};\n")
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            if rows:
                cursor.execute(f"PRAGMA table_info({table_name});")
                cols = [c[1] for c in cursor.fetchall()]
                for r in rows:
                    vals = [f"'{str(v)}'" if isinstance(v, str) else str(v) for v in r]
                    insert_stmt = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({', '.join(vals)});"
                    text_output.insert(tk.END, f"{insert_stmt}\n")
            text_output.insert(tk.END, "\n")
    except Exception as e:
        text_output.insert(tk.END, f"❌ ERROR: {e}")

# Feature 3: Database Tree-View helper functions
def refresh_db_tree():
    """Refresh the database tree view to show current tables."""
    db_tree.delete(*db_tree.get_children())
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    for table in cursor.fetchall():
        if table[0] != "sqlite_sequence":
            db_tree.insert("", "end", text=table[0])

def on_table_double_click(event):
    """Handle double-click on a table in the tree view."""
    selected_item = db_tree.selection()
    if selected_item:
        table_name = db_tree.item(selected_item[0], "text")
        text_input.delete("1.0", tk.END)
        text_input.insert(tk.END, f"SELECT * FROM {table_name};")
        route_execution()

# Feature 1: Multiple DB Support
def switch_database(event=None):
    global conn, cursor, current_db_file
    new_db = db_combo.get()
    if new_db:
        conn.close()
        current_db_file = new_db
        conn = sqlite3.connect(current_db_file, check_same_thread=False)
        cursor = conn.cursor()
        text_output.delete("1.0", tk.END)
        text_output.insert(tk.END, f"\nSwitched to database: {new_db}\n")
        refresh_db_tree()  # Refresh the database tree view

def create_new_database():
    """Create a new database file and switch to it."""
    global conn, cursor, current_db_file
    new_db_name = simpledialog.askstring("New Database", "Enter new database name (e.g., mydb.db):")
    if new_db_name:
        if not new_db_name.endswith('.db'):
            new_db_name += '.db'
        
        # Close current connection
        conn.close()
        
        # Create new database
        current_db_file = new_db_name
        conn = sqlite3.connect(current_db_file, check_same_thread=False)
        cursor = conn.cursor()
        
        # Update UI
        available_dbs = [f for f in os.listdir('.') if f.endswith('.db')]
        if new_db_name not in available_dbs:
            available_dbs.append(new_db_name)
        db_combo['values'] = available_dbs
        db_combo.set(new_db_name)
        
        text_output.delete("1.0", tk.END)
        text_output.insert(tk.END, f"\nCreated and switched to new database: {new_db_name}\n")
        refresh_db_tree()

# Feature 6: Error Highlighting Enhancement
def highlight_error_line():
    """Highlight the line where error occurred in text_input"""
    # Remove previous error highlights
    text_input.tag_remove("error_line", "1.0", tk.END)
    # In a real implementation, we would parse the error to find the line
    # For simplicity, we'll highlight the entire input for now
    # A more advanced implementation would parse SQLite error messages
    text_input.tag_add("error_line", "1.0", tk.END)

def route_execution():
    mode = mode_var.get()
    raw_code = text_input.get("1.0", tk.END).strip()
    text_output.delete("1.0", tk.END)
    if not raw_code:
        text_output.insert(tk.END, "Please enter commands first.")
        return
    start_time = time.time()
    if mode == MODE_SQL:
        execute_sql_block()
    elif mode == MODE_NOSQL:
        execute_nosql_mock(raw_code)
    elif mode == MODE_PYMYSQL:
        execute_python_mock(raw_code)
    execution_time_ms = int((time.time() - start_time) * 1000)
    time_label.config(text=f"Last run: {execution_time_ms} ms")

# ---------------------------------------------------------
# GUI SETUP (Tkinter)
# ---------------------------------------------------------
root = tk.Tk()
root.title("SQL Study Environment - Enhanced")
root.geometry("1000x600")
root.configure(padx=5, pady=5)

# --- GLOBAL DARK MODE CONFIG ---
dark_mode_state = False

# Fix for the hidden Combobox dropdown lists (Must be set before widgets are created)
root.option_add('*TCombobox*Listbox.background', '#1e1e1e')
root.option_add('*TCombobox*Listbox.foreground', '#a9b7c6')
root.option_add('*TCombobox*Listbox.selectBackground', '#2a4d69')
root.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')

# Global variables for tracking state (moved here to avoid Tk init error)
autocommit_mode = tk.BooleanVar(value=True)  # Track autocommit state

# Create main paned window for resizable sections
main_paned = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
main_paned.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

# Left sidebar for history and other panels
left_frame = ttk.Frame(main_paned, width=200)
main_paned.add(left_frame, weight=1)

# Right side for main interface
right_frame = ttk.Frame(main_paned)
main_paned.add(right_frame, weight=3)

# Feature 4: Cheat Sheet Sidebar (Rightmost pane)
rightmost_frame = ttk.Frame(main_paned, width=200)
main_paned.add(rightmost_frame, weight=1)

tk.Label(rightmost_frame, text="Cheat Sheet", font=("Arial", 10, "bold")).pack(anchor="w")
cheat_sheet = tk.Text(rightmost_frame, width=25, font=("Courier", 9), bg="#e9ecef")
cheat_sheet.pack(fill=tk.BOTH, expand=True, pady=(5,0))

cheat_texts = """-- CREATE
CREATE TABLE t (id INT);

-- INSERT
INSERT INTO t (c) 
VALUES (v);

-- UPDATE
UPDATE t SET c=v 
WHERE x;

-- DELETE
DELETE FROM t 
WHERE x;"""

cheat_sheet.insert(tk.END, cheat_texts)
cheat_sheet.config(state="disabled") # Make it read-only

# === LEFT SIDEBAR: Query History ===
tk.Label(left_frame, text="Query History", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0,5))
history_listbox = tk.Listbox(left_frame, height=10, width=25, font=("Courier", 9))
history_listbox.pack(fill=tk.BOTH, expand=True, pady=(0,5))
history_listbox.bind("<<ListboxSelect>>", load_query_from_history)

# Feature 3: Database Tree-View
tk.Label(left_frame, text="Tables (Click to SELECT)", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10,0))
db_tree = ttk.Treeview(left_frame, show="tree", height=10)
db_tree.pack(fill=tk.BOTH, expand=True, pady=(0,5))
db_tree.bind("<Double-1>", on_table_double_click)

# Add some sample history initially
query_history = ["SELECT * FROM students;", "CREATE TABLE test (id INTEGER);"]
update_history_display()

# Initialize database tree view
refresh_db_tree()

# === RIGHT FRAME: Main Interface ===
# Input Area with Line Numbers (Feature 7)
tk.Label(right_frame, text="Enter SQL Commands (separate multiple commands with ';'):", font=("Arial", 10, "bold")).pack(anchor="w")

# Create frame for line numbers and text input
input_container = tk.Frame(right_frame)
input_container.pack(pady=5, fill=tk.X)

# Line numbers widget
line_numbers = tk.Text(input_container, width=3, height=8, bg="#e0e0e0", font=("Courier", 10), state="disabled")
line_numbers.pack(side=tk.LEFT, fill=tk.Y)

# Text input widget with autocomplete
text_input = SyntaxHighlightingText(input_container, height=8, width=80, font=("Courier", 10))
text_input.pack(side=tk.LEFT, fill=tk.X, expand=True)

# Line numbers update function
def update_line_numbers(event=None):
    lines = text_input.get("1.0", "end-1c").count('\n') + 1
    line_numbers.config(state="normal")
    line_numbers.delete("1.0", tk.END)
    line_numbers.insert("1.0", "\n".join(str(i) for i in range(1, lines + 1)))
    line_numbers.config(state="disabled")

text_input.bind("<KeyRelease>", update_line_numbers)
text_input.bind("<MouseWheel>", update_line_numbers)

# Buttons Area
button_frame = tk.Frame(right_frame)
button_frame.pack(pady=8, fill=tk.X)

# Primary buttons
btn_execute = tk.Button(button_frame, text="▶ Execute Block", bg="#d4edda", font=("Arial", 10, "bold"), command=execute_sql_block)
btn_execute.pack(side=tk.LEFT, padx=2)

btn_schema = tk.Button(button_frame, text="📋 View Schema", bg="#cce5ff", font=("Arial", 10, "bold"), command=view_schema)
btn_schema.pack(side=tk.LEFT, padx=2)

btn_export = tk.Button(button_frame, text="💾 Export CSV", bg="#fff3cd", font=("Arial", 10, "bold"), command=export_to_csv)
btn_export.pack(side=tk.LEFT, padx=2)

btn_load = tk.Button(button_frame, text="📂 Load .sql", bg="#e2e3e5", font=("Arial", 10, "bold"), command=load_sql_file)
btn_load.pack(side=tk.LEFT, padx=2)

# Transaction controls
tk.Label(button_frame, text="Transaction:").pack(side=tk.LEFT, padx=(10,2))
autocommit_check = tk.Checkbutton(button_frame, text="Autocommit", variable=autocommit_mode, command=toggle_autocommit)
autocommit_check.pack(side=tk.LEFT, padx=2)

commit_button = tk.Button(button_frame, text="✓ Commit", bg="#d4edda", font=("Arial", 9), command=commit_transaction, state="disabled")
commit_button.pack(side=tk.LEFT, padx=2)

rollback_button = tk.Button(button_frame, text="↺ Rollback", bg="#f8d7da", font=("Arial", 9), command=rollback_transaction, state="disabled")
rollback_button.pack(side=tk.LEFT, padx=2)

# Secondary buttons
button_frame2 = tk.Frame(right_frame)
button_frame2.pack(pady=2, fill=tk.X)

btn_clear = tk.Button(button_frame2, text="🗑 Clear Output", bg="#e2e3e5", font=("Arial", 9), command=clear_output)
btn_clear.pack(side=tk.LEFT, padx=2)

btn_explain = tk.Button(button_frame2, text="❓ Explain", bg="#d1ecf1", font=("Arial", 9), command=explain_query)
btn_explain.pack(side=tk.LEFT, padx=2)

# Mode selector
mode_var = tk.StringVar(value=MODE_SQL)
tk.Label(button_frame2, text="Mode:").pack(side=tk.LEFT, padx=(10,2))
mode_menu = tk.OptionMenu(button_frame2, mode_var, MODE_SQL, MODE_NOSQL, MODE_PYMYSQL)
mode_menu.config(font=("Arial", 9))
mode_menu.pack(side=tk.LEFT, padx=2)

# Feature 1: Multiple DB Support - UI
tk.Label(button_frame2, text=" | DB:").pack(side=tk.LEFT, padx=(10,2))
available_dbs = [f for f in os.listdir('.') if f.endswith('.db')]
if "study_database.db" not in available_dbs:
    available_dbs.append("study_database.db")
db_combo = ttk.Combobox(button_frame2, values=available_dbs, state="readonly", width=12)
db_combo.set(current_db_file)
db_combo.pack(side=tk.LEFT, padx=2)
db_combo.bind("<<ComboboxSelected>>", switch_database)

# Button to create a new database
btn_new_db = tk.Button(button_frame2, text="+ New DB", bg="#d4edda", font=("Arial", 9), command=create_new_database)
btn_new_db.pack(side=tk.LEFT, padx=2)

# Danger zone buttons
button_frame3 = tk.Frame(right_frame)
button_frame3.pack(pady=2, fill=tk.X)

btn_nuke = tk.Button(button_frame3, text="💣 NUKE DB", bg="#ffcccc", font=("Arial", 9, "bold"), command=nuke_database)
btn_nuke.pack(side=tk.LEFT, padx=2)

btn_generate = tk.Button(button_frame3, text="↩ Generate SQL Code", bg="#ffe0b3", font=("Arial", 9), command=generate_code_from_tables)
btn_generate.pack(side=tk.LEFT, padx=2)

# Feature 5: Parameterized Queries UI
tk.Label(button_frame3, text="Params:").pack(side=tk.LEFT, padx=(10,2))
param_input = tk.Entry(button_frame3, width=15)
param_input.pack(side=tk.LEFT, padx=2)

# Output Area - with Grid View option
output_label = tk.Label(right_frame, text="Output / Results:", font=("Arial", 10, "bold"))
output_label.pack(anchor="w", pady=(10,0))

# Create a frame for output widgets
output_frame = tk.Frame(right_frame)
output_frame.pack(pady=5, fill=tk.BOTH, expand=True)

# Text output (original)
text_output = tk.Text(output_frame, height=12, width=80, font=("Courier", 10), bg="#f8f9fa")

# Grid view (Treeview) - initially hidden
result_tree = ttk.Treeview(output_frame, show="headings", height=6)
# We'll manage visibility with pack/unpack

# Start with text output visible
text_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Status bar
status_frame = tk.Frame(right_frame)
status_frame.pack(fill=tk.X, pady=(5,0))

time_label = tk.Label(status_frame, text="Last query: -- ms", font=("Arial", 9))
time_label.pack(side=tk.LEFT)

status_label = tk.Label(status_frame, text="Autocommit: ON", font=("Arial", 9), fg="green")
status_label.pack(side=tk.LEFT, padx=(20,0))

# Row count tracker (placeholder for future enhancement)
row_count_label = tk.Label(status_frame, text="Rows: --", font=("Arial", 9))
row_count_label.pack(side=tk.RIGHT, padx=(0,10))

def toggle_dark_mode():
    global dark_mode_state
    dark_mode_state = not dark_mode_state
    
    # --- Define Color Palettes ---
    bg_main = "#2b2b2b" if dark_mode_state else "#f0f0f0"
    bg_text = "#1e1e1e" if dark_mode_state else "#ffffff"
    fg_main = "#a9b7c6" if dark_mode_state else "#000000"
    fg_heading = "#ffffff" if dark_mode_state else "#000000"
    btn_bg = "#3c3f41" if dark_mode_state else "#e2e3e5"
    btn_fg = "#ffffff" if dark_mode_state else "#000000"
    select_bg = "#2a4d69" if dark_mode_state else "#0078d7"
    
    root.configure(bg=bg_main)
    
    # 1. Update TTK Widgets (PanedWindow, Treeview, Combobox)
    style = ttk.Style()
    style.theme_use('clam') 
    
    style.configure(".", background=bg_main, foreground=fg_main)
    style.configure("TFrame", background=bg_main)
    style.configure("TPanedwindow", background=bg_main)
    
    # Treeview (Tables)
    style.configure("Treeview", background=bg_text, foreground=fg_main, fieldbackground=bg_text, borderwidth=0)
    style.configure("Treeview.Heading", background=bg_main, foreground=fg_heading, relief="flat")
    style.map("Treeview", background=[('selected', select_bg)])
    
    # Comboboxes (Mode and DB Dropdowns) - Includes fix for the 3D border
    style.configure("TCombobox", fieldbackground=bg_text, background=bg_main, foreground=fg_main, 
                    arrowcolor=fg_main, bordercolor=bg_main, lightcolor=bg_main, darkcolor=bg_main)
    style.map("TCombobox", 
              fieldbackground=[('readonly', bg_text)], 
              selectbackground=[('readonly', select_bg)], 
              selectforeground=[('readonly', fg_main)],
              background=[('readonly', bg_main)])

    # Raw Tcl injection to force-update combobox dropdowns that are already cached in memory
    def force_update_popdowns(widget):
        if widget.winfo_class() == 'TCombobox':
            try:
                popdown = root.tk.eval(f'ttk::combobox::PopdownWindow {widget}')
                root.tk.eval(f'{popdown}.f.l configure -background "{bg_text}" -foreground "{fg_main}" -selectbackground "{select_bg}" -selectforeground "#ffffff"')
            except tk.TclError:
                pass 
        for child in widget.winfo_children():
            force_update_popdowns(child)
            
    force_update_popdowns(root)

    # 2. Recursively update all standard Tkinter widgets
    def apply_theme(widget):
        try:
            widget_class = widget.winfo_class()
            
            if widget_class in ('Frame', 'LabelFrame', 'PanedWindow'):
                widget.configure(bg=bg_main)
            elif widget_class == 'Label':
                widget.configure(bg=bg_main, fg=fg_heading)
            elif widget_class in ('Text', 'Entry', 'Listbox'):
                widget.configure(bg=bg_text, fg=fg_main, insertbackground=fg_heading, selectbackground=select_bg)
            elif widget_class == 'Checkbutton':
                widget.configure(bg=bg_main, fg=fg_heading, selectcolor=bg_text, activebackground=bg_main, activeforeground=fg_heading)
            elif widget_class == 'Button':
                widget.configure(bg=btn_bg, fg=btn_fg, activebackground="#4b4e51" if dark_mode_state else "#d4d5d7", activeforeground=btn_fg)
        except tk.TclError:
            pass 
        
        for child in widget.winfo_children():
            apply_theme(child)
            
    apply_theme(root)
    
    # 3. Explicit fixes for widgets that might dodge the recursive loop
    try:
        history_listbox.configure(bg=bg_text, fg=fg_main, selectbackground=select_bg)
    except NameError: pass
    
    try:
        line_numbers.configure(bg="#313335" if dark_mode_state else "#e0e0e0", fg="#606366" if dark_mode_state else "#000000")
    except NameError: pass

btn_dark_mode = tk.Button(status_frame, text="🌙 Toggle Theme", command=toggle_dark_mode)
btn_dark_mode.pack(side=tk.RIGHT, padx=10)

# Start the application
print("Starting application...")
root.mainloop()

# Close connection when the window is closed
conn.close()
