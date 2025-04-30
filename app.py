import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
import logging
import json
import re # Import regex module

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if not API_KEY:
    logging.error("Gemini API Key not found. Please set the GEMINI_API_KEY environment variable.")
    # Consider exiting if API key is mandatory for the app to function
    # exit("Exiting: Gemini API Key not found.")

# Configure Gemini
model = None # Initialize model as None
try:
    if API_KEY: # Only configure if key exists
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            # Slightly increased temp/p for creativity in grim-fill prompt
            generation_config={"temperature": 0.85, "top_p": 0.95}
        )
        logging.info("Gemini model configured successfully.")
    else:
         logging.warning("GEMINI_API_KEY not found in environment. AI features will be disabled.")
         # model remains None
except Exception as e:
    logging.error(f"Error configuring Gemini: {e}", exc_info=True)
    # model remains None

# =====================================================
# ========== CORE FLASK APP INITIALIZATION ==========
# =====================================================
# This line MUST exist and be executed before any @app.route decorators
app = Flask(__name__)
# =====================================================

# Set a secret key for session management or other security features if needed
app.config['SECRET_KEY'] = os.urandom(24)

chat_sessions = {} # Simple chat history store (replace with better session handling if needed)

# --- Helper Function: Call Gemini ---
def call_gemini(prompt_text, safety_level='BLOCK_MEDIUM_AND_ABOVE'):
    """Calls the Gemini API. Returns the text content on success,
       or an error string starting with 'Error:' on failure."""
    if not model:
        logging.error("call_gemini attempted but model is not configured.")
        return "Error: AI model is not available. Configuration failed or API key missing."
    # No need to check API_KEY again here, model check implies it was present during config attempt

    try:
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": safety_level},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": safety_level},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": safety_level},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": safety_level},
        ]
        # logging.info("Sending prompt to Gemini...") # Uncomment for verbose logging
        response = model.generate_content(
            prompt_text,
            safety_settings=safety_settings
        )
        # logging.info("Received response from Gemini.") # Uncomment for verbose logging

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason_str = response.prompt_feedback.block_reason.name
            safety_ratings_str = ", ".join([f"{rating.category.name}: {rating.probability.name}" for rating in response.prompt_feedback.safety_ratings])
            logging.warning(f"Gemini content blocked. Reason: {block_reason_str}. Ratings: {safety_ratings_str}")
            return f"Error: Content blocked by AI safety filters ({block_reason_str}). Let's try a different angle."

        if response.parts:
             response_text = response.text.strip()
             if response_text:
                return response_text
             else:
                logging.warning("Gemini returned parts but text is empty.")
                return "Error: AI returned empty content despite success status."
        else:
            logging.warning(f"Gemini returned no content parts. Full response: {response}")
            return "Error: AI returned no content. Perhaps ask again?"

    except Exception as e:
        logging.error(f"Gemini API call failed: {e}", exc_info=True)
        if "API_KEY_INVALID" in str(e):
             return "Error: Invalid Gemini API Key. Please check your .env file."
        # Provide a slightly more informative generic error
        return f"Error: Communication with AI failed ({type(e).__name__}). Check server logs."


