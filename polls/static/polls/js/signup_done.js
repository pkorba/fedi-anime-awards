const script = document.getElementById("signup-done-script");
const statusUrl = script.dataset.statusUrl;
const statusElement = document.getElementById("signup-status");
const errorElement = document.getElementById("signup-error");
const successElement = document.getElementById("signup-success");
const linkElement = document.getElementById("signup-link");

async function checkSignup() {
    try {
        const response = await fetch(statusUrl, {
            method: "GET",
            credentials: "same-origin",
            headers: {"Accept": "application/json"},
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error(`Status request failed: ${response.status}`);
        }

        const data = await response.json();

        if (data.status === "pending") {
            statusElement.textContent = "Your Fediverse account is being verified. Please wait…";
            setTimeout(checkSignup, 3000);
        } else if (data.status === "succeeded") {
            statusElement.hidden = true;
            successElement.hidden = false;
        } else if (data.status === "failed") {
            statusElement.textContent = "Signup could not be completed.";
            errorElement.textContent = data.message;
            errorElement.hidden = false;
            linkElement.hidden = false;
        } else {
            statusElement.textContent =
                "We couldn't find the status for this signup. Please try again.";
            linkElement.hidden = false;
        }
    } catch (error) {
        statusElement.textContent =
            "Could not check the status just now. Trying again…";
        setTimeout(checkSignup, 5000);
    }
}

checkSignup();
