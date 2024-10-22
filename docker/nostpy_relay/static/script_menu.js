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
            const reason = event.reason || "No reason provided";
            listItem.textContent = `Event: ${id}, Reason: ${reason}`;
            resultList.appendChild(listItem);
        });

        outputDiv.appendChild(resultList);

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
            const reason = item.reason || "No reason provided";
            listItem.textContent = `Pubkey: ${pubkey}, Reason: ${reason}`;
            resultList.appendChild(listItem);
        });
    
        outputDiv.appendChild(resultList);

    } else if (method === 'listallowedpubkeys' && responseData.result && responseData.result.length > 0) {
        const listTitle = document.createElement('h2');
        listTitle.textContent = 'Allowed Public Keys:';
        outputDiv.appendChild(listTitle);

        const resultList = document.createElement('ul');
        resultList.className = 'result-list';

        responseData.result.forEach(item => {
            const listItem = document.createElement('li');
            const pubkey = item.pubkey;
            const reason = item.reason || "No reason provided";
            listItem.textContent = `Pubkey: ${pubkey}, Reason: ${reason}`;
            resultList.appendChild(listItem);
        });

        outputDiv.appendChild(resultList);

    } else if (method === 'listblockedips' && responseData.result && responseData.result.length > 0) {
        const listTitle = document.createElement('h2');
        listTitle.textContent = 'Blocked IPs:';
        outputDiv.appendChild(listTitle);

        const resultList = document.createElement('ul');
        resultList.className = 'result-list';

        responseData.result.forEach(unit => {
            const listItem = document.createElement('li');
            const ip = unit.ip;
            const reason = unit.reason || "No reason provided";
            listItem.textContent = `Blocked IP: ${ip}, Reason: ${reason}`;
            resultList.appendChild(listItem);
        });

        outputDiv.appendChild(resultList);

    } else if (method === 'listallowedkinds' && responseData.result && responseData.result.length > 0) {
        const listTitle = document.createElement('h2');
        listTitle.textContent = 'Allowed Kinds:';
        outputDiv.appendChild(listTitle);

        const resultList = document.createElement('ul');
        resultList.className = 'result-list';

        responseData.result.forEach(kind => {
            const listItem = document.createElement('li');
            listItem.textContent = `${kind}`;
            resultList.appendChild(listItem);
        });

        outputDiv.appendChild(resultList);

    } else if (responseData.result === true) {
        const message = document.createElement('p');
        message.textContent = `${method.replace(/([A-Z])/g, ' $1')} has been processed successfully.`;
        outputDiv.appendChild(message);
    } else if (responseData.result && responseData.result.length === 0) {
        outputDiv.innerHTML = '<p>No results found.</p>';
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

// Function to handle sidebar navigation and show relevant section
function showSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.add('hidden');
    });

    // Show the selected section
    document.getElementById(sectionId).classList.remove('hidden');
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

// Initialize the form to show the appropriate fields when the page loads
handleMethodChange();
