# utils.py
import re
import io
import docx
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.layout import LAParams

# Optional NLTK
# from nltk.corpus import stopwords
# from nltk.tokenize import word_tokenize
# STOP_WORDS = set(stopwords.words('english'))

# --- PDF Extraction using pdfminer.six ---
def extract_text_from_pdf_content_pdfminer(content_bytes):
    """Extracts text from PDF content bytes using pdfminer.six."""
    try:
        # Use BytesIO to treat bytes as a file
        pdf_file = io.BytesIO(content_bytes)
        # Extract text using pdfminer.six. LAParams can be tuned for layout analysis.
        # Adding LAParams() can sometimes improve spacing/layout detection.
        text = pdfminer_extract_text(pdf_file, laparams=LAParams())
        # Basic check for empty result which pdfminer might return for image-only PDFs
        if not text.strip():
             print("Warning: pdfminer.six extracted empty text. PDF might be image-based or unreadable.")
             # Optionally, try OCR here if needed, but that's a bigger step.
             return "Error: Failed to extract text content (document might be image-based)."
        return text
    except Exception as e:
        print(f"Error reading PDF content with pdfminer.six: {e}")
        # Provide more specific feedback if possible
        if "incorrect password" in str(e).lower():
            return "Error: PDF is password protected and could not be opened."
        if "Trailer is not found" in str(e) or "Invalid" in str(e):
             return "Error: Invalid or corrupted PDF file format."
        return f"Error: Failed to process PDF content with pdfminer ({e})."

# --- DOCX and TXT Extraction (Keep as before) ---
def extract_text_from_docx_content(content_bytes):
    """Extracts text from DOCX content bytes."""
    text = ""
    try:
        docx_file = io.BytesIO(content_bytes)
        doc = docx.Document(docx_file)
        for para in doc.paragraphs:
            # Add space between paragraphs for better splitting later
            text += para.text + "\n\n" # Use double newline as paragraph separator
    except Exception as e:
        print(f"Error reading DOCX content: {e}")
        if "File is not a zip file" in str(e):
             return "Error: Invalid DOCX file format. Make sure it's a valid .docx file."
        return "Error: Failed to process DOCX content."
    return text

def extract_text_from_txt_content(content_bytes):
    """Extracts text from TXT content bytes, trying common encodings."""
    text = None
    encodings_to_try = ['utf-8', 'latin-1', 'cp1252']
    for encoding in encodings_to_try:
        try:
            text = content_bytes.decode(encoding)
            print(f"Successfully decoded TXT with {encoding}")
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
             print(f"Unexpected error decoding TXT with {encoding}: {e}")
             return f"Error: Unexpected issue decoding TXT content ({e})."
    if text is None:
        print("Error reading TXT content: Could not decode using common encodings.")
        return "Error: Could not decode TXT content. File might use an unsupported encoding."
    return text

# --- Main Extraction Function ---
def extract_text(filename, content_bytes):
    """Extracts text from PDF, DOCX, or TXT file content bytes."""
    lower_filename = filename.lower()
    extracted_text = None
    print(f"Attempting to extract text from: {filename}")
    if lower_filename.endswith(".pdf"):
        extracted_text = extract_text_from_pdf_content_pdfminer(content_bytes) # USE PDFMINER
    elif lower_filename.endswith(".docx"):
        extracted_text = extract_text_from_docx_content(content_bytes)
    elif lower_filename.endswith(".txt"):
         extracted_text = extract_text_from_txt_content(content_bytes)
    else:
        print(f"Error: Unsupported file format for {filename}.")
        return "Error: Unsupported file format. Please use PDF, DOCX, or TXT."

    if isinstance(extracted_text, str) and extracted_text.startswith("Error:"):
        return extracted_text
    elif not extracted_text or not extracted_text.strip():
        # Check again after potential extraction success but empty result
        return "Error: Extracted text is empty or could not be read properly."

    print(f"Successfully extracted raw text (length: {len(extracted_text)} chars)")
    return extracted_text


# --- Enhanced Preprocessing Function ---
def preprocess_text(text):
    """Cleans and preprocesses the extracted text into meaningful chunks."""
    if not text or (isinstance(text, str) and text.startswith("Error:")):
        return []

    print("Starting preprocessing...")

    # 1. Initial coarse cleaning: Remove excessive whitespace, normalize line breaks
    text = re.sub(r'(\r\n|\r|\n){3,}', '\n\n', text) # Normalize multiple newlines to double newline (paragraph)
    text = re.sub(r'[ \t]+', ' ', text) # Replace multiple spaces/tabs with single space
    text = text.strip()

    # 2. Split into potential chunks (paragraphs are often better than sentences for context)
    #    Split by double newline first, then process each paragraph.
    paragraphs = text.split('\n\n')
    print(f"Split into {len(paragraphs)} initial paragraphs.")

    cleaned_chunks = []
    min_chunk_length_words = 5 # Minimum words for a chunk to be considered

    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue

        # print(f"Processing paragraph {i}: {para[:100]}...") # Debugging

        # 3. Finer cleaning within each paragraph:
        #    - Remove typical header/footer patterns (adjust regex as needed)
        para = re.sub(r'^\s*Page\s+\d+\s*of\s*\d+\s*$', '', para, flags=re.IGNORECASE | re.MULTILINE)
        para = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', para, flags=re.MULTILINE) # e.g., - 5 -
        #    - Remove potential list markers like "-21-" or "•" at the start (be careful not to remove intended dashes)
        para = re.sub(r'^\s*[-•*]\s*\d+[-.]?\s*', '', para) # Removes "-21-", "* 5.", "• " etc. at start
        para = re.sub(r'^\s*[•*]\s+', '', para) # Remove bullet points at start

        #    - Attempt to fix words merged without spaces (heuristic, might be imperfect)
        #      Look for lowercase followed by uppercase (common merge pattern)
        para = re.sub(r'([a-z])([A-Z])', r'\1 \2', para)

        #    - Replace excessive internal whitespace again after cleaning
        para = ' '.join(para.split()) # Normalizes all internal whitespace to single spaces

        # 4. Chunking decision: Treat cleaned paragraph as a chunk if long enough
        word_count = len(para.split())
        if word_count >= min_chunk_length_words:
            cleaned_chunks.append(para)
            # print(f"  Added chunk (words: {word_count}): {para[:100]}...") # Debugging
        # else:
            # print(f"  Skipping short paragraph (words: {word_count})") # Debugging


    if not cleaned_chunks:
        print("Warning: No meaningful chunks found after preprocessing paragraphs.")
        # Fallback: try sentence splitting on the whole text if paragraph splitting failed
        # (This uses the previous logic as a backup)
        print("Falling back to sentence splitting...")
        potential_sentences = text.split('.') # Use original text before paragraph split
        for sentence in potential_sentences:
            sentence = ' '.join(sentence.split()).strip() # Clean whitespace
            if sentence:
                 sentence = re.sub(r'^\s*[-•*]\s*\d+[-.]?\s*', '', sentence) # Basic list marker removal
                 sentence = re.sub(r'^\s*[•*]\s+', '', sentence)
                 sentence = re.sub(r'([a-z])([A-Z])', r'\1 \2', sentence) # Fix merged words
                 sentence = ' '.join(sentence.split()) # Final whitespace clean
                 if len(sentence.split()) >= min_chunk_length_words:
                     cleaned_chunks.append(sentence + '.') # Add period back for sentences

    print(f"Preprocessing finished. Found {len(cleaned_chunks)} final chunks.")
    return cleaned_chunks