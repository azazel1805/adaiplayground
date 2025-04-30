document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    // --- Tab Switching Logic ---
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Deactivate all tabs and content
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // Activate clicked tab and corresponding content
            tab.classList.add('active');
            const targetTab = tab.getAttribute('data-tab');
            document.getElementById(targetTab).classList.add('active');
        });
    });

    // --- API Call Helper ---
    async function callApi(endpoint, data) {
        showLoader(data.mode); // Show specific loader
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });
            hideLoader(data.mode); // Hide loader on response

            if (!response.ok) {
                const errorData = await response.json();
                console.error('API Error Response:', errorData);
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API Call Failed:', error);
            hideLoader(data.mode); // Ensure loader hides on error
            // Display error to the user in the relevant feedback area
            displayFeedback(data.mode, `Oops! Something went wrong: ${error.message}`, 'error');
            return null; // Indicate failure
        }
    }

    // --- Loader Visibility ---
    function showLoader(mode) {
        const loaderId = getElementId(mode, 'loader');
        const loader = document.getElementById(loaderId);
        if (loader) loader.style.display = 'block';
        disableButtons(mode, true); // Disable buttons while loading
    }

    function hideLoader(mode) {
        const loaderId = getElementId(mode, 'loader');
        const loader = document.getElementById(loaderId);
        if (loader) loader.style.display = 'none';
        // Re-enable buttons based on current game state (handled within specific game logic)
        // For simplicity, we might just re-enable relevant buttons, or better, check state.
        // Example: disableButtons(mode, false);
    }

    // --- Button Disabling/Enabling ---
    function disableButtons(mode, disabled) {
        const gameContainer = document.getElementById(mode);
        if (!gameContainer) return;
        const buttons = gameContainer.querySelectorAll('button');
        buttons.forEach(button => button.disabled = disabled);
        const inputs = gameContainer.querySelectorAll('input, textarea');
         inputs.forEach(input => input.disabled = disabled);
    }

     // --- Helper to get element IDs based on mode ---
     function getElementId(mode, elementSuffix) {
        // Simple mapping based on convention used in HTML
        const prefixes = {
            'grim-fill': 'fill',
            'story-weaver': 'story',
            'story-weaver-start': 'story',
            'story-weaver-continue': 'story',
            'odd-situations': 'situation',
            'odd-situation': 'situation', // Alias for consistency
            'odd-situation-feedback': 'situation',
        };
        const prefix = prefixes[mode.split('-feedback')[0].split('-continue')[0].split('-start')[0]] || mode; // Handle variations
        return `${prefix}-${elementSuffix}`;
    }

    // --- Display Feedback ---
    function displayFeedback(mode, message, type = 'info') { // type: 'info', 'correct', 'incorrect', 'error'
        const feedbackAreaId = getElementId(mode, 'feedback');
        const feedbackArea = document.getElementById(feedbackAreaId);
        if (feedbackArea) {
            feedbackArea.textContent = message;
            feedbackArea.className = `feedback-area ${type}`; // Apply styling class
            feedbackArea.style.display = 'block'; // Ensure it's visible
        } else {
            console.warn(`Feedback area not found for mode: ${mode} (tried ID: ${feedbackAreaId})`);
        }
    }
     // --- Clear Feedback ---
    function clearFeedback(mode) {
         const feedbackAreaId = getElementId(mode, 'feedback');
        const feedbackArea = document.getElementById(feedbackAreaId);
        if (feedbackArea) {
            feedbackArea.textContent = '';
            feedbackArea.className = 'feedback-area'; // Reset class
            feedbackArea.style.display = 'none'; // Hide it
        }
    }


    // ==============================
    // --- Grim Fill-Ins Logic ---
    // ==============================
    const fillSentenceEl = document.getElementById('fill-sentence');
    const fillInputEl = document.getElementById('fill-input');
    const fillSubmitBtn = document.getElementById('fill-submit');
    const fillNewBtn = document.getElementById('fill-new');
    let currentCorrectWord = ''; // Store the correct word for the current sentence

    fillNewBtn.addEventListener('click', async () => {
        clearFeedback('grim-fill');
        fillSentenceEl.textContent = ''; // Clear previous sentence
        fillInputEl.value = '';
        fillInputEl.disabled = true;
        fillSubmitBtn.disabled = true;

        const data = await callApi('/api/generate', { mode: 'grim-fill' });

        // Re-enable buttons after API call completes (even if error)
        disableButtons('grim-fill', false);

        if (data && data.sentence && !data.error) {
            fillSentenceEl.textContent = data.sentence;
            currentCorrectWord = data.correct_word.toLowerCase(); // Store correct word (case-insensitive check)
            fillInputEl.disabled = false;
            fillSubmitBtn.disabled = false;
            fillInputEl.focus();
            fillSentenceEl.classList.remove('placeholder');
        } else if (data && data.error) {
             fillSentenceEl.textContent = 'Could not load sentence. Try again?';
             fillSentenceEl.classList.add('placeholder');
             displayFeedback('grim-fill', `Error: ${data.error}`, 'error');
             // Ensure buttons are appropriately enabled/disabled
             fillInputEl.disabled = true;
             fillSubmitBtn.disabled = true;
             fillNewBtn.disabled = false; // Allow user to try again
        } else {
            fillSentenceEl.textContent = 'Could not load sentence. Try again?';
            fillSentenceEl.classList.add('placeholder');
             // Ensure buttons are appropriately enabled/disabled
            fillInputEl.disabled = true;
            fillSubmitBtn.disabled = true;
            fillNewBtn.disabled = false; // Allow user to try again
        }
    });

    fillSubmitBtn.addEventListener('click', () => {
        const userAnswer = fillInputEl.value.trim().toLowerCase();
        if (!userAnswer) {
            displayFeedback('grim-fill', 'Please enter a word!', 'error');
            return;
        }

        if (userAnswer === currentCorrectWord) {
            displayFeedback('grim-fill', `Correct! "${currentCorrectWord}" fits perfectly morbidly.`, 'correct');
        } else {
            displayFeedback('grim-fill', `Not quite... The word I envisioned was "${currentCorrectWord}". Yours was... interesting though.`, 'incorrect');
        }
        // Disable input/submit after checking, encourage getting a new sentence
        fillInputEl.disabled = true;
        fillSubmitBtn.disabled = true;
    });

     // Allow pressing Enter in the input field to submit
    fillInputEl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !fillSubmitBtn.disabled) {
            fillSubmitBtn.click();
        }
    });


    // ==============================
    // --- Story Weaver Logic ---
    // ==============================
    const storyDisplayEl = document.getElementById('story-display');
    const storyInputEl = document.getElementById('story-input');
    const storySubmitBtn = document.getElementById('story-submit');
    const storyStartBtn = document.getElementById('story-start');
    let storyHistory = ''; // Keep track of the full story client-side

    storyStartBtn.addEventListener('click', async () => {
        clearFeedback('story-weaver');
        storyDisplayEl.textContent = ''; // Clear previous story
        storyDisplayEl.classList.add('placeholder');
        storyInputEl.value = '';
        storyInputEl.disabled = true;
        storySubmitBtn.disabled = true;
        storyHistory = ''; // Reset history

        const data = await callApi('/api/generate', { mode: 'story-weaver-start' });
        disableButtons('story-weaver', false); // Re-enable buttons

         if (data && data.story && !data.error) {
            storyHistory = data.story;
            storyDisplayEl.textContent = storyHistory;
            storyDisplayEl.classList.remove('placeholder');
            storyInputEl.disabled = false;
            storySubmitBtn.disabled = false;
            storyInputEl.focus();
        } else if (data && data.error) {
             storyDisplayEl.textContent = 'The muse is silent. Cannot start story.';
             displayFeedback('story-weaver', `Error: ${data.error}`, 'error');
             storyStartBtn.disabled = false; // Allow retry
        } else {
            storyDisplayEl.textContent = 'The muse is silent. Cannot start story.';
            storyStartBtn.disabled = false; // Allow retry
        }
    });

    storySubmitBtn.addEventListener('click', async () => {
        const userAddition = storyInputEl.value.trim();
        if (!userAddition) {
            displayFeedback('story-weaver', 'Don\'t be shy, add your twist to the tale!', 'error');
            return;
        }
         clearFeedback('story-weaver'); // Clear previous feedback

        // Append user input visually immediately (optional, gives faster feedback)
        const fullStoryBeforeAI = storyHistory + '\n\n' + userAddition;
        // storyDisplayEl.textContent = fullStoryBeforeAI; // Update display optimistically
        // storyInputEl.value = ''; // Clear input

        // Disable input while waiting for AI
        storyInputEl.disabled = true;
        storySubmitBtn.disabled = true;


        const data = await callApi('/api/generate', {
            mode: 'story-weaver-continue',
            input: userAddition,
            context: { history: storyHistory } // Send current history
        });

        // Re-enable input/button regardless of success/failure
        storyInputEl.disabled = false;
        storySubmitBtn.disabled = false;
        storyInputEl.value = ''; // Clear input after successful processing or error

        if (data && data.continuation && !data.error) {
            const aiContinuation = data.continuation;
            // Update history: Original + User's part + AI's part
            storyHistory = fullStoryBeforeAI + '\n\n' + aiContinuation;
            storyDisplayEl.textContent = storyHistory; // Update display with AI part
            storyInputEl.focus();
            // Scroll to bottom of story display
            storyDisplayEl.scrollTop = storyDisplayEl.scrollHeight;

        } else if (data && data.error) {
            // Revert optimistic update if needed, or just show error
            // storyDisplayEl.textContent = storyHistory; // Revert display to before user input
            displayFeedback('story-weaver', `The story stumbled: ${data.error}`, 'error');
             storyInputEl.focus(); // Allow user to try again
        } else {
             displayFeedback('story-weaver', 'The AI seems lost for words...', 'error');
              storyInputEl.focus(); // Allow user to try again
        }


    });


    // ==============================
    // --- Odd Situations Logic ---
    // ==============================
    const situationDisplayEl = document.getElementById('situation-display');
    const situationInputEl = document.getElementById('situation-input');
    const situationSubmitBtn = document.getElementById('situation-submit');
    const situationNewBtn = document.getElementById('situation-new');
    let currentSituation = ''; // Store current situation for feedback context

    situationNewBtn.addEventListener('click', async () => {
        clearFeedback('odd-situations');
        situationDisplayEl.textContent = '';
        situationDisplayEl.classList.add('placeholder');
        situationInputEl.value = '';
        situationInputEl.disabled = true;
        situationSubmitBtn.disabled = true;
        currentSituation = ''; // Reset situation

        const data = await callApi('/api/generate', { mode: 'odd-situation' });
         disableButtons('odd-situations', false); // Re-enable buttons

        if (data && data.situation && !data.error) {
            currentSituation = data.situation;
            situationDisplayEl.textContent = currentSituation;
            situationDisplayEl.classList.remove('placeholder');
            situationInputEl.disabled = false;
            situationSubmitBtn.disabled = false;
            situationInputEl.focus();
        } else if (data && data.error) {
             situationDisplayEl.textContent = 'The universe refuses to get weird right now.';
             displayFeedback('odd-situations', `Error: ${data.error}`, 'error');
             situationNewBtn.disabled = false; // Allow retry
        } else {
            situationDisplayEl.textContent = 'The universe refuses to get weird right now.';
            situationNewBtn.disabled = false; // Allow retry
        }
    });

    situationSubmitBtn.addEventListener('click', async () => {
        const userReaction = situationInputEl.value.trim();
        if (!userReaction) {
             displayFeedback('odd-situations', 'Don\'t just stand there, react!', 'error');
            return;
        }
         clearFeedback('odd-situations');

        // Disable input/button while getting feedback
        situationInputEl.disabled = true;
        situationSubmitBtn.disabled = true;

        const data = await callApi('/api/generate', {
            mode: 'odd-situation-feedback',
            input: userReaction,
            context: { situation: currentSituation }
        });

         // Re-enable components after feedback
         situationInputEl.disabled = false;
         // situationSubmitBtn.disabled = false; // Keep submit disabled until new situation? Or allow resubmit? Let's disable.
         situationNewBtn.disabled = false; // Always allow getting a new situation


        if (data && data.feedback && !data.error) {
            displayFeedback('odd-situations', data.feedback, 'info'); // Use 'info' style for AI feedback
             situationInputEl.focus(); // Let user review feedback and maybe get new situation
        } else if (data && data.error) {
             displayFeedback('odd-situations', `Feedback system glitch: ${data.error}`, 'error');
              situationInputEl.focus();
        } else {
             displayFeedback('odd-situations', 'My feedback circuits are down...', 'error');
              situationInputEl.focus();
        }
    });

}); // End DOMContentLoaded