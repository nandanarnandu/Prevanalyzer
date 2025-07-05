from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import pandas as pd
import sqlite3
import hashlib
import base64

app = Flask(__name__)
app.secret_key = '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'

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
DATABASE = 'data.db'
ALLOWED_EXTENSIONS = {'xls', 'xlsx', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_all_data():
    conn = sqlite3.connect(DATABASE)
    try:
        df = pd.read_sql_query("SELECT * FROM data", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df.to_dict(orient='records') if not df.empty else []

def compute_statistics():
    conn = sqlite3.connect(DATABASE)
    try:
        df = pd.read_sql_query("SELECT * FROM data", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()

    if df.empty:
        return {"message": "No data available for analysis"}

    stats = {}
    numeric_cols = df.select_dtypes(include='number').columns
    for col in numeric_cols:
        stats[f"{col} (numeric)"] = {
            'mean': round(df[col].mean(), 2),
            'min': df[col].min(),
            'max': df[col].max(),
            'count': df[col].count()
        }

    non_numeric_cols = df.select_dtypes(exclude='number').columns
    for col in non_numeric_cols:
        stats[f"{col} (text)"] = {
            'unique_values': df[col].nunique(),
            'top_value': df[col].mode().iloc[0] if not df[col].mode().empty else None,
            'total_count': df[col].count()
        }

    return stats

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify(success=False, message='No file part in the request.')

    file = request.files['file']
    if file.filename == '':
        return jsonify(success=False, message='No file selected.')

    if not allowed_file(file.filename):
        return jsonify(success=False, message='Only .xls, .xlsx, or .csv files allowed.')

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # Read file
        if filename.endswith(('xls', 'xlsx')):
            df = pd.read_excel(filepath)
        else:
            df = pd.read_csv(filepath)

        df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]

        # Store in SQLite
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS data;")

        column_defs = ', '.join([f'"{col}" TEXT' for col in df.columns])
        cursor.execute(f'CREATE TABLE data ({column_defs});')

        insert_query = f'INSERT INTO data ({", ".join([f'"{col}"' for col in df.columns])}) VALUES ({", ".join(["?"] * len(df.columns))})'
        for _, row in df.iterrows():
            cursor.execute(insert_query, tuple(str(x) for x in row.tolist()))

        conn.commit()
        conn.close()
        os.remove(filepath)

        # Create insights
        insights = []
        numeric_cols = df.select_dtypes(include='number')
        for col in numeric_cols.columns:
            insights.append(f"For <strong>{col}</strong>: average = {df[col].mean():.2f}, min = {df[col].min()}, max = {df[col].max()}.")

        non_numeric_cols = df.select_dtypes(exclude='number')
        for col in non_numeric_cols.columns:
            mode_val = df[col].mode().iloc[0] if not df[col].mode().empty else "N/A"
            insights.append(f"<strong>{col}</strong> has {df[col].nunique()} unique values. Most common: <em>{mode_val}</em>.")

        return jsonify(success=True, table=df.to_html(index=False, classes='table table-bordered table-striped', border=0), insights=insights)

    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify(success=False, message=f"Error: {str(e)}")

# Fixed route to match JavaScript calls
@app.route('/process/<operation>', methods=['POST'])
def process_operation(operation):
    global confidential_fields
    try:
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query("SELECT * FROM data", conn)
        conn.close()

        if df.empty:
            return jsonify({"error": "No data available. Please upload a file first."})

        # Check if confidential fields are selected
        if not confidential_fields:
            return jsonify({"error": "No confidential fields selected. Please select fields to process using the checkboxes above."})

        # Create a copy for processing
        processed_df = df.copy()

        def mask(val):
            return '*' * len(str(val)) if pd.notna(val) and str(val).strip() != '' else val

        def hash_value(val):
            return hashlib.sha256(str(val).encode()).hexdigest()[:10] if pd.notna(val) else val

        def encrypt(val):
            return base64.b64encode(str(val).encode()).decode() if pd.notna(val) else val

        def tokenize(val):
            return f"TOKEN_{abs(hash(str(val))) % 10000}" if pd.notna(val) else val

        # Apply operations ONLY to confidential fields
        for col in processed_df.columns:
            if col in confidential_fields:  # Only process confidential fields
                if operation == 'masking':
                    processed_df[col] = processed_df[col].apply(mask)
                elif operation == 'hashing':
                    processed_df[col] = processed_df[col].apply(hash_value)
                elif operation == 'encryption':
                    processed_df[col] = processed_df[col].apply(encrypt)
                elif operation == 'tokenization':
                    processed_df[col] = processed_df[col].apply(tokenize)
                elif operation == 'apply_all':
                    # Apply all operations in sequence
                    processed_df[col] = processed_df[col].apply(lambda x: encrypt(tokenize(mask(hash_value(x)))))

        result_html = processed_df.to_html(index=False, classes='table table-striped table-bordered', border=0)
        
        confidential_count = len(confidential_fields)
        message = f"{operation.replace('_', ' ').title()} applied to {confidential_count} confidential field(s): {', '.join(confidential_fields)}"
        
        return jsonify({
            "success": True,
            "message": message,
            "table": result_html,
            "rows_processed": len(processed_df),
            "confidential_fields_processed": confidential_fields
        })

    except Exception as e:
        return jsonify({"error": f"Error processing {operation}: {str(e)}"})

@app.route('/show-all')
def show_all():
    try:
        data = get_all_data()
        if not data:
            return jsonify({"message": "No data available. Please upload a file first."})
        
        # Convert to DataFrame for HTML table
        df = pd.DataFrame(data)
        table_html = df.to_html(index=False, classes='table table-striped table-bordered', border=0)
        
        return jsonify({
            "success": True,
            "message": f"Showing all {len(data)} entries",
            "table": table_html,
            "total_entries": len(data)
        })
    except Exception as e:
        return jsonify({"error": f"Error retrieving data: {str(e)}"})

@app.route('/statistics')
def statistics():
    try:
        stats = compute_statistics()
        return jsonify({
            "success": True,
            "message": "Data insights generated successfully",
            "statistics": stats
        })
    except Exception as e:
        return jsonify({"error": f"Error computing statistics: {str(e)}"})

# Store confidential fields selection
confidential_fields = []

@app.route('/set-confidential-fields', methods=['POST'])
def set_confidential_fields():
    global confidential_fields
    try:
        data = request.get_json()
        confidential_fields = data.get('fields', [])
        return jsonify({
            "success": True,
            "message": f"Confidential fields updated: {', '.join(confidential_fields) if confidential_fields else 'None selected'}",
            "fields": confidential_fields
        })
    except Exception as e:
        return jsonify({"error": f"Error updating confidential fields: {str(e)}"})

@app.route('/get-columns')
def get_columns():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(data)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return jsonify({"columns": columns})
    except Exception as e:
        return jsonify({"error": f"Error getting columns: {str(e)}"})

# Add query endpoint for the quick query functionality
# Add this enhanced query endpoint to replace your existing /query route in app.py

@app.route('/query', methods=['POST'])
def process_query():
    try:
        query = request.json.get('query', '').lower().strip()
        
        if not query:
            return jsonify({"error": "Please enter a query"})
        
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query("SELECT * FROM data", conn)
        conn.close()
        
        if df.empty:
            return jsonify({"error": "No data available. Please upload a file first."})
        
        result_html = ""
        message = ""
        
        # Enhanced query processing
        try:
            # 1. Show all entries
            if any(phrase in query for phrase in ["show all", "all entries", "display all", "list all"]):
                result_html = df.to_html(index=False, classes='table table-striped table-bordered', border=0)
                message = f"Showing all {len(df)} entries"
            
            # 2. Count queries
            elif "count" in query:
                count = len(df)
                message = f"Total entries: {count}"
                result_html = f"<div class='alert alert-info h5'>Total number of entries: <strong>{count}</strong></div>"
            
            # 3. Column-based searches
            elif any(word in query for word in ["show", "find", "search", "get", "list"]):
                # Extract potential column names and search terms
                words = query.replace(",", " ").split()
                
                # Look for column names in the query
                matching_columns = []
                search_terms = []
                
                for word in words:
                    # Check if word matches any column name (fuzzy matching)
                    for col in df.columns:
                        if word in col.lower() or col.lower() in word:
                            if col not in matching_columns:
                                matching_columns.append(col)
                    
                    # Collect potential search terms (skip common words)
                    if word not in ['show', 'find', 'search', 'get', 'list', 'where', 'with', 'all', 'entries', 'data']:
                        search_terms.append(word)
                
                # If specific columns mentioned, show only those columns
                if matching_columns:
                    display_df = df[matching_columns]
                    result_html = display_df.to_html(index=False, classes='table table-striped table-bordered', border=0)
                    message = f"Showing {', '.join(matching_columns)} columns ({len(df)} entries)"
                
                # If search terms provided, filter data
                elif search_terms:
                    filtered_df = df.copy()
                    
                    # Search across all text columns
                    mask = pd.Series([False] * len(df))
                    
                    for term in search_terms:
                        for col in df.columns:
                            # Convert to string and search (case-insensitive)
                            col_mask = df[col].astype(str).str.lower().str.contains(term, na=False)
                            mask = mask | col_mask
                    
                    filtered_df = df[mask]
                    
                    if len(filtered_df) > 0:
                        result_html = filtered_df.to_html(index=False, classes='table table-striped table-bordered', border=0)
                        message = f"Found {len(filtered_df)} entries matching '{' '.join(search_terms)}'"
                    else:
                        result_html = "<div class='alert alert-warning'>No entries found matching your search terms.</div>"
                        message = f"No results found for '{' '.join(search_terms)}'"
                
                else:
                    # Default: show all data
                    result_html = df.to_html(index=False, classes='table table-striped table-bordered', border=0)
                    message = f"Showing all {len(df)} entries"
            
            # 4. Statistics queries
            elif any(phrase in query for phrase in ["stats", "statistics", "summary", "analyze", "analysis"]):
                stats = compute_statistics()
                
                # Format statistics as HTML
                result_html = "<div class='row'>"
                
                for key, stat in stats.items():
                    result_html += f"<div class='col-md-6 mb-3'>"
                    result_html += f"<div class='card'><div class='card-body'>"
                    result_html += f"<h6 class='card-title'>{key}</h6>"
                    
                    if isinstance(stat, dict):
                        for sub_key, value in stat.items():
                            result_html += f"<p class='card-text mb-1'><strong>{sub_key.replace('_', ' ').title()}:</strong> {value}</p>"
                    else:
                        result_html += f"<p class='card-text'>{stat}</p>"
                    
                    result_html += "</div></div></div>"
                
                result_html += "</div>"
                message = "Statistical analysis of your data"
            
            # 5. Column information queries
            elif any(phrase in query for phrase in ["columns", "fields", "headers", "what columns"]):
                columns_info = f"<div class='alert alert-info'><h5>Available Columns ({len(df.columns)}):</h5>"
                columns_info += "<ul class='list-unstyled'>"
                
                for col in df.columns:
                    data_type = df[col].dtype
                    unique_count = df[col].nunique()
                    columns_info += f"<li><strong>{col}</strong> - Type: {data_type}, Unique values: {unique_count}</li>"
                
                columns_info += "</ul></div>"
                result_html = columns_info
                message = f"Information about {len(df.columns)} columns"
            
            # 6. Unique values queries
            elif "unique" in query:
                words = query.split()
                target_column = None
                
                # Find column name in query
                for word in words:
                    for col in df.columns:
                        if word in col.lower() or col.lower() in word:
                            target_column = col
                            break
                    if target_column:
                        break
                
                if target_column:
                    unique_values = df[target_column].unique()
                    unique_df = pd.DataFrame({target_column: unique_values})
                    result_html = unique_df.to_html(index=False, classes='table table-striped table-bordered', border=0)
                    message = f"Unique values in '{target_column}' column ({len(unique_values)} unique values)"
                else:
                    result_html = "<div class='alert alert-warning'>Please specify a column name for unique values query.</div>"
                    message = "Column not specified for unique values"
            
            # 7. Filter by value queries (e.g., "show where name is john")
            elif any(phrase in query for phrase in ["where", "equals", "is", "="]):
                # Simple parsing for "where column is value" type queries
                parts = query.replace("show", "").replace("where", "").replace("is", "=").replace("equals", "=").strip()
                
                if "=" in parts:
                    try:
                        column_part, value_part = parts.split("=", 1)
                        column_part = column_part.strip()
                        value_part = value_part.strip()
                        
                        # Find matching column
                        target_column = None
                        for col in df.columns:
                            if column_part in col.lower() or col.lower() in column_part:
                                target_column = col
                                break
                        
                        if target_column:
                            # Filter data
                            filtered_df = df[df[target_column].astype(str).str.lower().str.contains(value_part, na=False)]
                            
                            if len(filtered_df) > 0:
                                result_html = filtered_df.to_html(index=False, classes='table table-striped table-bordered', border=0)
                                message = f"Found {len(filtered_df)} entries where {target_column} contains '{value_part}'"
                            else:
                                result_html = "<div class='alert alert-warning'>No entries found matching the criteria.</div>"
                                message = f"No results found for {target_column} = {value_part}"
                        else:
                            result_html = "<div class='alert alert-warning'>Column not found in data.</div>"
                            message = "Specified column not found"
                    except:
                        result_html = "<div class='alert alert-warning'>Could not parse the filter query. Try: 'show where column_name is value'</div>"
                        message = "Query format not recognized"
                else:
                    result_html = "<div class='alert alert-warning'>Filter queries should include '=' or 'is'. Example: 'show where name is john'</div>"
                    message = "Invalid filter format"
            
            # 8. Default fallback - try to search for the query term across all data
            else:
                # Search for the query term across all columns
                mask = pd.Series([False] * len(df))
                
                for col in df.columns:
                    col_mask = df[col].astype(str).str.lower().str.contains(query, na=False)
                    mask = mask | col_mask
                
                filtered_df = df[mask]
                
                if len(filtered_df) > 0:
                    result_html = filtered_df.to_html(index=False, classes='table table-striped table-bordered', border=0)
                    message = f"Found {len(filtered_df)} entries containing '{query}'"
                else:
                    # Show helpful suggestions
                    suggestions = [
                        "Try: 'show all entries'",
                        "Try: 'count'",
                        f"Try: 'show {df.columns[0]}'" if len(df.columns) > 0 else "",
                        "Try: 'statistics'",
                        "Try: 'columns'",
                        f"Try: 'unique {df.columns[0]}'" if len(df.columns) > 0 else "",
                        "Try: 'show where column_name is value'"
                    ]
                    
                    suggestions_html = "<div class='alert alert-info'><h6>No results found. Try these examples:</h6><ul>"
                    for suggestion in suggestions:
                        if suggestion:  # Only add non-empty suggestions
                            suggestions_html += f"<li>{suggestion}</li>"
                    suggestions_html += "</ul></div>"
                    
                    result_html = suggestions_html
                    message = f"No results found for '{query}'"
        
        except Exception as query_error:
            result_html = f"<div class='alert alert-danger'>Error processing query: {str(query_error)}</div>"
            message = "Query processing error"
        
        return jsonify({
            "success": True,
            "message": message,
            "table": result_html,
            "query": query
        })
        
    except Exception as e:
        return jsonify({"error": f"Error processing query: {str(e)}"})


# Optional: Add a helper endpoint to get query suggestions
@app.route('/query-help')
def query_help():
    try:
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query("SELECT * FROM data", conn)
        conn.close()
        
        if df.empty:
            return jsonify({"error": "No data available"})
        
        # Generate helpful query examples based on actual data
        examples = [
            "show all entries",
            "count",
            "statistics",
            "columns",
        ]
        
        # Add column-specific examples
        for col in df.columns[:3]:  # Show examples for first 3 columns
            examples.append(f"show {col}")
            examples.append(f"unique {col}")
            
            # Add a sample filter query if there's data
            if not df[col].empty:
                sample_value = str(df[col].iloc[0])[:20]  # First 20 chars
                examples.append(f"show where {col} is {sample_value}")
        
        return jsonify({
            "success": True,
            "examples": examples,
            "columns": list(df.columns)
        })
        
    except Exception as e:
        return jsonify({"error": f"Error getting query help: {str(e)}"})
    


if __name__ == '__main__':
    app.run(debug=True)