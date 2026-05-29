const chatBox = document.getElementById("chatBox");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("message");
const sendButton = document.getElementById("sendButton");
const uploadForm = document.getElementById("uploadForm");
const fileInput = document.getElementById("pdfFile");
const fileName = document.getElementById("fileName");
const uploadStatus = document.getElementById("uploadStatus");
const documentList = document.getElementById("documentList");
const refreshDocs = document.getElementById("refreshDocs");
const logoutButton = document.getElementById("logoutButton");

function refreshIcons() {
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

function clearEmptyState() {
    const empty = chatBox.querySelector(".empty-state");
    if (empty) {
        empty.remove();
    }
}

function scrollChat() {
    chatBox.scrollTop = chatBox.scrollHeight;
}

function setStatus(element, message, isError = false) {
    element.textContent = message || "";
    element.classList.toggle("error", Boolean(isError));
}

async function readJson(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || "Request failed.");
    }
    return data;
}

function addMessage(role, text, options = {}) {
    clearEmptyState();

    const message = document.createElement("article");
    message.className = `message ${role}`;

    const body = document.createElement("div");
    body.className = "message-body";
    body.textContent = text;
    message.appendChild(body);

    if (options.sources?.length) {
        const sources = document.createElement("div");
        sources.className = "sources";
        options.sources.slice(0, 5).forEach((source) => {
            const pill = document.createElement("span");
            pill.className = "source-pill";
            pill.textContent = `${source.filename}${source.page ? `, ${source.page}` : ""}`;
            sources.appendChild(pill);
        });
        message.appendChild(sources);
    }

    if (options.actions?.length) {
        const actions = document.createElement("div");
        actions.className = "message-actions";
        options.actions.forEach((action) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = `mini-action ${action.primary ? "primary" : ""}`;
            button.textContent = action.label;
            button.addEventListener("click", action.onClick);
            actions.appendChild(button);
        });
        message.appendChild(actions);
    }

    chatBox.appendChild(message);
    refreshIcons();
    scrollChat();
    return message;
}

async function askQuestion(text, allowLlm = false, echoUser = true) {
    if (echoUser) {
        addMessage("user", text);
    }

    sendButton.disabled = true;
    messageInput.disabled = true;
    const pending = addMessage("assistant", "Thinking...");

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message: text, allow_llm: allowLlm}),
        });
        const data = await readJson(response);
        pending.remove();

        if (data.needs_confirmation) {
            addMessage("assistant", data.message, {
                actions: [
                    {
                        label: "Use AI model",
                        primary: true,
                        onClick: () => askQuestion(text, true, false),
                    },
                    {
                        label: "Cancel",
                        onClick: () => addMessage("assistant", "Skipped."),
                    },
                ],
            });
            return;
        }

        addMessage("assistant", data.answer || "No answer returned.", {
            sources: data.sources || [],
        });
    } catch (error) {
        pending.remove();
        addMessage("assistant", error.message);
    } finally {
        sendButton.disabled = false;
        messageInput.disabled = false;
        messageInput.focus();
    }
}

function resizeComposer() {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 180)}px`;
}

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = messageInput.value.trim();
    if (!text) {
        return;
    }
    messageInput.value = "";
    resizeComposer();
    await askQuestion(text);
});

messageInput.addEventListener("input", resizeComposer);
messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatForm.requestSubmit();
    }
});

fileInput.addEventListener("change", () => {
    fileName.textContent = fileInput.files[0]?.name || "Choose PDF";
});

async function loadDocuments() {
    documentList.innerHTML = "";
    try {
        const response = await fetch("/api/documents");
        const data = await readJson(response);
        if (!data.documents.length) {
            const empty = document.createElement("p");
            empty.className = "document-empty";
            empty.textContent = "No PDFs yet";
            documentList.appendChild(empty);
            return;
        }

        data.documents.forEach((documentData) => {
            const item = document.createElement("div");
            item.className = "document-item";

            const text = document.createElement("div");
            const title = document.createElement("div");
            title.className = "document-name";
            title.textContent = documentData.filename;
            const meta = document.createElement("div");
            meta.className = "document-meta";
            meta.textContent = `${documentData.pages} pages | ${documentData.chunks} chunks`;
            text.append(title, meta);

            const remove = document.createElement("button");
            remove.className = "icon-button";
            remove.type = "button";
            remove.title = "Delete file";
            remove.innerHTML = '<i data-lucide="trash-2"></i>';
            remove.addEventListener("click", () => deleteDocument(documentData.id));

            item.append(text, remove);
            documentList.appendChild(item);
        });
        refreshIcons();
    } catch (error) {
        const empty = document.createElement("p");
        empty.className = "document-empty";
        empty.textContent = error.message;
        documentList.appendChild(empty);
    }
}

async function deleteDocument(id) {
    try {
        const response = await fetch(`/api/documents/${id}`, {method: "DELETE"});
        await readJson(response);
        await loadDocuments();
    } catch (error) {
        addMessage("assistant", error.message);
    }
}

uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) {
        setStatus(uploadStatus, "Choose a PDF first.", true);
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    const uploadButton = uploadForm.querySelector("button[type='submit']");
    uploadButton.disabled = true;
    setStatus(uploadStatus, "Indexing PDF...");

    try {
        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData,
        });
        const data = await readJson(response);
        setStatus(uploadStatus, data.message);
        uploadForm.reset();
        fileName.textContent = "Choose PDF";
        await loadDocuments();
    } catch (error) {
        setStatus(uploadStatus, error.message, true);
    } finally {
        uploadButton.disabled = false;
    }
});

refreshDocs.addEventListener("click", loadDocuments);

logoutButton.addEventListener("click", async () => {
    await fetch("/api/auth/logout", {method: "POST"});
    window.location.href = "/signin";
});

window.addEventListener("DOMContentLoaded", () => {
    refreshIcons();
    loadDocuments();
});

// In api/static/app.js

function clearChat() {
    // 1. Clear the messages from the UI state
    // Replace 'messages' with the actual variable name you use 
    // to store the chat bubbles in your JavaScript
    messages = []; 
    
    // 2. Select the chat container element and empty it
    const chatContainer = document.getElementById('chat-container'); // Adjust ID as needed
    if (chatContainer) {
        chatContainer.innerHTML = ''; 
    }
    
    console.log("Chat cleared");
}

// Ensure your button is linked to this function
const clearButton = document.getElementById('clear-chat-btn'); // Adjust ID as needed
if (clearButton) {
    clearButton.addEventListener('click', clearChat);
}