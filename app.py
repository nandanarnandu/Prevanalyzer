from flask import Flask, request, jsonify, render_template, Response
from werkzeug.utils import secure_filename
import os
import pandas as pd
import sqlite3
import hashlib
import base64
from connection import get_ai_response  # Added import for AI connection

app = Flask(__name__)  # ✅ Fixed here

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
DATABASE = 'data.db'
ALLOWED_EXTENSIONS = {'xls', 'xlsx', 'csv'}

confidential_fields = []  # Global variable

# ---------- Utility Functions ----------

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

# ---------- Routes ----------

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

        # Normalize column names
        df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]

        # Apply protections
        protection_map = {}

        def mask_email(val):
            if pd.isna(val): return val
            email_str = str(val)
            if '@' in email_str:
                parts = email_str.split('@')
                if len(parts[0]) > 2:
                    masked = parts[0][:1] + '*' * (len(parts[0]) - 2) + parts[0][-1:] + '@' + parts[1]
                    return masked
            return email_str

        def hash_value(val):
            if pd.isna(val): return val
            return hashlib.sha256(str(val).encode()).hexdigest()[:10]

        def tokenize(val):
            if pd.isna(val): return val
            return f"TOKEN_{hashlib.md5(str(val).encode()).hexdigest()[:6]}"

        def encrypt(val):
            if pd.isna(val): return val
            return base64.b64encode(str(val).encode()).decode()

        for col in df.columns:
            if any(k in col for k in ['email', 'mail']):
                df[col] = df[col].apply(mask_email)
                protection_map[col] = 'masking'
            elif any(k in col for k in ['card', 'credit', 'debit']):
                df[col] = df[col].apply(hash_value)
                protection_map[col] = 'hashing'
            elif any(k in col for k in ['phone', 'contact', 'mobile']):
                df[col] = df[col].apply(tokenize)
                protection_map[col] = 'tokenization'
            elif any(k in col for k in ['address', 'location']):
                df[col] = df[col].apply(encrypt)
                protection_map[col] = 'encryption'

        # Store to SQLite
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS data;")
        column_defs = ', '.join([f'"{col}" TEXT' for col in df.columns])
        cursor.execute(f'CREATE TABLE data ({column_defs});')
        insert_query = f"INSERT INTO data ({', '.join([f'"{col}"' for col in df.columns])}) VALUES ({', '.join(['?'] * len(df.columns))})"
        for _, row in df.iterrows():
            cursor.execute(insert_query, tuple(str(x) for x in row.tolist()))
        conn.commit()
        conn.close()
        os.remove(filepath)

        global confidential_fields
        confidential_fields = list(protection_map.keys())

        preview_html = df.head(5).to_html(index=False, classes='table table-bordered table-striped', border=0)

        return jsonify(
            success=True,
            message="File uploaded, protected, and saved successfully.",
            columns=list(df.columns),
            confidential_fields=list(protection_map.items()),
            preview_data=df.head(5).to_dict(orient='records'),
            table=preview_html
        )

    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify(success=False, message=f"Error: {str(e)}")


@app.route('/set-confidential-fields', methods=['POST'])
def set_conf_fields():
    global confidential_fields
    data = request.get_json()
    confidential_fields = data.get('fields', [])
    return jsonify({
        "success": True,
        "message": f"Confidential fields updated: {', '.join(confidential_fields) if confidential_fields else 'None'}",
        "fields": confidential_fields
    })


