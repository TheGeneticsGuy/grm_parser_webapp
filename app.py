import os
import json
from io import StringIO
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, request, render_template, redirect, url_for, session
from flask_session import Session

app = Flask(__name__)

# --- CONFIGURATION FOR SERVER-SIDE SESSIONS ---
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')

from parsing_logic import process_lua_content, format_to_text, format_to_csv

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    # If it's a GET request, clearing any previous session data for a fresh start
    if request.method == 'GET':
        session.pop('grm_log_data', None)
        session.pop('guild_metadata', None)

    if request.method == 'POST':
        if 'file' not in request.files or not request.files['file'].filename:
            return render_template('error.html', message='No file was selected. Please try again.')

        file = request.files['file']
        if file.filename != 'Guild_Roster_Manager.lua' or not file.filename.endswith('.lua'):
            return render_template('error.html', message='Invalid file. Only Guild_Roster_Manager.lua save file is accepted.')

        try:
            lua_content = file.read().decode('utf-8', errors='ignore')
            log_data = process_lua_content(lua_content)

            # Check if parsing produced any data
            if not log_data:
                return render_template('error.html', message='Could not find any valid GRM log data in the file.')

        except Exception as e:
            print(f"Parsing error: {e}")
            return render_template('error.html', message='There was an error processing your file. Please ensure it is an unmodified GRM save file.')

        session['grm_log_data'] = log_data
        session['guild_metadata'] = {
            name: len(logs) for name, logs in log_data.items()
        }
        return redirect(url_for('select_export'))

    return render_template('upload.html')

@app.route('/select')
def select_export():
    if 'guild_metadata' not in session:
        return redirect(url_for('upload_file'))

    metadata = session.get('guild_metadata', {})
    return render_template('select.html', guilds=metadata)

@app.route('/export', methods=['POST'])
def export_data():
    if 'grm_log_data' not in session:
        return render_template('error.html', message='Your session has expired. Please upload your file again.')

    # ... The rest of your export_data function ...
    # CRITICAL CHANGE: We will NO LONGER clear the session here.
    # The session will persist until the user returns to the homepage.

    # ... (all your existing logic for generating the file) ...

    # Example snippet, ensure your full logic is here
    selected_guild = request.form.get('guild_name')
    export_format = request.form.get('format')
    full_data = session['grm_log_data']

    # Your logic for data_to_export and filename
    if selected_guild == 'ALL':
        data_to_export = full_data
        filename = "grm_logs_ALL"
    else:
        data_to_export = {selected_guild: full_data.get(selected_guild, [])}
        filename = f"grm_logs_{selected_guild.replace(' ', '_')}"

    # Your logic for output_content and content_type
    output_content = ""
    if export_format == 'csv':
        output_content = format_to_csv(data_to_export)
        content_type = 'text/csv'
        file_extension = '.csv'
    elif export_format == 'text':
        output_content = format_to_text(data_to_export)
        content_type = 'text/plain'
        file_extension = '.txt'
    else: # json
        output_content = json.dumps(data_to_export, indent=4, ensure_ascii=False)
        content_type = 'application/json'
        file_extension = '.json'

    str_io = StringIO()
    str_io.write(output_content)
    str_io.seek(0)

    from flask import make_response
    response = make_response(str_io.read())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}{file_extension}"
    response.headers["Content-type"] = content_type

    # REMOVED session.pop() lines
    return response

if __name__ == '__main__':
    app.run(debug=True)