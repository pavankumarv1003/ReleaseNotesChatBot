# app.py
import dash
# CORRECTED IMPORT: PreventUpdate comes from dash.exceptions
from dash import dcc, html, Input, Output, State, callback_context, ALL, MATCH
from dash.exceptions import PreventUpdate
import base64
import io
import time
import traceback # Import traceback for better error printing

from chatbot import update_chatbot_instance, get_chatbot_instance, reset_chatbot_instance

# --- Initialize Dash App ---
# No Bootstrap theme needed, rely on custom CSS
# Make sure assets_folder points correctly if your structure differs
app = dash.Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets')
server = app.server

# --- Helper Function: Generate Chat Display Elements (Updated for new classes) ---
def display_chat_elements(chat_history):
    if not chat_history:
        # Initial message centered in the chat area
        return [html.Div("Start by uploading a release note document using the panel above.",
                         style={'textAlign': 'center', 'padding': '40px', 'color': 'var(--text-secondary)'})]

    chat_elements = []
    for i, entry in enumerate(chat_history):
        question = entry.get('Q', 'N/A')
        answer = entry.get('A', 'N/A')
        answer_id = f"answer-text-{i}"
        button_id = {"type": "copy-button", "index": i}
        clipboard_id = f"clipboard-{i}"

        # User Message Block
        chat_elements.append(html.Div([ # message-container
            html.Div( # message-bubble user-message
                html.P(question, className='message-content')
            , className='message-bubble user-message')
        ], className='message-container'))


        # Bot Message Block
        chat_elements.append(html.Div([ # message-container
            html.Div([ # message-bubble bot-message
                html.P(answer, className='message-content', id=answer_id),
                # Copy Button/Clipboard Area
                html.Div([
                    dcc.Clipboard(id=clipboard_id, target_id=answer_id, className='dash-clipboard'),
                    html.Button("Copy", id=button_id, className="copy-button", n_clicks=0, title="Copy answer")
                ], className="clipboard-container")
            ], className='message-bubble bot-message')
        ], className='message-container'))


    return chat_elements

# --- App Layout ---
app.layout = html.Div(id='app-container', children=[

    # Stores remain hidden
    dcc.Store(id='chat-history-store', data=[]),
    dcc.Store(id='file-status-store', data={'filename': None, 'processed': False, 'error': None, 'num_chunks': 0}),

    # --- Sidebar ---
    html.Div(id='sidebar', children=[
        html.H5("Controls"),
        html.Button([html.I(className="fas fa-redo"), html.Span("Reset Chat", className="btn-text")], # Assuming FontAwesome via CDN or local setup for icon
                      id='reset-button', n_clicks=0, className='sidebar-button'),
        html.Div(style={'marginTop': 'auto', 'fontSize': '0.8em', 'color': '#888'}, children=["ReleaseNote Bot v1.0"])
    ]),

    # --- Main Content Area ---
    html.Div(id='main-content', children=[

        # --- Top Area (Upload/Info) ---
        html.Div(id='top-main-area', children=[
             dcc.Upload(
                id='upload-data',
                children=html.Div([
                    'Drag and Drop or ', html.A('Select a File'), ' (PDF, DOCX, TXT)'
                ]),
            ),
            html.Div(id='upload-feedback-alert'), # Feedback shown here
            html.Div(id='doc-info-area')
        ]),

        # --- Chat Display Wrapper (Scrollable) ---
        # Loading wraps the chat display. CSS handles scrolling/padding.
        dcc.Loading(id="loading-chat", type="dot",
                    children=[html.Div(id='chat-display-wrapper')] # This is the target for chat updates
                   ),

        # --- Input Bar Container (absolutely positioned) ---
        # REMOVED the outer 'input-area-wrapper' Div.
        # This container is now a direct child of 'main-content'.
        # CSS rule '#input-area-container' handles its absolute positioning.
        html.Div(id='input-area-container', children=[
            # Use a standard div for form-like structure
            html.Div(id='input-form', children=[
                dcc.Textarea(
                    id='user-question',
                    placeholder='Ask a question...',
                    disabled=True,
                    rows=1,
                ),
                html.Button('Ask',
                            id='ask-button', n_clicks=0, disabled=True)
            ]),
        ]),
        # End of Input Bar Container

    ]) # End main-content
]) # End app-container


# --- CALLBACKS ---

