import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
import logging
import json
import re # <--- IMPORT REGEX MODULE

# --- Configuration, Helper Function (call_gemini), Routes ---
# (Keep all the code from the previous version here - no changes needed above the API endpoint)
# ... (previous code for imports, config, logging, model init, call_gemini, Flask app, routes) ...

# --- API Endpoint for Games ---
@app.route('/api/generate', methods=['POST'])
def generate_content():
    # (Keep model check, data retrieval, logging info)
    if not model:
        logging.error("API request received but Gemini model not available.")
        return jsonify({'error': 'AI Service is currently unavailable. Check server configuration.'}), 503

    data = request.json
    game_mode = data.get('mode')
    user_input = data.get('input', '')
    context = data.get('context', {})
    logging.info(f"Received API request for mode: {game_mode}")

    prompt = ""
    result = {}

    # --- Game Logic & Prompts ---
    if game_mode == 'grim-fill':
        # (The complex prompt remains the same as the last version)
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

        # Check for error string first (no change here)
        if isinstance(ai_response_raw, str) and ai_response_raw.startswith("Error:"):
             logging.error(f"Error received directly from call_gemini for grim-fill: {ai_response_raw}")
             status_code = 400 if "blocked" in ai_response_raw.lower() else 500
             return jsonify({'error': ai_response_raw}), status_code

        # =====================================================
        # ========== NEW: EXTRACT JSON USING REGEX ============
        # =====================================================
        json_string = None
        try:
            # Regex to find a block starting with { and ending with }
            # re.DOTALL makes '.' match newlines as well
            match = re.search(r'\{.*\}', ai_response_raw, re.DOTALL)
            if match:
                json_string = match.group(0)
                logging.info(f"Extracted JSON string: {json_string[:200]}...") # Log extracted part
            else:
                # Log error if no JSON block is found at all
                logging.error(f"Could not find JSON block in AI response for grim-fill. Raw: '{ai_response_raw}'")
                return jsonify({'error': 'AI response did not contain a recognizable JSON block.'}), 500

            # Now, try parsing the extracted string
            ai_response = json.loads(json_string)

            # --- Validation (same as before) ---
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
            # This error now means the *extracted* string was still not valid JSON
            logging.error(f"Failed to parse EXTRACTED JSON from Gemini for grim-fill. Extracted: '{json_string}'. Original Raw: '{ai_response_raw}'. Error: {e}", exc_info=True)
            result = {'error': 'AI response contained malformed JSON. Check server logs.', 'raw_response_snippet': ai_response_raw[:200]}
            return jsonify(result), 500 # Internal Server Error status
        except ValueError as e: # Catch our custom validation error
             logging.error(f"JSON structure validation failed: {e}. Parsed: {ai_response}", exc_info=True)
             result = {'error': f'AI response validation failed: {e}'}
             return jsonify(result), 500
        except Exception as e: # Catch other potential errors during processing
             logging.error(f"Error processing grim-fill response after extraction/parsing: {e}", exc_info=True)
             result = {'error': f'An unexpected server error occurred during processing: {e}'}
             return jsonify(result), 500
        # =====================================================
        # ================ END OF JSON EXTRACTION =============
        # =====================================================

    # --- Other Game Modes ---
    # (Keep the logic for story-weaver-start, story-weaver-continue,
    # odd-situation, and odd-situation-feedback exactly the same as before)
    elif game_mode == 'story-weaver-start':
        # ... (previous code) ...
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
        # ... (previous code) ...
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
        # ... (previous code) ...
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
        # ... (previous code) ...
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
        # (Keep invalid mode handling)
        logging.warning(f"Invalid game mode requested: {game_mode}")
        return jsonify({'error': 'Invalid game mode'}), 400 # Bad Request

    # (Keep final success return)
    logging.info(f"Successfully generated content for mode: {game_mode}")
    return jsonify(result)

# --- Run the App ---
# (Keep the __main__ block the same)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