# --- Routes ---
# These use the 'app' variable defined above
@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/manifest.json')
def serve_manifest():
    """Serves the PWA manifest file."""
    return send_from_directory('.', 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    """Serves the Service Worker file."""
    # Ensure correct MIME type for JavaScript
    return send_from_directory('.', 'sw.js', mimetype='application/javascript')

@app.route('/offline.html')
def offline():
    """Serves the offline fallback page."""
    return send_from_directory('static', 'offline.html')

# Route for static files (CSS, JS, Images)
@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serves static files from the 'static' directory."""
    return send_from_directory('static', filename)


# --- API Endpoint for Games ---
# Also uses the 'app' variable
@app.route('/api/generate', methods=['POST'])
def generate_content():
    """Handles requests for AI-generated game content."""
    if not model: # Check if model failed to initialize
        logging.error("API request received but Gemini model not available.")
        return jsonify({'error': 'AI Service is currently unavailable. Check server configuration.'}), 503 # Service Unavailable

    data = request.json
    game_mode = data.get('mode')
    user_input = data.get('input', '')
    context = data.get('context', {}) # For storing game state like story history
    logging.info(f"Received API request for mode: {game_mode}")

    prompt = ""
    result = {} # Initialize result dict for game data

    # --- Game Logic & Prompts ---
    if game_mode == 'grim-fill':
        prompt = f"""
        You are an AI assistant skilled in creating darkly humorous, absurd, and surprisingly weird sentences for intermediate English learners (B1-B2 level).
        Your goal is to generate a SINGLE, grammatically correct sentence containing EXACTLY ONE blank ('_____'). This blank should replace a SINGLE common English word (noun, verb, adjective, or adverb).
        The sentence MUST evoke dark humor, surrealism, unexpectedness, or absurdity.

        **CRITICAL INSTRUCTIONS:**
        1.  **TONE:** Aim for genuinely funny-weird, macabre-lite, ironic, or nonsensical. Think unexpected juxtapositions.
        2.  **VARIETY:** DO NOT always use the same sentence structure. Vary sentence beginnings, use different clauses, maybe even a question format sometimes. Surprise the user!
        3.  **AVOID:** Do not create boring, predictable, bland, or overly simple sentences. Avoid generic situations. If it feels plain, try again.
        4.  **BLANK:** Only ONE blank ('_____') representing ONE common English word.
        5.  **OUTPUT:** Your response MUST be ONLY a valid JSON object with keys "sentence" and "word". NO introductory text, NO explanations, NO apologies, NO markdown formatting (like ```json). Just the JSON.

        **GOOD Examples (Demonstrating Tone & Variety):**
        {{ "sentence": "My therapist suggested I embrace my inner child, so I promptly _____ it in the attic.", "word": "locked" }}
        {{ "sentence": "The polite zombie offered me a cup of tea, brewed with questionable _____.", "word": "water" }}
        {{ "sentence": "To save money on haunting costs, the ghost decided to _____ less dramatically.", "word": "materialize" }}
        {{ "sentence": "His dating profile listed 'taxidermy' and '_____ snacks' as his main hobbies.", "word": "existential" }}
        {{ "sentence": "Is it considered rude to _____ during a séance?", "word": "multitask" }}
        {{ "sentence": "The sentient toaster oven demanded _____ before making breakfast.", "word": "fealty" }}

        **BAD Examples (Too Bland / Not Weird Enough):**
        {{ "sentence": "The black cat sat on the ____.", "word": "mat" }}
        {{ "sentence": "He felt ____ after the long walk.", "word": "tired" }}
        {{ "sentence": "The house on the hill looked ____.", "word": "spooky" }}

        Generate a new sentence following these instructions precisely.
        """
        ai_response_raw = call_gemini(prompt)

        logging.info(f"--- Grim Fill Raw AI Response ---")
        logging.info(f"Type: {type(ai_response_raw)}")
        log_content = ai_response_raw[:500] + ('...' if len(ai_response_raw) > 500 else '')
        logging.info(f"Content Snippet: '{log_content}'")
        logging.info(f"--- End Raw AI Response ---")

        # Check for error string first
        if isinstance(ai_response_raw, str) and ai_response_raw.startswith("Error:"):
             logging.error(f"Error received directly from call_gemini for grim-fill: {ai_response_raw}")
             status_code = 400 if "blocked" in ai_response_raw.lower() else 500
             return jsonify({'error': ai_response_raw}), status_code

        # Extract JSON using Regex
        json_string = None
        try:
            match = re.search(r'\{.*\}', ai_response_raw, re.DOTALL)
            if match:
                json_string = match.group(0)
                logging.info(f"Extracted JSON string snippet: {json_string[:200]}...")
            else:
                logging.error(f"Could not find JSON block in AI response for grim-fill. Raw: '{ai_response_raw}'")
                return jsonify({'error': 'AI response did not contain a recognizable JSON block.'}), 500

            # Parse the extracted string
            ai_response = json.loads(json_string)

            # Validation
            if not isinstance(ai_response, dict):
                 raise ValueError("Parsed response is not a dictionary.")
            sentence = ai_response.get('sentence')
            word = ai_response.get('word')
            if not sentence or not isinstance(sentence, str):
                 logging.error(f"Parsed JSON missing or invalid 'sentence'. Parsed: {ai_response}")
                 result = {'error': 'AI response missing or invalid sentence data.'}
                 return jsonify(result), 500
            if not word or not isinstance(word, str):
                 logging.error(f"Parsed JSON missing or invalid 'word'. Parsed: {ai_response}")
                 result = {'error': 'AI response missing or invalid word data.'}
                 return jsonify(result), 500
            # Success
            result = {'sentence': sentence, 'correct_word': word}

        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse EXTRACTED JSON from Gemini for grim-fill. Extracted: '{json_string}'. Original Raw: '{ai_response_raw}'. Error: {e}", exc_info=True)
            result = {'error': 'AI response contained malformed JSON. Check server logs.', 'raw_response_snippet': ai_response_raw[:200]}
            return jsonify(result), 500
        except ValueError as e:
             logging.error(f"JSON structure validation failed: {e}. Parsed: {ai_response}", exc_info=True)
             result = {'error': f'AI response validation failed: {e}'}
             return jsonify(result), 500
        except Exception as e:
             logging.error(f"Error processing grim-fill response after extraction/parsing: {e}", exc_info=True)
             result = {'error': f'An unexpected server error occurred during processing: {e}'}
             return jsonify(result), 500

    elif game_mode == 'story-weaver-start':
        prompt = """
        Start a short story (1-2 sentences) with a dark humor, mysterious, or funny-weird tone suitable for an intermediate English learner (B1-B2 level).
        Keep it intriguing and open-ended. Output only the story starting sentences, no extra text.
        """
        story_start = call_gemini(prompt)
        if story_start.startswith("Error:"):
             logging.error(f"Error getting story start: {story_start}")
             status_code = 400 if "blocked" in story_start.lower() else 500
             return jsonify({'error': story_start}), status_code
        result = {'story': story_start}

    elif game_mode == 'story-weaver-continue':
        story_history = context.get('history', '')
        user_addition = user_input
        if not story_history or not user_addition:
             logging.warning("Story weaver continue called with missing history or input.")
             return jsonify({'error': 'Missing story history or user input.'}), 400
        prompt = f"""
        You are a collaborative storyteller with a dark humor, mysterious, or funny-weird style.
        Continue the following story. The last part was added by the user. Add 1-2 sentences that logically follow, maintain the tone, and keep the story engaging for an intermediate English learner.
        Ensure grammatical correctness and flow. Output ONLY the next part of the story, no extra text.

        Story So Far:
        {story_history}

        User added:
        {user_addition}

        Your continuation:
        """
        continuation = call_gemini(prompt)
        if continuation.startswith("Error:"):
             logging.error(f"Error continuing story: {continuation}")
             status_code = 400 if "blocked" in continuation.lower() else 500
             return jsonify({'error': continuation}), status_code
        result = {'continuation': continuation}

    elif game_mode == 'odd-situation':
        prompt = """
        Describe a brief (1-2 sentence) hypothetical situation that is strange, has dark humor, or is absurdly funny.
        This is for an intermediate English learner (B1-B2) to react to. Make it thought-provoking or amusing.
        Output ONLY the situation description, no extra text.

        Example: You open your fridge and find a single, sentient sock tap-dancing on the cheese. It demands better life choices from you.
        """
        situation = call_gemini(prompt)
        if situation.startswith("Error:"):
             logging.error(f"Error getting odd situation: {situation}")
             status_code = 400 if "blocked" in situation.lower() else 500
             return jsonify({'error': situation}), status_code
        result = {'situation': situation}

    elif game_mode == 'odd-situation-feedback':
        situation_context = context.get('situation', '')
        user_reaction = user_input
        if not situation_context or not user_reaction:
            logging.warning("Odd situation feedback called with missing context or reaction.")
            return jsonify({'error': 'Missing situation context or user reaction.'}), 400
        prompt = f"""
        An intermediate English learner was presented with this situation:
        "{situation_context}"

        They responded:
        "{user_reaction}"

        Provide brief (1-3 sentences), constructive, and slightly quirky/dark-humored feedback on their response.
        Focus on:
        1. Clarity and grammar (mention one specific point if needed, gently).
        2. How well their response fits the odd/funny/dark tone of the situation.
        3. Keep the feedback encouraging but in character (a slightly eccentric AI).
        Output ONLY the feedback, no extra text.
        """
        feedback = call_gemini(prompt)
        if feedback.startswith("Error:"):
             logging.error(f"Error getting situation feedback: {feedback}")
             status_code = 400 if "blocked" in feedback.lower() else 500
             return jsonify({'error': feedback}), status_code
        result = {'feedback': feedback}

    else:
        logging.warning(f"Invalid game mode requested: {game_mode}")
        return jsonify({'error': 'Invalid game mode'}), 400 # Bad Request

    # Final Success Return
    logging.info(f"Successfully generated content for mode: {game_mode}")
    return jsonify(result)

# --- Run the App ---
# This also needs the 'app' variable defined earlier
if __name__ == '__main__':
    # Use environment variable for port if available (common for deployment)
    port = int(os.environ.get('PORT', 5000))
    # Set debug based on environment variable (safer for production)
    # Default to False if FLASK_DEBUG is not set or not 'true'
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    # Run on 0.0.0.0 to be accessible on the network
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
