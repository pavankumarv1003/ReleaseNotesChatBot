# chatbot.py
import os
import time
import numpy as np
from dotenv import load_dotenv, find_dotenv # Import find_dotenv
import google.generativeai as genai
from utils import extract_text, preprocess_text
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from google.api_core import exceptions as google_exceptions # <-- ENSURE THIS LINE IS CORRECT


print(f"Current Working Directory: {os.getcwd()}")

# --- Explicitly find and load .env ---
dotenv_path = find_dotenv() # Tries to find .env walking up from CWD
print(f"Path found by find_dotenv(): {dotenv_path}")

if dotenv_path:
    # Provide the found path explicitly to load_dotenv
    load_successful = load_dotenv(dotenv_path=dotenv_path, verbose=True) # Add verbose=True
    print(f".env load successful (explicit path): {load_successful}")
else:
    print("ERROR: find_dotenv() could not locate the .env file.")
    load_successful = False # Ensure flag is false if path not found

# --- Get the key ---
loaded_key = os.getenv("GOOGLE_API_KEY")
print(f"Value of GOOGLE_API_KEY after load_dotenv: '{loaded_key}'")

# --- Configure Google AI Client ---
GOOGLE_API_KEY = loaded_key

gemini_model = None
if not GOOGLE_API_KEY:
    print("ERROR: GOOGLE_API_KEY is None after attempting to load.")
    # Proceed without Gemini client initialization below
else:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-2.0-flash')
        print("Gemini client configured and model initialized.")
    except google_exceptions.PermissionDenied as e:
         print(f"ERROR: Google API Permission Denied. Check your API key and ensure the Gemini API is enabled. Details: {e}")
         gemini_model = None
    except Exception as e:
        print(f"Error configuring Google AI client or initializing model: {e}")
        gemini_model = None


# --- Global variable to hold the chatbot instance ---
chatbot_instance = None

class ReleaseNoteChatbot:
    # __init__ remains the same (handles document processing for RETRIEVAL)
    def __init__(self, filename=None, content_bytes=None):
        self.filename = filename
        self.content_bytes = content_bytes
        self.vectorizer = None
        self.tfidf_matrix = None
        self.chunks = []
        self.processing_error = None
        self.initialized = False # Tracks if TF-IDF processing is done
        self.num_chunks = 0

        if filename and content_bytes:
            start_time = time.time()
            self._load_and_process_document() # Performs extraction, preprocessing, TF-IDF
            end_time = time.time()
            if not self.processing_error:
                 print(f"Document '{self.filename}' processed for retrieval in {end_time - start_time:.2f} seconds.")
                 self.initialized = True # Mark as ready for retrieval
            else:
                 print(f"Error processing document '{self.filename}': {self.processing_error}")
                 self.initialized = False
        else:
             self.processing_error = "Error: No file provided for processing."
             self.initialized = False

    # _load_and_process_document remains the same
    def _load_and_process_document(self):
        # ... (This code is identical to the previous RAG version) ...
        # It extracts text, preprocesses it, and creates self.chunks,
        # self.vectorizer, and self.tfidf_matrix using TF-IDF.
        print(f"Processing document for retrieval: {self.filename}")
        raw_text = extract_text(self.filename, self.content_bytes)
        if isinstance(raw_text, str) and raw_text.startswith("Error:"):
            self.processing_error = raw_text; return
        if not raw_text:
            self.processing_error = "Error: Could not extract text."; return

        print("Preprocessing text...")
        self.chunks = preprocess_text(raw_text)
        self.num_chunks = len(self.chunks)
        if not self.chunks:
            self.processing_error = "Error: No meaningful text chunks found."; return

        print(f"Found {self.num_chunks} chunks. Vectorizing with TF-IDF...")
        try:
            self.vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2), max_df=0.90, min_df=2)
            self.tfidf_matrix = self.vectorizer.fit_transform(self.chunks)
            if self.tfidf_matrix.shape[0] == 0 or self.tfidf_matrix.shape[1] == 0:
                 self.processing_error = "Error: Could not vectorize content effectively."; return
            print(f"TF-IDF Vectorization complete. Matrix shape: {self.tfidf_matrix.shape}")
            self.processing_error = None
        except Exception as e:
             print(f"Error during TF-IDF vectorization: {e}")
             self.processing_error = f"Error during vectorization: {e}"


    # get_answer uses Gemini for the GENERATION step
    def get_answer(self, question, similarity_threshold=0.05, top_n=4):
        """
        Retrieves relevant chunks using TF-IDF and generates an answer using Gemini Pro.
        """
        if not self.initialized:
            return self.processing_error or "Error: Chatbot is not initialized. Please upload a valid file."
        if not self.vectorizer or self.tfidf_matrix is None:
             return "Error: Text retrieval model is not available."
        if not gemini_model: # Check if the Gemini model was initialized successfully
             return "Error: LLM client (Gemini) not initialized. Check API key and configuration."

        if not question or not question.strip():
            return "Please ask a specific question."

        print(f"RAG Step 1: Retrieving context for question: '{question[:50]}...'")
        try:
            # --- 1. Retrieve relevant chunks (Identical to previous RAG) ---
            question_vector = self.vectorizer.transform([question.strip()])
            if question_vector.nnz == 0:
                return "Your question didn't contain terms found in the document. Please rephrase."

            similarities = cosine_similarity(question_vector, self.tfidf_matrix).flatten()
            relevant_indices_above_threshold = np.where(similarities >= similarity_threshold)[0]

            if len(relevant_indices_above_threshold) == 0:
                return "Sorry, I couldn't find specific information related to your question in the document based on keywords."

            sorted_relevant_indices = relevant_indices_above_threshold[np.argsort(similarities[relevant_indices_above_threshold])[::-1]]
            top_indices = sorted_relevant_indices[:top_n]
            context_chunks = [self.chunks[i] for i in top_indices]
            context_str = "\n\n---\n\n".join(context_chunks)

            # Inside get_answer method in chatbot.py

