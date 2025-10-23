import asyncio
import aiohttp
import io
import pandas as pd
import plotly.express as px
from flask import Flask, render_template, request
import json # Import the json library

# --- Block 1: Setup ---
app = Flask(__name__)

# --- Block 2: AI Configuration (CRITICAL CHANGES) ---
SYSTEM_PROMPT = """
You are an automated data extraction bot.
Your ONLY job is to find structured data and return it as a CSV.
You MUST follow these rules:
1.  The first line MUST be the CSV headers.
2.  You MUST NOT add any introduction, explanation, or notes.
3.  If you find no data, you MUST return the single string: "Error: No structured data found."
4.  Do not use any formatting like markdown.
"""

# THIS IS THE CORRECT API URL FOR THIS ENVIRONMENT
API_URL = "https://generativelen.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=AIzaSyAU6Z3CSRSS9XdcLn7TTTEQwUVSlGgUilg"

# THIS IS THE MOST IMPORTANT PART: LEAVE THE KEY EMPTY.
# The server will provide it automatically. DO NOT PASTE YOUR OWN KEY.
API_KEY = "AIzaSyAU6Z3CSRSS9XdcLn7TTTEQwUVSlGgUilg" 

# --- Block 3: Asynchronous AI Call Function ---
async def call_gemini(article_text):
    """Makes an async call to the Gemini API to extract data."""
    
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": article_text}]}],
    }
    
    full_api_url = API_URL + API_KEY
    
    async with aiohttp.ClientSession() as session:
        for i in range(3): # Max 3 retries
            try:
                async with session.post(full_api_url, json=payload, headers={'Content-Type': 'application/json'}) as response:
                    
                    if response.status != 200:
                        # If we get a bad status, try to read the error message from Google
                        error_text = await response.text()
                        return f"Error: API call failed with status {response.status}. Response: {error_text}"

                    result_text = await response.text()
                    
                    try:
                        result = json.loads(result_text)
                    except json.JSONDecodeError:
                        return f"Error: Failed to decode AI response. Response was: {result_text}"

                    if result.get('candidates'):
                        return result['candidates'][0]['content']['parts'][0]['text']
                    else:
                        if result.get('promptFeedback'):
                             return f"Error: AI call blocked. Reason: {result['promptFeedback']['blockReason']}"
                        return f"Error: Invalid API response structure. Response: {result_text}"

            except aiohttp.ClientError as e:
                if i == 2:
                    return f"Error: API call failed after retries. Check internet connection. {e}"
                await asyncio.sleep(2**i)
                
    return "Error: Could not contact AI service after all retries."


# --- Block 4: The Main Route (Handles everything) ---
@app.route('/', methods=['GET', 'POST'])
def index():
    # These variables will be sent to the HTML
    extracted_data = ""
    column_headers = []
    graph_html = None
    error_message = None

    try:
        if request.method == 'POST':
            data_from_textarea = request.form.get('data_textarea', '')
            chart_type = request.form.get('chart_type', 'bar')
            x_col = request.form.get('x_col')
            y_col = request.form.get('y_col')
            
            if 'extract_button' in request.form:
                article_text = request.form['article_content']
                if not article_text:
                    raise Exception("Please paste an article first.")
                
                extracted_data = asyncio.run(call_gemini(article_text))
                
                if extracted_data.startswith('Error:'):
                    raise Exception(extracted_data)
                
                try:
                    df = pd.read_csv(io.StringIO(extracted_data))
                    column_headers = df.columns.tolist()
                except Exception as e:
                    raise Exception(f"AI returned data, but Pandas couldn't read it. Error: {e} | AI Data: '{extracted_data}'")

            elif 'visualize_button' in request.form:
                if not data_from_textarea:
                    raise Exception("Please extract data first.")
                if not x_col or not y_col:
                    raise Exception("Please select X-Axis and Y-Axis.")

                extracted_data = data_from_textarea
                data_file = io.StringIO(extracted_data)
                df = pd.read_csv(data_file)
                column_headers = df.columns.tolist()

                fig = None
                if chart_type == 'bar':
                    fig = px.bar(df, x=x_col, y=y_col, title=f"Bar Chart of {y_col} by {x_col}")
                elif chart_type == 'line':
                    fig = px.line(df, x=x_col, y=y_col, title=f"Line Chart of {y_col} by {x_col}")
                elif chart_type == 'pie':
                    fig = px.pie(df, names=x_col, values=y_col, title=f"Pie Chart of {y_col}")
                
                if fig:
                    fig.update_layout(paper_bgcolor='white', plot_bgcolor='white')
                    graph_html = fig.to_html(full_html=False)

    except Exception as e:
        error_message = f"An error occurred: {e}"

    return render_template('index_ai.html',
                           graph_html=graph_html,
                           extracted_data=extracted_data,
                           column_headers=column_headers,
                           error_message=error_message)

# --- Block 5: The "Run" Command ---
if __name__ == '__main__':
    app.run(debug=True)