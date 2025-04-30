import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
import logging
import json # Import json module

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    logging.error("Gemini API Key not found. Please set the GEMINI_API_KEY environment variable.")
    # You might want to exit or handle this more gracefully depending on your needs
    # For now, we'll let it potentially fail later during API call

# Configure Gemini
try:
    genai.configure(api_key=API_KEY)
    # Using gemini-1.5-flash as requested
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        generation_config={"temperature": 0.8, "top_p": 0.9} # Adjust for creativity/predictability
    )
    chat_sessions = {} # Store chat history for Story Weaver per user session (simple example)
except Exception as e:
    logging.error(f"Error configuring Gemini: {e}")
    model = None # Set model to None if configuration fails

# --- Flask App ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) # For potential session management later
logging.basicConfig(level=logging.INFO)

# --- Helper Function: Call Gemini ---
def call_gemini(prompt_text, safety_level='BLOCK_MEDIUM_AND_ABOVE'):
    """Calls the Gemini API with the provided prompt."""
    if not model:
        return "Error: Gemini model not configured. Check API Key and configuration."
    if not API_KEY:
        return "Error: Gemini API Key is missing."

    try:
        # Define safety settings - adjust as needed for the "dark" theme, but be mindful of API limits
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": safety_level},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": safety_level},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": safety_level},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": safety_level},
        ]

        response = model.generate_content(
            prompt_text,
            safety_settings=safety_settings
        )
        # Basic check if response has text - you might need more robust checks
        if response.parts:
             # Check for blocked content prompt feedback
            if response.prompt_feedbacks:
                block_reason = next((fb.block_reason for fb in response.prompt_feedbacks if fb.block_reason), None)
                if block_reason:
                    logging.warning(f"Gemini content blocked due to: {block_reason}")
                    # Provide a user-friendly message for blocked content
                    if block_reason.name == 'SAFETY':
                         # More specific handling based on safety feedback if available
                        safety_ratings = [str(rating) for rating in response.prompt_feedbacks[0].safety_ratings]
                        return f"Hmm, that direction got a bit too dark or strange, even for me! Let's try a different angle. (Blocked: Safety - {', '.join(safety_ratings)})"
                    else:
                         return f"Hmm, that direction got a bit too dark or strange, even for me! Let's try a different angle. (Blocked: {block_reason.name})"
            return response.text.strip()
        elif response.prompt_feedbacks and any(fb.block_reason for fb in response.prompt_feedbacks):
             block_reason = next((fb.block_reason for fb in response.prompt_feedbacks if fb.block_reason), "Unknown")
             logging.warning(f"Gemini prompt blocked due to: {block_reason}")
             return f"My circuits buzzed strangely with that request. Blocked. Reason: {block_reason}. Let's try something else?"
        else:
            # Handle cases where response generation might fail silently or return empty
            logging.warning(f"Gemini returned no content. Full response: {response}")
            return "My thoughts seem to have vanished... Perhaps ask again?"

    except Exception as e:
        logging.error(f"Gemini API call failed: {e}")
        # Check for specific API key errors if possible
        if "API_KEY_INVALID" in str(e):
             return "Error: Invalid Gemini API Key. Please check your .env file."
        return f"Error: Could not connect to the AI. ({type(e).__name__})"


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
    # Set correct MIME type for JavaScript
    return send_from_directory('.', 'sw.js', mimetype='application/javascript')

