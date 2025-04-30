// --- Service Worker Registration ---
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('Service Worker registered successfully with scope:', registration.scope);
            })
            .catch(error => {
                console.error('Service Worker registration failed:', error);
            });
    });
} else {
    console.log('Service Worker is not supported by this browser.');
}

// --- PWA Install Prompt Handling ---
let deferredPrompt;
const installButton = document.getElementById('installButton');

window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent the mini-infobar from appearing on mobile
    e.preventDefault();
    // Stash the event so it can be triggered later.
    deferredPrompt = e;
    // Update UI notify the user they can install the PWA
    if (installButton) {
        installButton.style.display = 'block'; // Show the button
        console.log('`beforeinstallprompt` event fired.');
    } else {
        console.warn('Install button not found in the DOM.');
    }


    installButton.addEventListener('click', (e) => {
        // Hide the install button
        installButton.style.display = 'none';
        // Show the install prompt
        deferredPrompt.prompt();
        // Wait for the user to respond to the prompt
        deferredPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === 'accepted') {
                console.log('User accepted the install prompt');
            } else {
                console.log('User dismissed the install prompt');
            }
            deferredPrompt = null; // We can only use the prompt once.
        });
    });
});

window.addEventListener('appinstalled', (evt) => {
    console.log('ADAI Playground was installed.');
    // Optionally hide the install button permanently or give feedback
    if (installButton) installButton.style.display = 'none';
});