# Callback 1: Handle Upload
@app.callback(
    Output('file-status-store', 'data'),
    Output('upload-feedback-alert', 'children'),
    Output('doc-info-area', 'children'),
    Output('user-question', 'disabled'),
    Output('ask-button', 'disabled'),
    Output('chat-history-store', 'data', allow_duplicate=True),
    Output('chat-display-wrapper', 'children', allow_duplicate=True), # Update chat display directly on upload
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    prevent_initial_call=True
)
def handle_upload(contents, filename):
    if contents is not None:
        chat_history_reset = []
        initial_chat_display = [html.Div("Processing file...", style={'textAlign': 'center', 'color': 'var(--text-secondary)', 'padding':'20px'})]
        doc_info = ""
        alert = html.Div("Processing file, please wait...", className="alert alert-info")

        try:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            allowed_extensions = ('.pdf', '.docx', '.txt')

            if filename and filename.lower().endswith(allowed_extensions):
                print(f"Received file: {filename}")
                result = update_chatbot_instance(filename, decoded) # Calls chatbot init

                if isinstance(result, str): # Error during processing
                    status = {'filename': filename, 'processed': False, 'error': result, 'num_chunks': 0}
                    alert = html.Div(f"Error: {result}", className="alert alert-danger")
                    question_disabled = True; ask_disabled = True; doc_info = ""
                    initial_chat_display = [html.Div(f"Error processing: {result}", style={'textAlign': 'center', 'color': '#f1aeb5', 'padding':'20px'})]

                else: # Success
                     chatbot_instance = result
                     status = {'filename': filename, 'processed': True, 'error': None, 'num_chunks': chatbot_instance.num_chunks}
                     alert = html.Div(f"File '{filename}' processed!", className="alert alert-success")
                     question_disabled = False; ask_disabled = False
                     doc_info = f"Loaded: {filename} ({status['num_chunks']} chunks)"
                     initial_chat_display = [html.Div("Ready to answer questions.", style={'textAlign': 'center', 'color': 'var(--text-secondary)', 'padding':'20px'})]

            else: # Invalid file type
                status = {'filename': filename, 'processed': False, 'error': 'Invalid file type', 'num_chunks': 0}
                alert = html.Div(f"Invalid file type: '{filename}'. Use PDF, DOCX, or TXT.", className="alert alert-danger")
                question_disabled = True; ask_disabled = True; doc_info = ""
                reset_chatbot_instance()
                initial_chat_display = [html.Div("Invalid file type.", style={'textAlign': 'center', 'color': 'orange', 'padding':'20px'})]

            return status, alert, doc_info, question_disabled, ask_disabled, chat_history_reset, initial_chat_display

        except Exception as e:
             print(f"Error during file upload processing: {e}")
             traceback.print_exc()
             status = {'filename': filename, 'processed': False, 'error': f'Upload error: {e}', 'num_chunks': 0}
             alert = html.Div(f"Upload Error: {e}", className="alert alert-danger")
             reset_chatbot_instance()
             error_chat_display = [html.Div(f"Upload Error: {e}", style={'textAlign': 'center', 'color': '#f1aeb5', 'padding':'20px'})]
             return status, alert, "", True, True, chat_history_reset, error_chat_display

    raise PreventUpdate


# Callback 2: Handle Asking Questions (SIMPLIFIED VERSION)
@app.callback(
    Output('chat-history-store', 'data'), # Update store only triggers CB3
    Output('user-question', 'value'), # Clear input
    Input('ask-button', 'n_clicks'),
    State('user-question', 'value'),
    State('chat-history-store', 'data'),
    State('file-status-store', 'data'),
    prevent_initial_call=True
)
def handle_ask(n_clicks, question, chat_history, file_status):
    if n_clicks > 0 and question and file_status.get('processed'):
        chatbot = get_chatbot_instance()
        if chatbot:
            print(f"Asking question: {question}")

            try:
                answer = chatbot.get_answer(question)
                print(f"Received answer: {answer[:100]}...")
                new_entry = {"Q": question, "A": answer}
            except Exception as e:
                print(f"Error getting answer: {e}")
                traceback.print_exc()
                new_entry = {"Q": question, "A": f"Sorry, an error occurred while generating the answer: {e}"}

            if chat_history is None:
                chat_history = []
            updated_history = chat_history + [new_entry]

            return updated_history, ""
        else:
             error_entry = {"Q": question, "A": "Error: Chatbot not ready. Please Reset and re-upload."}
             if chat_history is None:
                 chat_history = []
             updated_history = chat_history + [error_entry]
             return updated_history, ""

    raise PreventUpdate


# Callback 3: Update Chat Display Area based on Store
@app.callback(
    Output('chat-display-wrapper', 'children', allow_duplicate=True),
    Input('chat-history-store', 'data'),
    prevent_initial_call=True
)
def update_chat_display_from_store(chat_history):
    print("Updating chat display from store change.")
    if chat_history is None:
        return []
    return display_chat_elements(chat_history or [])


# Callback 4: Handle Reset Button
@app.callback(
    Output('chat-history-store', 'data', allow_duplicate=True),
    Output('file-status-store', 'data', allow_duplicate=True),
    Output('upload-feedback-alert', 'children', allow_duplicate=True),
    Output('doc-info-area', 'children', allow_duplicate=True),
    Output('user-question', 'value', allow_duplicate=True),
    Output('user-question', 'disabled', allow_duplicate=True),
    Output('ask-button', 'disabled', allow_duplicate=True),
    Output('chat-display-wrapper', 'children', allow_duplicate=True),
    Input('reset-button', 'n_clicks'),
    prevent_initial_call=True
)
def handle_reset(n_clicks):
    if n_clicks > 0:
        print("Reset button clicked.")
        reset_chatbot_instance()
        initial_file_status = {'filename': None, 'processed': False, 'error': None, 'num_chunks': 0}
        initial_history = []
        reset_alert = html.Div("Chat reset. Upload a file.", className="alert alert-warning")
        initial_doc_info = ""
        initial_question = ""
        question_disabled = True; ask_disabled = True
        initial_chat_display = display_chat_elements([])

        return (initial_history, initial_file_status, reset_alert, initial_doc_info,
                initial_question, question_disabled, ask_disabled, initial_chat_display)
    raise PreventUpdate


# Callback 5: Handle Copy Button Clicks
@app.callback(
    Input({"type": "copy-button", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_copy_click(n_clicks):
    ctx = dash.callback_context
    if not ctx.triggered or not any(click is not None and click > 0 for click in n_clicks):
        raise PreventUpdate

    triggered_id = ctx.triggered_id
    if isinstance(triggered_id, dict) and 'index' in triggered_id:
         clicked_index = triggered_id['index']
         print(f"Copy button {clicked_index} clicked (clipboard action handled by dcc.Clipboard).")
    else:
         print("Copy button clicked, but couldn't identify index.")

    raise PreventUpdate


# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=True)
