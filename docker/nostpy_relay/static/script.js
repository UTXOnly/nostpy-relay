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
            const id = event.id;
            const reason = event.reason || "No reason provided"; // Default text for missing reason
            listItem.textContent = `Event: ${id}, Reason: ${reason}`;
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
    
        // Loop through the array of dictionaries (objects)
        responseData.result.forEach(item => {
            const listItem = document.createElement('li');
            const pubkey = item.pubkey;
            const reason = item.reason || "No reason provided"; // Default text for missing reason
            listItem.textContent = `Pubkey: ${pubkey}, Reason: ${reason}`;
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

        responseData.result.forEach(item => {
            const listItem = document.createElement('li');
            const pubkey = item.pubkey
            const reason = item.reason || "No reason provided"; // Default text for missing reason
            listItem.textContent = `Pubkey: ${pubkey}, Reason: ${reason}`;
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

        responseData.result.forEach(unit => {
            const listItem = document.createElement('li');
            const ip = unit.ip
            const reason = unit.reason || "No reason provided"; // Default text for missing reason
            listItem.textContent = `Blocked IP: ${ip}, Reason: ${reason}`;
            resultList.appendChild(listItem);
        });

        outputDiv.appendChild(resultList);

    } else if (method === 'listallowedkinds' && responseData.result && responseData.result.length > 0) {
        const listTitle = document.createElement('h2');
        listTitle.textContent = 'Allowed kinds:';
        outputDiv.appendChild(listTitle);

        const resultList = document.createElement('ul');
        resultList.className = 'result-list';

        responseData.result.forEach(kind => {
            const listItem = document.createElement('li');
            listItem.textContent = `${kind}`;
            resultList.appendChild(listItem);
        });

        outputDiv.appendChild(resultList);

    // Handle 'banpubkey' method
    } else if (method === 'banpubkey' && responseData.result == true) {
        const message = document.createElement('p');
        message.textContent = 'Pubkey has been banned successfully.';
        outputDiv.appendChild(message);

    // Handle 'allowpubkey' method
    } else if (method === 'allowpubkey' && responseData.result == true) {
        const message = document.createElement('p');
        message.textContent = 'Pubkey has been allowed successfully.';
        outputDiv.appendChild(message);

    // Handle 'banevent' method
    } else if (method === 'banevent' && responseData.result == true) {
        const message = document.createElement('p');
        message.textContent = 'Event has been banned successfully.';
        outputDiv.appendChild(message);

    // Handle 'allowevent' method
    } else if (method === 'allowevent' && responseData.result == true) {
        const message = document.createElement('p');
        message.textContent = 'Event has been allowed successfully.';
        outputDiv.appendChild(message);

    } else if (method === 'allowkind' && responseData.result == true) {
        const message = document.createElement('p');
        message.textContent = 'Kind has been allowed successfully.';
        outputDiv.appendChild(message);

    // Handle 'changerelayname' method
    } else if (method === 'changerelayname' && responseData.result == true) {
        const message = document.createElement('p');
        message.textContent = 'Relay name has been changed successfully.';
        outputDiv.appendChild(message);

    // Handle 'changerelaydescription' method
    } else if (method === 'changerelaydescription' && responseData.result == true) {
        const message = document.createElement('p');
        message.textContent = 'Relay description has been changed successfully.';
        outputDiv.appendChild(message);

    // Handle 'changerelayicon' method
    } else if (method === 'changerelayicon' && responseData.result == true) {
        const message = document.createElement('p');
        message.textContent = 'Relay icon has been changed successfully.';
        outputDiv.appendChild(message);

    } else if (method === 'blockip' && responseData.result == true) {
        const message = document.createElement('p');
        message.textContent = 'IP has been blocked successfully.';
        outputDiv.appendChild(message);

    } else if (method === 'unblockip' && responseData.result == true) {
        const message = document.createElement('p');
        message.textContent = 'IP has been allowed successfully.';
        outputDiv.appendChild(message);

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
            reasonField.classList.remove('hidden');  // Optional reason
            break;
        case 'banevent':
            idField.classList.remove('hidden')
            reasonField.classList.remove('hidden');
        case 'allowevent':
            idField.classList.remove('hidden');
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
        const id = document.getElementById('id').value;

        // Fetch the public key using the extension
        const publicKey = await window.nostr.getPublicKey();

        // Build the request body based on the selected method and fields
        let params = [];
        switch (method) {
            case 'banpubkey':
                params.push(pubkey);
                if (reason) params.push(reason);
                break;
            case 'listallowedkinds':
            case 'allowpubkey':
                params.push(pubkey);
                if (reason) params.push(reason);
                break;
            case 'banevent':
                params.push(id)
                if (reason) params.push(reason);
                break;
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
                ["u", "https://dev.nostpy.lol/nip86"],  // Example tag for URL
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
        displayResults(responseData);  // Call the function directly without assigning it to innerHTML

    } catch (err) {
        console.error('Error creating or signing event:', err);
    }
});

// Initialize the form to show the appropriate fields when the page loads
handleMethodChange();