@app.route('/process/<operation>', methods=['POST'])
def process_operation(operation):
    global confidential_fields
    try:
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query("SELECT * FROM data", conn)
        conn.close()

        if df.empty:
            return jsonify({"error": "No data available."})

        if not confidential_fields:
            return jsonify({"error": "No confidential fields selected."})

        processed_df = df.copy()

        def mask(val): return '*' * len(str(val)) if pd.notna(val) else val
        def hash_value(val): return hashlib.sha256(str(val).encode()).hexdigest()[:10] if pd.notna(val) else val
        def encrypt(val): return base64.b64encode(str(val).encode()).decode() if pd.notna(val) else val
        def tokenize(val): return f"TOKEN_{abs(hash(str(val))) % 10000}" if pd.notna(val) else val

        for col in processed_df.columns:
            if col in confidential_fields:
                if operation == 'masking':
                    processed_df[col] = processed_df[col].apply(mask)
                elif operation == 'hashing':
                    processed_df[col] = processed_df[col].apply(hash_value)
                elif operation == 'encryption':
                    processed_df[col] = processed_df[col].apply(encrypt)
                elif operation == 'tokenization':
                    processed_df[col] = processed_df[col].apply(tokenize)
                elif operation == 'apply_all':
                    processed_df[col] = processed_df[col].apply(lambda x: encrypt(tokenize(hash_value(mask(x)))))

        result_html = processed_df.to_html(index=False, classes='table table-striped table-bordered', border=0)
        message = f"{operation.title()} applied to {len(confidential_fields)} fields: {', '.join(confidential_fields)}"

        return jsonify({
            "success": True,
            "message": message,
            "table": result_html,
            "rows_processed": len(processed_df)
        })

    except Exception as e:
        return jsonify({"error": f"Processing error: {str(e)}"})


@app.route('/show-all')
def show_all():
    try:
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query("SELECT * FROM data", conn)
        conn.close()
        return jsonify({
            "success": True,
            "message": "All records retrieved",
            "table": df.to_html(index=False, classes='table table-striped table-bordered')
        })
    except Exception as e:
        return jsonify({"error": f"Error fetching data: {str(e)}"})


@app.route('/statistics')
def statistics():
    try:
        stats = compute_statistics()
        return jsonify({
            "success": True,
            "message": "Data insights computed",
            "statistics": stats
        })
    except Exception as e:
        return jsonify({"error": f"Stats error: {str(e)}"})


@app.route('/get-columns', methods=['GET'])
def get_columns():
    try:
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query("SELECT * FROM data", conn)
        conn.close()
        return jsonify({"columns": list(df.columns)})
    except Exception as e:
        return jsonify({"error": f"Column fetch error: {str(e)}"})


# ---------- AI Chat Route ----------
@app.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({"error": "No question provided"}), 400
        
        # Get data context from database
        context = ""
        try:
            conn = sqlite3.connect(DATABASE)
            df = pd.read_sql_query("SELECT * FROM data LIMIT 5", conn)
            conn.close()
            
            if not df.empty:
                # Create context from data structure and sample
                context = f"Data columns: {', '.join(df.columns)}\n"
                context += f"Sample data:\n{df.head(3).to_string()}"
                print(context,"&&&&&&&&&&")
        except Exception:
            context = "No data available in the system."
        print(context,"1&&&&&&&&&&&&&&&&&&&&&&")
        # Get AI response
        response = get_ai_response(question, context)
        
        return jsonify({
            "success": True,
            "answer": response
        })
        
    except Exception as e:
        return jsonify({"error": f"Error getting AI response: {str(e)}"}), 500


# ---------- Main App Run ----------
if __name__ == '__main__':
    app.run(debug=True)# Import all the libraries we need for the web app
from flask import Flask, request, jsonify, render_template, Response
from werkzeug.utils import secure_filename
import os
import pandas as pd
import sqlite3
import hashlib
import base64
from connection import get_ai_response  # Added import for AI connection

# Create the Flask web application
app = Flask(__name__)  # ✅ Fixed here

# Set up configuration for file uploads
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
DATABASE = 'data.db'
ALLOWED_EXTENSIONS = {'xls', 'xlsx', 'csv'}

confidential_fields = []  # Global variable

# ---------- Utility Functions ----------

