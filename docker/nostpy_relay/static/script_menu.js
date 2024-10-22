// Wait for DOM to be fully loaded
document.addEventListener("DOMContentLoaded", function() {
    
    // Function to show/hide sections
    function showSection(sectionId) {
        const sections = document.querySelectorAll('.content-section');
        sections.forEach(section => {
            section.classList.add('hidden');  // Hide all sections
        });
        document.getElementById(sectionId).classList.remove('hidden');  // Show the selected section
    }

    // Add event listeners for the sidebar links
    document.querySelectorAll('.sidebar a').forEach(link => {
        link.addEventListener('click', function (event) {
            event.preventDefault(); // Prevent default anchor behavior
            const sectionId = this.getAttribute('onclick').match(/'(.*)'/)[1]; // Extract section ID from onclick attribute
            showSection(sectionId); // Show the corresponding section
        });
    });

    // Add event listeners to section buttons
    const manageKindButton = document.getElementById('manageKindButton');
    const manageEventButton = document.getElementById('manageEventButton');
    const managePubkeyButton = document.getElementById('managePubkeyButton');
    const manageIPButton = document.getElementById('manageIPButton');

    if (manageKindButton) {
        manageKindButton.addEventListener('click', async () => {
            await handleSubmit('kind');
        });
    }
    
    if (manageEventButton) {
        manageEventButton.addEventListener('click', async () => {
            await handleSubmit('id');
        });
    }

    if (managePubkeyButton) {
        managePubkeyButton.addEventListener('click', async () => {
            await handleSubmit('pubkey');
        });
    }

    if (manageIPButton) {
        manageIPButton.addEventListener('click', async () => {
            await handleSubmit('ip');
        });
    }

    // Handle form submissions for different sections
    async function handleSubmit(inputType) {
        try {
            const method = document.getElementById('method').value;
            let inputField = document.getElementById(inputType);
            const inputValue = inputField ? inputField.value : null;

            let params = [inputValue];  // Default param is the input value

            if (inputType === 'pubkey' || inputType === 'kind' || inputType === 'id' || inputType === 'ip') {
                params.push(inputValue); // Add the corresponding input value to params
            }

            const requestBody = {
                method: method,
                params: params
            };
            const requestBodyString = JSON.stringify(requestBody);

            // Send the POST request
            const response = await fetch('/nip86', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/nostr+json+rpc'
                },
                body: requestBodyString
            });

            // Parse and display the response from the server
            const responseData = await response.json();
            console.debug("Server Response:", responseData.result);
            displayResults(responseData);  // Call the function to display results

        } catch (err) {
            console.error('Error processing request:', err);
        }
    }

    // Function to display results in a human-readable format
    function displayResults(responseData) {
        const outputDiv = document.getElementById('output');
        const method = document.getElementById('method').value;

        // Clear previous output
        outputDiv.innerHTML = '';

        if (responseData.result && responseData.result.length > 0) {
            const resultList = document.createElement('ul');
            responseData.result.forEach(item => {
                const listItem = document.createElement('li');
                listItem.textContent = `${item}`;
                resultList.appendChild(listItem);
            });
            outputDiv.appendChild(resultList);
        } else {
            outputDiv.innerHTML = '<p>No results found.</p>';
        }
    }

    // Function to handle method change and display appropriate fields
    function handleMethodChange() {
        const method = document.getElementById('method').value;
        const pubkeyField = document.getElementById('pubkey');
        const kindField = document.getElementById('kind');
        const reasonField = document.getElementById('reason');
        const ipField = document.getElementById('ip');
        const idField = document.getElementById('id');

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
                idField.classList.remove('hidden');
                reasonField.classList.remove('hidden');
                break;
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

    // Initialize the form to show the appropriate fields when the page loads
    document.getElementById('method').addEventListener('change', handleMethodChange);

    // Call the function to set up initial form state
    handleMethodChange();
});
