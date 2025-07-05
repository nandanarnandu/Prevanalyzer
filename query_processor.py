from flask import (
    Blueprint, render_template, request, flash
)
import sqlite3
import pandas as pd
import html

# Define your blueprint (assuming app factory pattern)
query_bp = Blueprint('query', __name__, template_folder='templates')

# Config flag for Groq AI (set to True if you integrate Groq AI client)
GROQ_ENABLED = False

DATABASE = 'hospital.db'  # change to your actual DB path


def execute_sql_query(query: str):
    """Executes a SQL query on the SQLite DB and returns HTML table or error."""
    try:
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query(query, conn)
        conn.close()
        if df.empty:
            return "<p>No results found.</p>"
        # Convert DataFrame to HTML table with Bootstrap classes
        html_table = df.to_html(classes='table table-striped table-bordered', index=False, border=0)
        return html_table
    except Exception as e:
        # Return a safe error message
        return f"<p><strong>Error:</strong> {html.escape(str(e))}</p>"


def dummy_groq_ai_response(user_query: str):
    """Stub for AI/Groq integration - replace with real API call."""
    # This example just echoes the input query.
    return f"AI response to your query: <em>{html.escape(user_query)}</em>"


@query_bp.route('/query', methods=['GET', 'POST'])
def query_page():
    response = None

    if request.method == 'POST':
        user_query = request.form.get('user_query', '').strip()

        if not user_query:
            flash("Please enter a query.")
        else:
            # Basic keyword checks to decide execution mode
            # You can extend this logic to support more natural language queries
            lower_query = user_query.lower()

            # If Groq AI enabled, use AI for query processing
            if GROQ_ENABLED:
                response = dummy_groq_ai_response(user_query)
            else:
                # Basic handling: For some simple commands, run a SQL query
                # Example commands mapping to SQL
                if "show all employees" in lower_query:
                    sql = "SELECT * FROM employees"
                    response = execute_sql_query(sql)
                elif "find" in lower_query:
                    # Extract a name from query, naive approach
                    name = user_query.split("find", 1)[1].strip()
                    if name:
                        sql = "SELECT * FROM employees WHERE name LIKE ?"
                        try:
                            conn = sqlite3.connect(DATABASE)
                            df = pd.read_sql_query(sql, conn, params=(f'%{name}%',))
                            conn.close()
                            if df.empty:
                                response = f"<p>No employees found matching '{html.escape(name)}'.</p>"
                            else:
                                response = df.to_html(classes='table table-striped table-bordered', index=False, border=0)
                        except Exception as e:
                            response = f"<p><strong>Error:</strong> {html.escape(str(e))}</p>"
                    else:
                        response = "<p>Please specify a name to find.</p>"
                elif "encrypt salary" in lower_query:
                    # Just a demo response, encryption not implemented here
                    response = "<p>Salary encryption is not implemented yet.</p>"
                else:
                    # Fallback: treat the query as SQL but block dangerous commands
                    # Very important: Never run user input SQL in production without sanitation!
                    blocked_keywords = ['delete', 'drop', 'update', 'insert', 'alter']
                    if any(keyword in lower_query for keyword in blocked_keywords):
                        response = "<p>Unsafe queries are not allowed.</p>"
                    else:
                        response = execute_sql_query(user_query)

    return render_template(
        'query_processor.html',  # Your Jinja2 template file name
        response=response,
        groq_enabled=GROQ_ENABLED
    )