# Function to check if uploaded file has allowed extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to calculate statistics about the data
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
    # Calculate statistics for numeric columns
    numeric_cols = df.select_dtypes(include='number').columns
    for col in numeric_cols:
        stats[f"{col} (numeric)"] = {
            'mean': round(df[col].mean(), 2),
            'min': df[col].min(),
            'max': df[col].max(),
            'count': df[col].count()
        }

    # Calculate statistics for text columns
    non_numeric_cols = df.select_dtypes(exclude='number').columns
    for col in non_numeric_cols:
        stats[f"{col} (text)"] = {
            'unique_values': df[col].nunique(),
            'top_value': df[col].mode().iloc[0] if not df[col].mode().empty else None,
            'total_count': df[col].count()
        }

    return stats

# ---------- Routes ----------

# Home page route - shows the main webpage
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle file uploads
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
        # Read the uploaded file into a DataFrame
        if filename.endswith(('xls', 'xlsx')):
            df = pd.read_excel(filepath)
        else:
            df = pd.read_csv(filepath)

        # Clean up column names (lowercase, no spaces)
        df.columns = [col.lower().strip().replace(" ", "_") for col in df.columns]

        # Apply data protection based on column names
        protection_map = {}

        # Function to hide part of email addresses
        def mask_email(val):
            if pd.isna(val): return val
            email_str = str(val)
            if '@' in email_str:
                parts = email_str.split('@')
                if len(parts[0]) > 2:
                    masked = parts[0][:1] + '*' * (len(parts[0]) - 2) + parts[0][-1:] + '@' + parts[1]
                    return masked
            return email_str

        # Function to create a hash (scrambled version) of data
        def hash_value(val):
            if pd.isna(val): return val
            return hashlib.sha256(str(val).encode()).hexdigest()[:10]

        # Function to replace data with a token
        def tokenize(val):
            if pd.isna(val): return val
            return f"TOKEN_{hashlib.md5(str(val).encode()).hexdigest()[:6]}"

        # Function to encrypt (encode) data
        def encrypt(val):
            if pd.isna(val): return val
            return base64.b64encode(str(val).encode()).decode()

        # Automatically protect sensitive columns based on their names
        for col in df.columns:
            if any(k in col for k in ['email', 'mail']):
                df[col] = df[col].apply(mask_email)
                protection_map[col] = 'masking'
            elif any(k in col for k in ['card', 'credit', 'debit']):
                df[col] = df[col].apply(hash_value)
                protection_map[col] = 'hashing'
            elif any(k in col for k in ['phone', 'contact', 'mobile']):
                df[col] = df[col].apply(tokenize)
                protection_map[col] = 'tokenization'
            elif any(k in col for k in ['address', 'location']):
                df[col] = df[col].apply(encrypt)
                protection_map[col] = 'encryption'

        # Save the processed data to SQLite database
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS data;")
        column_defs = ', '.join([f'"{col}" TEXT' for col in df.columns])
        cursor.execute(f'CREATE TABLE data ({column_defs});')
        insert_query = f"INSERT INTO data ({', '.join([f'"{col}"' for col in df.columns])}) VALUES ({', '.join(['?'] * len(df.columns))})"
        for _, row in df.iterrows():
            cursor.execute(insert_query, tuple(str(x) for x in row.tolist()))
        conn.commit()
        conn.close()
        os.remove(filepath)  # Delete the uploaded file

        global confidential_fields
        confidential_fields = list(protection_map.keys())

        # Create HTML preview of the data
        preview_html = df.head(5).to_html(index=False, classes='table table-bordered table-striped', border=0)

        return jsonify(
            success=True,
            message="File uploaded, protected, and saved successfully.",
            columns=list(df.columns),
            confidential_fields=list(protection_map.items()),
            preview_data=df.head(5).to_dict(orient='records'),
            table=preview_html
        )

    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify(success=False, message=f"Error: {str(e)}")

# Route to manually set which fields are confidential
@app.route('/set-confidential-fields', methods=['POST'])
def set_conf_fields():
    global confidential_fields
    data = request.get_json()
    confidential_fields = data.get('fields', [])
    return jsonify({
        "success": True,
        "message": f"Confidential fields updated: {', '.join(confidential_fields) if confidential_fields else 'None'}",
        "fields": confidential_fields
    })

