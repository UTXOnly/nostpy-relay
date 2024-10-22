// Wait for the DOM to fully load before attaching event listeners
document.addEventListener("DOMContentLoaded", function() {
    const createEventButton = document.getElementById('createEventButton');

    // Check if the button exists before trying to add the event listener
    if (createEventButton) {
        // Add event listener for Create and Sign Event button
        createEventButton.addEventListener('click', async () => {
            try {
                // Get selected method and user inputs
                const method = document.getElementById('method').value;
                const pubkey = document.getElementById('pubkey').value;
                const kind = document.getElementById('kind').value;
                const reason = document.getElementById('reason').value;
                const ip = document.getElementById('ip').value;
                const id = document.getElementById('id').value;

                // Fetch the public key using the extension
                const publicKey = await window.nostr.getPublicKey();

                // Build the request body based on the selected method and fields
                let params = [];
                switch (method) {
                    case 'banpubkey':
                    case 'allowpubkey':
                        params.push(pubkey);
                        if (reason) params.push(reason);
                        break;
                    case 'banevent':
                    case 'allowevent':
                        params.push(id);
                        if (reason) params.push(reason);
                        break;
                    case 'changerelayname':
                    case 'changerelaydescription':
                    case 'changerelayicon':
                        params.push(reason);
                        break;
                    case 'allowkind':
                    case 'disallowkind':
                        params.push(kind);
                        break;
                    case 'blockip':
                    case 'unblockip':
                        params.push(ip);
                        if (reason) params.push(reason);
                        break;
                }

                const requestBody = {
                    method: method,
                    params: params
                };
                const requestBodyString = JSON.stringify(requestBody);

                // Calculate the SHA-256 hash of the request body
                const encoder = new TextEncoder();
                const requestBodyHashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(requestBodyString));
                const hashArray = Array.from(new Uint8Array(requestBodyHashBuffer));
                const requestBodyHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

                // Define the event object you want to sign
                const event = {
                    pubkey: publicKey,
                    kind: 27235,
                    created_at: Math.floor(Date.now() / 1000),
                    tags: [
                        ["u", "http://172.17.0.1:8000/nip86"],
                        ["method", "POST"],
                        ["payload", requestBodyHash]
                    ],
                    content: ""
                };

                // Sign the event using the browser extension
                const signedEvent = await window.nostr.signEvent(event);

                // Convert the signed event to base64
                const eventBase64 = btoa(JSON.stringify(signedEvent));

                // Send the POST request to the endpoint
                const response = await fetch('/nip86', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Nostr ${eventBase64}`,
                        'Content-Type': 'application/nostr+json+rpc'
                    },
                    body: requestBodyString
                });

                // Parse and display the response from the server
                const responseData = await response.json();
                console.debug("Server Response:", responseData.result);
                displayResults(responseData);

            } catch (err) {
                console.error('Error creating or signing event:', err);
            }
        });
    } else {
        console.error('Create and Sign Event button not found in the DOM');
    }
});

// Function to show/hide fields based on method selection
function handleMethodChange() {
    const method = document.getElementById('method').value;
    const pubkeyField = document.getElementById('pubkeyField');
    const kindField = document.getElementById('kindField');
    const reasonField = document.getElementById('reasonField');
    const ipField = document.getElementById('ipField');
    const idField = document.getElementById('idField');

    // Reset fields visibility
    pubkeyField.classList.add('hidden');
    kindField.classList.add('hidden');
    reasonField.classList.add('hidden');
    ipField.classList.add('hidden');
    idField.classList.add('hidden');

    // Show the appropriate fields based on the selected method
    switch (method) {
        case 'banpubkey':
        case 'allowpubkey':
            pubkeyField.classList.remove('hidden');
            reasonField.classList.remove('hidden');
            break;
        case 'banevent':
        case 'allowevent':
            idField.classList.remove('hidden');
            reasonField.classList.remove('hidden');
            break;
        case 'changerelayname':
        case 'changerelaydescription':
        case 'changerelayicon':
            reasonField.classList.remove('hidden');
            break;
        case 'allowkind':
        case 'disallowkind':
            kindField.classList.remove('hidden');
            break;
        case 'blockip':
            ipField.classList.remove('hidden');
            reasonField.classList.remove('hidden');
            break;
        case 'unblockip':
            ipField.classList.remove('hidden');
            break;
        default:
            break;
    }
}

// Initialize the form to show the appropriate fields when the page loads
handleMethodChange();
