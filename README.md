# SQL Study Environment - Enhanced Python Database Interpreter

A comprehensive, feature-rich SQL study tool built with a Python backend and a modern HTML/CSS/JS frontend for learning database concepts, practicing SQL queries, and understanding database systems.

![Python Version](https://img.shields.io/badge/Python-3.13-blue)
![Frontend](https://img.shields.io/badge/Frontend-HTML%2FCSS%2FJS-green)
![SQLite](https://img.shields.io/badge/Database-SQLite-orange)

## 📚 Overview

This is an enhanced version of a basic SQL interpreter that includes 20+ learning-focused features designed to help students study for database exams, practice SQL queries, and understand database concepts through interactive exploration.

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- A modern browser (Chrome, Safari, Firefox, Edge)
- No additional packages required!

### Installation & Running

```bash
# Navigate to the project directory
cd db_interpreter

# Run the web application
python python-db-interpreter.py

# Or with python3
python3 python-db-interpreter.py
```

Then open `http://127.0.0.1:8000` in your browser.

## ✨ Core Features

### 🛠️ Functionality Upgrades

#### 1. NoSQL Toggle Mode
Switch between SQL, NoSQL, and PyMySQL execution modes.

**Usage:**
1. Select mode from dropdown: `SQL`, `NoSQL`, or `PyMySQL`
2. Type your code in the input area
3. Press Execute

**Example NoSQL Commands:**
```javascript
db.users.find()
db.products.insertOne({"name": "Laptop", "price": 999})
```

**Example PyMySQL Commands:**
```python
import pymysql
conn = pymysql.connect(host='localhost')
cursor = conn.cursor()
cursor.execute("SELECT * FROM users")
```

---

#### 2. Syntax Highlighting
Color-codes SQL keywords as you type for better readability and memorization.

- **Blue** - SQL keywords (SELECT, FROM, WHERE, etc.)
- **Red** - Operators (=, >, <, !=, etc.)
- **Green** - String values ('quotes')

---

#### 3. Export to CSV
Save SELECT query results to a CSV file.

**Usage:**
1. Run a SELECT query
2. Click `💾 Export CSV` button
3. Choose save location and filename

---

#### 4. Transaction Rollback
Practice database transaction concepts with Commit/Rollback controls.

**Usage:**
1. Uncheck `Autocommit` checkbox
2. Execute your queries
3. Click `✓ Commit` to save or `↺ Rollback` to undo

**Learning Point:** Without autocommit, you can test how errors affect data before committing.

---

#### 5. Query History
Automatically saves your last 10 executed queries.

**Usage:**
1. Click any query in the History sidebar
2. Query loads into the input area
3. Edit and re-execute as needed

---

#### 6. Load .sql Files
Open and run SQL script files from your teacher.

**Usage:**
1. Click `📂 Load .sql` button
2. Navigate to your .sql file
3. File content loads into input area
4. Click Execute to run

---

#### 7. Auto-Semicolon
Automatically appends `;` if you forget it, preventing execution errors.

**Example:** Type `SELECT * FROM users` (without semicolon) and it auto-completes.

---

### 📊 Visualization & UI

#### 8. Grid View (Table Display)
Shows query results in an Excel-like table format.

**Features:**
- Sortable columns
- Row-based display
- Easy to read large result sets

**Usage:** SELECT queries automatically display in grid view.

---

#### 9. Database Tree-View
Sidebar showing all tables in your database.

**Features:**
- Lists all tables automatically
- Double-click to auto-generate `SELECT * FROM table`
- Quick table exploration

**Usage:**
1. View tables in left sidebar
2. Double-click any table name
3. Query executes automatically

---

#### 10. Theme Presets
Switch between visual styles depending on your preference.

**Usage:**
1. Use the `Theme` dropdown in the top bar
2. Select one of:
   - `Modern Light`
   - `Modern Dark`
   - `Retro 95` (classic square Windows-style look)

---

#### 11. Clear Terminal Button
Quickly wipe the output screen.

**Usage:** Click `🗑 Clear Output` button.

---

#### 12. Line Numbers
Tracks line numbers in the input area.

**Features:**
- Helps locate errors in long queries
- Updates automatically as you type
- Grey background for distinction

---

### 🐍 Python & Backend Logic

#### 13. Simplified Execution Flow
The editor now runs direct SQL statements without a separate parameter input field,
to keep the UI focused and easier to use in class demos.

---

#### 14. Execution Timer
Shows query execution time in milliseconds.

**Display:** Status bar shows "Last query: X ms"

**Learning Point:** Understand how indexing affects query performance.

---

#### 15. Error Highlighting
Highlights problematic input lines on errors.

**Features:**
- Red background on error location
- Helps identify mistake location
- Clear error messages

---

#### 16. Multiple Database Support
Switch between different .db files.

**Usage:**
1. Select database from dropdown
2. Click to switch instantly
3. Create new databases with `+ New DB`

---

#### 17. Row Count Tracker
Shows "Total Rows in Table: X" for verification.

**Display:** Status bar shows "Rows: X"

**Usage:** Verify DELETE/INSERT commands worked correctly.

---

### 🧪 Study-Specific Features

#### 18. Explain Mode
Breaks down SQL into plain English.

**Usage:**
1. Write your SQL query
2. Click `❓ Explain` button
3. Read the plain English explanation

**Example Output:**
```
SELECT * FROM users WHERE age > 20 ORDER BY name;

"This query retrieves all columns from the 'users' table, 
filtering rows based on specified conditions, sorting the results."
```

---

#### 19. Quick SQL Reference
Use the schema viewer and README snippets as your fast reference for common SQL commands.

**Contents:**
- CREATE TABLE syntax
- INSERT syntax
- UPDATE syntax
- DELETE syntax

**Usage:** Reference during coding without switching windows.

---

#### 20. NoSQL-to-SQL Translator
Translates NoSQL-style commands to SQL.

**Example:**
```javascript
db.users.find()
```
Translates to:
```sql
SELECT * FROM users;
```

---

### 🎯 Bonus Features

#### 💣 NUKE Database
One-click reset to delete all tables.

**Usage:**
1. Click `💣 NUKE DB` button
2. Confirm deletion
3. Database is completely reset

**Warning:** This action cannot be undone!

---

#### ↩ Generate SQL Code
Reverse engineer database to CREATE/INSERT statements.

**Usage:**
1. Click `↩ Generate SQL Code` button
2. View generated SQL
3. Copy for backup or recreation

---

#### 📂 Create New Database
Create new .db files directly from the interface.

**Usage:**
1. Click `+ New DB` button
2. Enter database name
3. Click OK to create and switch

---

## ⌨️ Keyboard Shortcuts & Tips

### Autocomplete Feature

The inline autocomplete helps you write SQL faster:

1. **Type Partially:** Type `INSE` and ghost text shows `RT`
2. **Accept:** Press `Tab` to accept the suggestion
3. **Cycle:** Press `Tab` again to see next option
4. **Reject:** Type more letters or press `Backspace`

### Key Bindings

| Key | Action |
|-----|--------|
| `Tab` | Accept autocomplete / Cycle options |
| `Backspace` | Reject autocomplete |
| `Space` | Clear current suggestions |
| `Escape` | Cancel autocomplete |
| `Ctrl+A` | Select all text |
| `Ctrl+C` | Copy selected text |
| `Ctrl+V` | Paste text |

### Autocomplete Keywords

The system recognizes these SQL keywords:

```
SELECT, FROM, WHERE, INSERT, UPDATE, DELETE,
CREATE, TABLE, DROP, ALTER, JOIN, INNER,
LEFT, RIGHT, OUTER, ON, GROUP BY, ORDER BY,
HAVING, UNION, VALUES, SET, INTO, COMMIT,
ROLLBACK, DISTINCT, AS, NOT, NULL, AND,
OR, LIKE, BETWEEN, IN, EXISTS, CASE, WHEN,
THEN, ELSE, END
```

---

## 📖 SQL Examples

### Basic SELECT
```sql
SELECT * FROM students;
```

### SELECT with WHERE
```sql
SELECT name, age FROM students WHERE age > 18;
```

### INSERT
```sql
INSERT INTO students (name, age, grade) VALUES ('Alice', 20, 'A');
```

### UPDATE
```sql
UPDATE students SET grade = 'B' WHERE name = 'Alice';
```

### DELETE
```sql
DELETE FROM students WHERE name = 'Bob';
```

### CREATE TABLE
```sql
CREATE TABLE students (
    id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER,
    grade TEXT
);
```

### JOIN
```sql
SELECT students.name, courses.title 
FROM students 
INNER JOIN courses ON students.course_id = courses.id;
```

### GROUP BY with HAVING
```sql
SELECT grade, COUNT(*) as count 
FROM students 
GROUP BY grade 
HAVING count > 1;
```

### ORDER BY
```sql
SELECT * FROM students ORDER BY age DESC, name ASC;
```

---

## 🔧 Troubleshooting

### Application Won't Start

**Error:** "Address already in use"

**Solution:**
```bash
# Stop the process currently using port 8000,
# or run the app from another terminal session after freeing the port.
```

### Database Locked

**Error:** "Database is locked"

**Solution:** Close other applications using the database and try again.

### Syntax Errors

**Tip:** Use the Explain feature (`❓ Explain`) to understand your query better.

---

## 📁 Project Structure

```
db_interpreter/
├── python-db-interpreter.py          # Entry point script
├── db_interpreter_app/
│   ├── __init__.py                   # Public app exports
│   ├── app.py                        # App runner wrapper
│   ├── web_server.py                 # HTTP API + static file server
│   ├── core/
│   │   ├── __init__.py
│   │   ├── constants.py              # Modes and shared constants
│   │   ├── database_service.py       # SQLite execution and state management
│   │   ├── explainer.py              # SQL-to-English explanation logic
│   │   └── sql_utils.py              # SQL parsing and safety helpers
│   └── web/
│       ├── index.html                # Frontend layout
│       ├── styles.css                # Modern + Retro 95 themes
│       └── app.js                    # Frontend behavior and API calls
├── study_database.db                 # Default SQLite database
├── README.md                         # This documentation
└── [other].db                        # Additional databases you create
```

---

## 🎓 Learning Path

### Beginner
1. Learn basic SELECT queries
2. Practice INSERT, UPDATE, DELETE
3. Use Explain mode to understand syntax
4. Use History/Tables side panels for quick exploration

### Intermediate
1. Learn JOINs with Database Tree-View
2. Practice GROUP BY and HAVING
3. Compare `Modern` and `Retro 95` themes
4. Export results to CSV

### Advanced
1. Practice transaction control (commit/rollback)
2. Test error scenarios
3. Use multiple databases
4. Generate SQL code from existing databases

---

## 🛠️ Development

### Adding New Features

The code is structured for easy modification:

```python
from db_interpreter_app import run_web_app

# Start the backend server + web frontend
run_web_app(host="127.0.0.1", port=8000)
```

### Extending PyMySQL Mock Safety

Edit the `SAFE_PYTHON_BUILTINS` map in `db_interpreter_app/core/constants.py`
if you need to allow additional harmless Python built-ins in mock mode.

---

## 📝 License

This project is open for educational use. Feel free to modify and share!

---

## 🙏 Credits

Built with Python 3.13, SQLite, and a custom HTML/CSS/JS frontend for the Database Systems course.

---

## 📞 Support

For issues or questions:
1. Check the Schema panel output
2. Use Explain mode for query help
3. Review this README

---

**Happy Learning! 🎓**