@app.route('/offline.html')
def offline():
    """Serves the offline fallback page."""
    return send_from_directory('static', 'offline.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serves static files (CSS, JS, Images)."""
    return send_from_directory('static', filename)


# --- API Endpoint for Games ---
@app.route('/api/generate', methods=['POST'])
def generate_content():
    """Handles requests for AI-generated game content."""
    data = request.json
    game_mode = data.get('mode')
    user_input = data.get('input', '')
    context = data.get('context', {}) # For storing game state like story history

    prompt = ""
    result = {}

    # --- Game Logic & Prompts ---
    if game_mode == 'grim-fill':
        # Generate a sentence with a blank
        prompt = f"""
        Create a single, grammatically correct sentence for an intermediate English learner (B1-B2 level) with a dark humor, slightly spooky, or absurdly funny tone.
        The sentence MUST contain exactly one blank represented by '_____' where a common English word (verb, noun, adjective, adverb) should go.
        Provide the sentence and the missing word.
        Format your response ONLY as a JSON object with keys "sentence" and "word". No other text.

        Example:
        {{
          "sentence": "The skeletal librarian insisted the overdue book fee was payable in ____.",
          "word": "souls"
        }}
        """
        ai_response_raw = call_gemini(prompt)
        try:
            # Attempt to parse the JSON response from Gemini
            ai_response = json.loads(ai_response_raw)
            result = {'sentence': ai_response.get('sentence', 'Error: Could not generate sentence.'),
                      'correct_word': ai_response.get('word', '')}
        except json.JSONDecodeError:
            logging.error(f"Failed to parse JSON from Gemini for grim-fill: {ai_response_raw}")
            result = {'error': 'AI response format error. Could not parse sentence.', 'raw_response': ai_response_raw}
        except Exception as e: # Catch other potential errors during processing
             logging.error(f"Error processing grim-fill response: {e}")
             result = {'error': f'An unexpected error occurred: {e}'}


    elif game_mode == 'story-weaver-start':
        # Start a new story
        prompt = """
        Start a short story (1-2 sentences) with a dark humor, mysterious, or funny-weird tone suitable for an intermediate English learner (B1-B2 level).
        Keep it intriguing and open-ended. Output only the story starting sentences.
        """
        story_start = call_gemini(prompt)
        result = {'story': story_start}
        # Optional: Use session ID or other mechanism for distinct user stories
        # For simplicity, we'll manage history client-side for now, but backend storage is better for real sessions

    elif game_mode == 'story-weaver-continue':
        # Continue the story based on user input and history
        story_history = context.get('history', '')
        user_addition = user_input

        if not story_history or not user_addition:
             return jsonify({'error': 'Missing story history or user input.'}), 400

        prompt = f"""
        You are a collaborative storyteller with a dark humor, mysterious, or funny-weird style.
        Continue the following story. The last part was added by the user. Add 1-2 sentences that logically follow, maintain the tone, and keep the story engaging for an intermediate English learner.
        Ensure grammatical correctness and flow. Output ONLY the next part of the story.

        Story So Far:
        {story_history}

        User added:
        {user_addition}

        Your continuation:
        """
        continuation = call_gemini(prompt)
        result = {'continuation': continuation}

    elif game_mode == 'odd-situation':
         # Generate an odd situation
        prompt = """
        Describe a brief (1-2 sentence) hypothetical situation that is strange, has dark humor, or is absurdly funny.
        This is for an intermediate English learner (B1-B2) to react to. Make it thought-provoking or amusing.
        Output ONLY the situation description.

        Example: You open your fridge and find a single, sentient sock tap-dancing on the cheese. It demands better life choices from you.
        """
        situation = call_gemini(prompt)
        result = {'situation': situation}

    elif game_mode == 'odd-situation-feedback':
         # Give feedback on the user's reaction
        situation_context = context.get('situation', '')
        user_reaction = user_input

        if not situation_context or not user_reaction:
            return jsonify({'error': 'Missing situation context or user reaction.'}), 400

        prompt = f"""
        An intermediate English learner was presented with this situation:
        "{situation_context}"

        They responded:
        "{user_reaction}"

        Provide brief (1-3 sentences), constructive, and slightly quirky/dark-humored feedback on their response.
        Focus on:
        1. Clarity and grammar (mention one specific point if needed).
        2. How well their response fits the odd/funny/dark tone of the situation.
        3. Keep the feedback encouraging but in character (a slightly eccentric AI).
        Output ONLY the feedback.
        """
        feedback = call_gemini(prompt)
        result = {'feedback': feedback}

    else:
        return jsonify({'error': 'Invalid game mode'}), 400

    # Check if the result contains an error message from call_gemini
    if isinstance(result, dict) and 'error' in result:
         # If the error came from JSON parsing or other processing
         return jsonify(result), 500 # Internal Server Error status
    elif isinstance(result, str) and result.startswith("Error:"):
         # If the error came directly from call_gemini failure
         return jsonify({'error': result}), 500
    elif isinstance(result, str) and "Blocked" in result:
         # Handle blocked content messages gracefully
         return jsonify({'error': result}), 400 # Bad Request or similar, as the content was inappropriate

    return jsonify(result)

# --- Run the App ---
if __name__ == '__main__':
    # Use 0.0.0.0 to be accessible on the network (important for testing PWA on mobile)
    # Debug=True is helpful during development, REMOVE for production
    app.run(host='0.0.0.0', port=5000, debug=True)