# ... (Context retrieval code remains the same) ...
            print(f"Retrieved {len(context_chunks)} context chunks (Max Similarity: {similarities[top_indices[0]]:.4f}).")

        except Exception as e:
            # ... (Error handling for retrieval) ...

            print("RAG Step 2 & 3: Augmenting prompt and Generating answer with Gemini...")
        try:
            # --- 2. Augment prompt (REVISED FOR MORE NATURAL ANSWERS) ---

            # System-like instruction (incorporated into the main prompt for Gemini)
            instructions = f"""You are a helpful and knowledgeable assistant explaining information from the release notes for '{self.filename}'.
Your goal is to answer the user's question clearly and comprehensively, based *strictly* on the provided context snippets below.

Instructions for answering:
- Analyze the user's question and the provided context carefully.
- Synthesize information if multiple context snippets are relevant to the question. Do not just list snippets.
- Explain the answer in a natural, conversational, and easy-to-understand way. Elaborate slightly where helpful, but stay factual.
- Use formatting like bullet points or numbered lists if it makes the answer clearer (e.g., for listing features or known issues).
- Do *not* invent information or use any knowledge outside the provided context. Stick strictly to the text given.
- If the provided context definitively does not contain the information needed to answer the question, state that clearly and politely (e.g., "Based on the provided sections of the release notes, I couldn't find specific details about X.").
- Avoid phrases like "Based on the context provided..." in your final answer unless absolutely necessary for clarity. Answer as if you are simply relaying the relevant information from the document.
"""

            # Construct the final prompt for Gemini
            prompt = f"""{instructions}

--- CONTEXT START ---
{context_str}
--- CONTEXT END ---

User Question: {question}

Please provide a helpful and well-formatted answer based only on the context above:
Answer:"""

            print(f"Prompt sent to Gemini (first 200 chars): {prompt[:200]}...") # Log start of prompt

            # --- 3. Generate answer using Gemini API ---
            generation_config = genai.types.GenerationConfig(
                temperature=0.3,      # Keep temperature relatively low for factuality
                max_output_tokens=800 # INCREASE max tokens to allow for longer answers
            )
            # Safety settings remain the same
            safety_settings = [
                # ... (keep previous safety settings) ...
            ]

            response = gemini_model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            # ... (Rest of the response processing and exception handling remains the same) ...

            # --- Process the response ---
            # Check for safety blocks or lack of content first
            if not response.candidates:
                 block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else 'Unknown'
                 print(f"Warning: Gemini response blocked or empty. Reason: {block_reason}")
                 # Customize message based on reason if possible
                 if block_reason == 'SAFETY':
                      return "Sorry, the generated response was blocked due to safety settings."
                 else:
                     return "Sorry, the AI model could not generate a response for this question based on the context (possibly blocked or empty)."

            # Extract the text if available
            if response.text:
                generated_answer = response.text.strip()
                print(f"Gemini Generated Answer: {generated_answer[:200]}...")

                # Check if Gemini indicated answer not found (heuristic based on common phrasing)
                if "not found in the provided snippets" in generated_answer.lower() or \
                   "context does not contain" in generated_answer.lower() or \
                   "unable to answer based on the context" in generated_answer.lower():
                     print("Gemini indicated answer not found in context.")
                     return "Based on the relevant sections found in the document, I could not find a specific answer to your question."

                return generated_answer
            else:
                # This case might occur if candidates exist but have no text part
                print("Warning: Gemini response candidate found but contains no text.")
                return "Sorry, the AI model generated an empty response."


        except google_exceptions.PermissionDenied as e:
            print(f"Google API Permission Denied Error: {e}")
            return "Error: Google API key is invalid or the API is not enabled. Please check configuration."
        except google_exceptions.ResourceExhausted as e:
             print(f"Google API Rate Limit Error: {e}")
             return "Error: Google API quota or rate limit exceeded. Please try again later or check your usage limits."
        except Exception as e:
            print(f"Error during Gemini generation: {e}")
            import traceback; traceback.print_exc()
            return "Sorry, an unexpected error occurred while generating the answer using the AI model."


# --- Functions to manage the global chatbot instance ---
# (These remain identical to the previous RAG version)
def update_chatbot_instance(filename, content_bytes):
    global chatbot_instance
    print(f"Attempting to initialize chatbot processing for: {filename}")
    chatbot_instance = ReleaseNoteChatbot(filename=filename, content_bytes=content_bytes)
    if chatbot_instance.processing_error:
        return chatbot_instance.processing_error
    elif not chatbot_instance.initialized:
        return "Error: Chatbot initialization failed (post-processing). Check logs."
    else:
        return chatbot_instance # Return instance

def get_chatbot_instance():
    global chatbot_instance
    return chatbot_instance

def reset_chatbot_instance():
    global chatbot_instance
    chatbot_instance = None
    print("Chatbot instance reset.")