# Route to apply different protection operations to the data
@app.route('/process/<operation>', methods=['POST'])
def process_operation(operation):
    global confidential_fields
    try:
        # Load data from database
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query("SELECT * FROM data", conn)
        conn.close()

        if df.empty:
            return jsonify({"error": "No data available."})

        if not confidential_fields:
            return jsonify({"error": "No confidential fields selected."})

        processed_df = df.copy()

        # Define protection functions
        def mask(val): return '*' * len(str(val)) if pd.notna(val) else val
        def hash_value(val): return hashlib.sha256(str(val).encode()).hexdigest()[:10] if pd.notna(val) else val
        def encrypt(val): return base64.b64encode(str(val).encode()).decode() if pd.notna(val) else val
        def tokenize(val): return f"TOKEN_{abs(hash(str(val))) % 10000}" if pd.notna(val) else val

        # Apply the requested protection operation
        for col in processed_df.columns:
            if col in confidential_fields:
                if operation == 'masking':
                    processed_df[col] = processed_df[col].apply(mask)
                elif operation == 'hashing':
                    processed_df[col] = processed_df[col].apply(hash_value)
                elif operation == 'encryption':
                    processed_df[col] = processed_df[col].apply(encrypt)
                elif operation == 'tokenization':
                    processed_df[col] = processed_df[col].apply(tokenize)
                elif operation == 'apply_all':
                    processed_df[col] = processed_df[col].apply(lambda x: encrypt(tokenize(hash_value(mask(x)))))

        # Convert result to HTML table
        result_html = processed_df.to_html(index=False, classes='table table-striped table-bordered', border=0)
        message = f"{operation.title()} applied to {len(confidential_fields)} fields: {', '.join(confidential_fields)}"

        return jsonify({
            "success": True,
            "message": message,
            "table": result_html,
            "rows_processed": len(processed_df)
        })

    except Exception as e:
        return jsonify({"error": f"Processing error: {str(e)}"})

# Route to show all data records
@app.route('/show-all')
def show_all():
    try:
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query("SELECT * FROM data", conn)
        conn.close()
        return jsonify({
            "success": True,
            "message": "All records retrieved",
            "table": df.to_html(index=False, classes='table table-striped table-bordered')
        })
    except Exception as e:
        return jsonify({"error": f"Error fetching data: {str(e)}"})

# Route to get statistics about the data
@app.route('/statistics')
def statistics():
    try:
        stats = compute_statistics()
        return jsonify({
            "success": True,
            "message": "Data insights computed",
            "statistics": stats
        })
    except Exception as e:
        return jsonify({"error": f"Stats error: {str(e)}"})

# Route to get list of all columns
@app.route('/get-columns', methods=['GET'])
def get_columns():
    try:
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query("SELECT * FROM data", conn)
        conn.close()
        return jsonify({"columns": list(df.columns)})
    except Exception as e:
        return jsonify({"error": f"Column fetch error: {str(e)}"})

# ---------- AI Chat Route ----------
# Route to handle AI questions about the data
@app.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({"error": "No question provided"}), 400
        
        # Get data context from database to help AI understand the data
        context = ""
        try:
            conn = sqlite3.connect(DATABASE)
            df = pd.read_sql_query("SELECT * FROM data LIMIT 5", conn)
            conn.close()
            
            if not df.empty:
                # Create context from data structure and sample
                context = f"Data columns: {', '.join(df.columns)}\n"
                context += f"Sample data:\n{df.head(3).to_string()}"
        except Exception:
            context = "No data available in the system."


        print(context,"2&&&&&&&&&&&&&&&")
        
        # Get AI response using the imported function
        response = get_ai_response(question, context)
        
        return jsonify({
            "success": True,
            "answer": response
        })
        
    except Exception as e:
        return jsonify({"error": f"Error getting AI response: {str(e)}"}), 500

# ---------- Main App Run ----------
# Start the Flask web application
if __name__ == '__main__':
    app.run(debug=True,use_reloader=False)  # Set use_reloader=False to avoid double startup in debug mode