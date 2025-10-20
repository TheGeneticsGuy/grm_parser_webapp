import os
import json
from io import StringIO
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, request, render_template, redirect, url_for, session
from flask_session import Session
from parsing_logic import process_lua_content, format_to_text, format_to_csv


app = Flask(__name__)

# --- CONFIGURATION FOR SERVER-SIDE SESSIONS ---
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file part", 400

        file = request.files['file']
        if file.filename == '' or not file.filename.endswith('.lua'):
            return "Invalid file type. Please upload a .lua file.", 400

        # Read file content
        try:
            lua_content = file.read().decode('utf-8', errors='ignore')
        except Exception as e:
             return f"Error reading file content: {e}", 500

        # Run processing logic
        try:
            log_data = process_lua_content(lua_content)
        except Exception as e:
            print(f"Parsing error: {e}")
            return f"Error processing file. Please ensure it is the correct GRM Save Variables file. Debug: {e}", 500

        # Store the processed data in the session (this now saves to a server file)
        session['grm_log_data'] = log_data
        session['guild_metadata'] = {
            name: len(logs) for name, logs in log_data.items()
        }

        return redirect(url_for('select_export'))

    return render_template('upload.html')

@app.route('/select', methods=['GET'])
def select_export():
    if 'guild_metadata' not in session:
        return redirect(url_for('upload_file'))

    metadata = session['guild_metadata']
    return render_template('select.html', guilds=metadata)

@app.route('/export', methods=['POST'])
def export_data():
    if 'grm_log_data' not in session:
        return redirect(url_for('upload_file'))

    selected_guild = request.form.get('guild_name')
    export_format = request.form.get('format')

    full_data = session['grm_log_data']

    # 1. Determine data subset and filename
    if selected_guild == 'ALL':
        data_to_export = full_data
        filename = "grm_logs_ALL"
    elif selected_guild in full_data:
        data_to_export = {selected_guild: full_data[selected_guild]}
        # Clean the guild name for a safe filename
        safe_guild_name = selected_guild.replace(' ', '_').replace('[', '').replace(']', '').replace('-', '_')
        filename = f"grm_logs_{safe_guild_name}"
    else:
        return "Invalid guild selected.", 400

    # 2. Generate content based on format
    content_type = ""
    file_extension = ""
    output_content = ""

    if export_format == 'json':
        output_content = json.dumps(data_to_export, indent=4, ensure_ascii=False)
        content_type = 'application/json'
        file_extension = '.json'

    elif export_format == 'text':
        output_content = format_to_text(data_to_export)
        content_type = 'text/plain'
        file_extension = '.txt'

    elif export_format == 'csv':
        output_content = format_to_csv(data_to_export)
        content_type = 'text/csv'
        file_extension = '.csv'

    else:
        return "Invalid export format.", 400

    # 3. Using StringIO to serve the content directly without saving a temporary file to disk
    # This is safer and cleaner for ephemeral web apps like this.
    str_io = StringIO()
    str_io.write(output_content)
    str_io.seek(0)

    # Flask response to force download
    from flask import make_response
    response = make_response(str_io.read())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}{file_extension}"
    response.headers["Content-type"] = content_type

    # Clearing the session data immediately after starting the download
    session.pop('grm_log_data', None)
    session.pop('guild_metadata', None)

    return response

if __name__ == '__main__':
    # Flask default is 5000
    app.run(debug=True)