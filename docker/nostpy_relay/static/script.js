// Function to display results in a human-readable format
function displayResults(responseData) {
    const outputDiv = document.getElementById('output');
    const method = document.getElementById('method').value;

    // Clear previous output
    outputDiv.innerHTML = '';

    // Handle 'listbannedevents' method
    if (method === 'listbannedevents' && responseData.result && responseData.result.length > 0) {
        const listTitle = document.createElement('h2');
        listTitle.textContent = 'Banned Events:';
        outputDiv.appendChild(listTitle);

        const resultList = document.createElement('ul');
        resultList.className = 'result-list';

        responseData.result.forEach(event => {
            const listItem = document.createElement('li');
            listItem.textContent = `Event ID: ${event}`;
            resultList.appendChild(listItem);
        });

        outputDiv.appendChild(resultList);

    // Handle 'listbannedpubkeys' method
    } else if (method === 'listbannedpubkeys' && responseData.result && responseData.result.length > 0) {
        const listTitle = document.createElement('h2');
        listTitle.textContent = 'Banned Public Keys:';
        outputDiv.appendChild(listTitle);

        const resultList = document.createElement('ul');
        resultList.className = 'result-list';

        responseData.result.forEach(pubkey => {
            const listItem = document.createElement('li');
            listItem.textContent = `Pubkey: ${pubkey}`;
            resultList.appendChild(listItem);
        });

        outputDiv.appendChild(resultList);

    // Handle 'listallowedpubkeys' method
    } else if (method === 'listallowedpubkeys' && responseData.result && responseData.result.length > 0) {
        const listTitle = document.createElement('h2');
        listTitle.textContent = 'Allowed Public Keys:';
        outputDiv.appendChild(listTitle);

        const resultList = document.createElement('ul');
        resultList.className = 'result-list';

        responseData.result.forEach(pubkey => {
            const listItem = document.createElement('li');
            listItem.textContent = `Allowed Pubkey: ${pubkey}`;
            resultList.appendChild(listItem);
        });

        outputDiv.appendChild(resultList);

    // Handle 'listblockedips' method
    } else if (method === 'listblockedips' && responseData.result && responseData.result.length > 0) {
        const listTitle = document.createElement('h2');
        listTitle.textContent = 'Blocked IPs:';
        outputDiv.appendChild(listTitle);

        const resultList = document.createElement('ul');
        resultList.className = 'result-list';

        responseData.result.forEach(ip => {
            const listItem = document.createElement('li');
            listItem.textContent = `Blocked IP: ${ip}`;
            resultList.appendChild(listItem);
        });

        outputDiv.appendChild(resultList);

    // Handle cases where there are no results
    } else if (responseData.result && responseData.result.length === 0) {
        outputDiv.innerHTML = '<p>No results found.</p>';

    // Handle invalid responses or methods
    } else {
        outputDiv.innerHTML = '<p>Invalid response or method.</p>';
    }
}


// Function to show/hide fields based on method selection
function handleMethodChange() {
    const method = document.getElementById('method').value;
    const pubkeyField = document.getElementById('pubkeyField');
    const kindField = document.getElementById('kindField');
    const reasonField = document.getElementById('reasonField');
    const ipField = document.getElementById('ipField');

    // Reset fields visibility
    pubkeyField.classList.add('hidden');
    kindField.classList.add('hidden');
    reasonField.classList.add('hidden');
    ipField.classList.add('hidden');

    // Show the appropriate fields based on the selected method
    switch (method) {
        case 'banpubkey':
        case 'allowpubkey':
            pubkeyField.classList.remove('hidden');
            reasonField.classList.remove('hidden');  // Optional reason
            break;
        case 'banevent':
        case 'allowevent':
            kindField.classList.remove('hidden');
            reasonField.classList.remove('hidden');  // Optional reason
            break;
        case 'changerelayname':
        case 'changerelaydescription':
        case 'changerelayicon':
            reasonField.classList.remove('hidden');  // Use for new name/icon/description
            break;
        case 'allowkind':
        case 'disallowkind':
            kindField.classList.remove('hidden');
            break;
        case 'blockip':
            ipField.classList.remove('hidden');
            reasonField.classList.remove('hidden');  // Optional reason
            break;
        case 'unblockip':
            ipField.classList.remove('hidden');
            break;
        default:
            // Other methods don't need additional input
            break;
    }
}

// Add event listener for Create and Sign Event button
document.getElementById('createEventButton').addEventListener('click', async () => {
    try {
        // Get selected method and user inputs
        const method = document.getElementById('method').value;
        const pubkey = document.getElementById('pubkey').value;
        const kind = document.getElementById('kind').value;
        const reason = document.getElementById('reason').value;
        const ip = document.getElementById('ip').value;

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
                params.push(pubkey, kind);
                if (reason) params.push(reason);
                break;
            case 'changerelayname':
            case 'changerelaydescription':
            case 'changerelayicon':
                params.push(reason);  // Reason is used for new name, icon, or description
                break;
            case 'allowkind':
            case 'disallowkind':
                params.push(kind);
                break;
            case 'blockip':
                params.push(ip);
                if (reason) params.push(reason);
                break;
            case 'unblockip':
                params.push(ip);
                break;
            default:
                // No additional parameters for list methods
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
            pubkey: publicKey,  // Your public key from the extension
            kind: 27235,        // Event kind (for NIP-86 management events)
            created_at: Math.floor(Date.now() / 1000),  // Current timestamp in seconds
            tags: [
                ["u", "http://localhost:8000/nip86"],  // Example tag for URL
                ["method", "POST"],                    // Example tag for method
                ["payload", requestBodyHash]           // Payload hash for the request body
            ],
            content: ""  // The content is always empty
        };

        // Sign the event using the browser extension
        const signedEvent = await window.nostr.signEvent(event);

        // Convert the signed event to base64
        const eventBase64 = btoa(JSON.stringify(signedEvent)); // Convert event to base64

        // Send the POST request to the endpoint
        const response = await fetch('http://localhost:8000/nip86', {
            method: 'POST',
            headers: {
                'Authorization': `Nostr ${eventBase64}`,
                'Content-Type': 'application/nostr+json+rpc'
            },
            body: requestBodyString
        });

        // Parse and display the response from the server
        const responseData = await response.json();
        displayResults(responseData);  // Call the function directly without assigning it to innerHTML

    } catch (err) {
        console.error('Error creating or signing event:', err);
    }
});

// Initialize the form to show the appropriate fields when the page loads
handleMethodChange();
