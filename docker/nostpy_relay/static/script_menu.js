// Wait for DOM to be fully loaded
document.addEventListener("DOMContentLoaded", function() {

    // Function to show/hide sections
    function showSection(sectionId) {
        const sections = document.querySelectorAll('.content-section');
        sections.forEach(section => {
            section.classList.add('hidden');
        });
        document.getElementById(sectionId).classList.remove('hidden');
    }

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
});
