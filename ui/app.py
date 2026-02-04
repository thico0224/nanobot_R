import os
import re
import subprocess
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Force Python to use UTF-8 for all sub-processes
os.environ["PYTHONIOENCODING"] = "utf-8"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    try:
        # Run Nanobot Agent
        process = subprocess.run(
            ["nanobot", "agent", "-m", user_input],
            capture_output=True,
            text=True,
            shell=True,
            encoding='utf-8',
            errors='ignore'
        )

        full_output = (process.stdout or "") + "\n" + (process.stderr or "")

        # Surgical extraction of the AI response from the Traceback/Locals
        match = re.search(r"response\s*=\s*['\"](.*?)['\"]", full_output, re.DOTALL)

        if match:
            # Decode unicode escapes (e.g., \n -> actual newline)
            answer = match.group(1).encode('utf-8').decode('unicode_escape', errors='ignore')
        else:
            # Fallback: clean the output from any Rich/Traceback lines
            lines = [l for l in full_output.split('\n') if '|' not in l and 'Traceback' not in l]
            answer = "\n".join(lines).strip()

        if not answer or "agent" in answer.lower() and "cli" in answer.lower():
            answer = "Task completed, but I couldn't parse the specific text. Please check your console."

        return jsonify({"status": "success", "reply": answer})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


if __name__ == '__main__':
    print("Starting Nanobot Web Interface at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)