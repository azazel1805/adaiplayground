import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
import logging
import json # Keep json import

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Logging
# Use INFO level for general flow, DEBUG for more detail if needed
# Output logs to console (stderr by default)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if not API_KEY:
    logging.error("Gemini API Key not found. Please set the GEMINI_API_KEY environment variable.")
    # Exit or handle gracefully - exiting is safer if key is mandatory
    # exit("Exiting: Gemini API Key not found.")
    # For now, we'll let it potentially fail later during API call but log error

# Configure Gemini
model = None # Initialize model as None
try:
    if API_KEY: # Only configure if key exists
        genai.configure(api_key=API_KEY)
        # Using gemini-1.5-flash as requested
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            generation_config={"temperature": 0.8, "top_p": 0.9} # Adjust for creativity
        )
        logging.info("Gemini model configured successfully.")
    else:
         # Already logged the error above
         pass # model remains None
except Exception as e:
    logging.error(f"Error configuring Gemini: {e}", exc_info=True)
    # model remains None

chat_sessions = {} # Simple chat history store (consider more robust session handling for production)

# --- Flask App ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) # For potential session management later

# --- Helper Function: Call Gemini ---
def call_gemini(prompt_text, safety_level='BLOCK_MEDIUM_AND_ABOVE'):
    """Calls the Gemini API. Returns the text content on success,
       or an error string starting with 'Error:' on failure."""
    if not model:
        # This case should ideally be prevented by checking model before calling,
        # but handle it defensively.
        logging.error("call_gemini attempted but model is not configured.")
        return "Error: AI model is not available. Configuration failed or API key missing."
    if not API_KEY: # Redundant check if model config fails, but good safety net
        return "Error: Gemini API Key is missing."

    try:
        # Define safety settings - adjust as needed
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": safety_level},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": safety_level},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": safety_level},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": safety_level},
        ]

        logging.info("Sending prompt to Gemini...")
        # logging.debug(f"Prompt: {prompt_text[:200]}...") # Log beginning of prompt if needed

        response = model.generate_content(
            prompt_text,
            safety_settings=safety_settings
        )

        logging.info("Received response from Gemini.")
        # More detailed check on response structure
        # logging.debug(f"Gemini Raw Response: {response}")

        # Check for blocking via prompt_feedback first (new recommended way)
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason_str = response.prompt_feedback.block_reason.name
            safety_ratings_str = ", ".join([f"{rating.category.name}: {rating.probability.name}" for rating in response.prompt_feedback.safety_ratings])
            logging.warning(f"Gemini content blocked. Reason: {block_reason_str}. Ratings: {safety_ratings_str}")
            # Return a user-friendly, but clearly identifiable error string
            return f"Error: Content blocked by AI safety filters ({block_reason_str}). Let's try a different angle."

        # If not blocked, check if parts exist and have text
        if response.parts:
             # Accessing .text should be safe now if not blocked and parts exist
             response_text = response.text.strip()
             if response_text:
                # logging.debug(f"Gemini Response Text: {response_text[:200]}...")
                return response_text
             else:
                logging.warning("Gemini returned parts but text is empty.")
                return "Error: AI returned empty content despite success status."
        else:
            # Handle cases where response generation might fail silently or return empty
            # This might indicate an issue not caught by prompt_feedback (less common)
            logging.warning(f"Gemini returned no content parts. Full response: {response}")
            return "Error: AI returned no content. Perhaps ask again?"

    except Exception as e:
        logging.error(f"Gemini API call failed: {e}", exc_info=True) # Add exc_info for full traceback
        if "API_KEY_INVALID" in str(e):
             return "Error: Invalid Gemini API Key. Please check your .env file."
        # Return a generic error string
        return f"Error: Could not reach the AI ({type(e).__name__}). Check server logs."


# --- Routes ---
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
    return send_from_directory('.', 'sw.js', mimetype='application/javascript')

@app.route('/offline.html')
def offline():
    """Serves the offline fallback page."""
    return send_from_directory('static', 'offline.html')

# Route for static files (CSS, JS, Images) - Ensure this exists
# Note: Flask's default static handling usually works if 'static' folder is present
# This explicit route can be helpful for clarity or specific configurations.
@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serves static files (CSS, JS, Images)."""
    return send_from_directory('static', filename)


# --- API Endpoint for Games ---
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
        # Log potentially long responses carefully in production
        log_content = ai_response_raw[:500] + ('...' if len(ai_response_raw) > 500 else '')
        logging.info(f"Content Snippet: '{log_content}'") # Log beginning of actual string
        logging.info(f"--- End Raw AI Response ---")

        # Check for error string BEFORE parsing
        if isinstance(ai_response_raw, str) and ai_response_raw.startswith("Error:"):
             logging.error(f"Error received directly from call_gemini for grim-fill: {ai_response_raw}")
             # Determine status code based on error type
             status_code = 400 if "blocked" in ai_response_raw.lower() else 500
             return jsonify({'error': ai_response_raw}), status_code

        # Proceed with parsing only if it's not an error string
        try:
            # Use strict=False potentially? No, better to enforce strict JSON from AI.
            ai_response = json.loads(ai_response_raw)

            # Validate the parsed structure
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

            # If validation passes
            result = {'sentence': sentence, 'correct_word': word}
            # Success - will be returned at the end

        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from Gemini for grim-fill. Raw response was: '{ai_response_raw}'", exc_info=True)
            result = {'error': 'AI response was not in the expected JSON format. Check server logs.', 'raw_response_snippet': ai_response_raw[:200]} # Include snippet for client debug
            return jsonify(result), 500 # Internal Server Error status
        except ValueError as e: # Catch our custom validation error
             logging.error(f"JSON structure validation failed: {e}. Parsed: {ai_response}", exc_info=True)
             result = {'error': f'AI response validation failed: {e}'}
             return jsonify(result), 500
        except Exception as e: # Catch other potential errors during processing
             logging.error(f"Error processing grim-fill response after potentially parsing: {e}", exc_info=True)
             result = {'error': f'An unexpected server error occurred: {e}'}
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
             return jsonify({'error': 'Missing story history or user input.'}), 400 # Bad Request

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
            return jsonify({'error': 'Missing situation context or user reaction.'}), 400 # Bad Request

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

    # If we successfully generated content for a valid game mode and didn't return early with an error
    logging.info(f"Successfully generated content for mode: {game_mode}")
    return jsonify(result)

# --- Run the App ---
if __name__ == '__main__':
    # Use 0.0.0.0 to be accessible on the network
    # Set debug=False for production, True for development
    # Use environment variable for port if available (common for deployment platforms)
    port = int(os.environ.get('PORT', 5000))
    # Set debug based on an environment variable or default to False for safety
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
