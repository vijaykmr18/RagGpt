const form = document.getElementById("authForm");
const statusLine = document.getElementById("authStatus");
const authButton = document.getElementById("authButton");

function refreshIcons() {
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function setStatus(message, isError = false) {
    statusLine.textContent = message || "";
    statusLine.classList.toggle("error", Boolean(isError));
}

async function readJson(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Request failed.");
    }
    return data;
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const mode = form.dataset.mode;
    const endpoint = mode === "signup" ? "/api/auth/signup" : "/api/auth/signin";
    const payload = {
        email: document.getElementById("email").value.trim(),
        password: document.getElementById("password").value,
    };

    const nameInput = document.getElementById("name");
    if (nameInput) {
        payload.name = nameInput.value.trim();
    }

    authButton.disabled = true;
    setStatus(mode === "signup" ? "Creating account..." : "Signing in...");

    try {
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
        });
        const data = await readJson(response);
        window.location.href = data.redirect || "/";
    } catch (error) {
        setStatus(error.message, true);
    } finally {
        authButton.disabled = false;
    }
});

window.addEventListener("DOMContentLoaded", refreshIcons);
