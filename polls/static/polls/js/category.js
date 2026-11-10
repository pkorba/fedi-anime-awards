const form = document.getElementById("nomination-form");
const choices = [...document.querySelectorAll(".selection-choice")];
const counter = document.getElementById("selection-count");
const status = document.getElementById("save-status");
const maxSelections = JSON.parse(
    document.getElementById("max-selections").textContent
);
const searchInput = document.getElementById("s-search");
const fieldset = form.querySelector("fieldset");
const sOptions = [...fieldset.querySelectorAll(".s-option")];
const selectedTray = document.getElementById("selected-tray");
const selectedItems = document.getElementById("selected-items");

let saveTimer = null;
let savePending = false;
let saveRun = null;

searchInput.addEventListener("input", () => {
    const query = searchInput.value.trim().toLocaleLowerCase();

    sOptions.forEach(option => {
        const title = option.querySelector(".s-title")
            .textContent.trim().toLocaleLowerCase();
        option.hidden = !title.includes(query);
    });
});

function moveSelectedToTop() {
    const selected = sOptions.filter(option =>
        option.querySelector(".selection-choice").checked
    );
    const unselected = sOptions.filter(option =>
        !option.querySelector(".selection-choice").checked
    );

    [...selected, ...unselected].forEach(option => fieldset.appendChild(option));
}

function updateSelectedTray() {
    selectedItems.replaceChildren();

    const selected = choices.filter(choice => choice.checked);
    selectedTray.hidden = selected.length === 0;

    selected.forEach(choice => {
        const option = choice.closest(".s-option");
        const label = option.querySelector("label");
        const title = label.querySelector(".s-title")?.textContent.trim()
            || label.textContent.trim();

        const chip = document.createElement("div");
        chip.className = "selected-chip";

        const poster = label.querySelector(".poster-frame img");
        if (poster) {
            const thumbnail = document.createElement("img");
            thumbnail.src = poster.src;
            thumbnail.alt = "";
            chip.appendChild(thumbnail);
        }

        const name = document.createElement("span");
        name.textContent = title;
        chip.appendChild(name);
        selectedItems.appendChild(chip);
    });
}

function updateChoices() {
    const count = choices.filter(choice => choice.checked).length;
    counter.textContent = `${count}/${maxSelections}`;

    choices.forEach(choice => {
        choice.disabled = !choice.checked && count >= maxSelections;
    });

    updateSelectedTray();
}

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function scheduleSave() {
    clearTimeout(saveTimer);

    saveTimer = setTimeout(() => {
        saveTimer = null;
        savePending = true;
        flushSaves().catch(() => {
            status.textContent = "❌";
        });
    }, 400);
}

async function flushSaves() {
    // Share the active save loop so navigation can wait for it.
    if (saveRun) {
        return saveRun;
    }

    saveRun = (async () => {
        while (savePending) {
            savePending = false;

            // Capture the latest state when sending, not when the click occurred.
            const selected = choices
                .filter(choice => choice.checked)
                .map(choice => choice.value);

            const data = new FormData();
            data.append(
                "csrfmiddlewaretoken",
                form.querySelector('[name="csrfmiddlewaretoken"]').value
            );
            selected.forEach(id => data.append("selected_entries", id));

            status.textContent = "🔄";

            const response = await fetch(window.location.href, {
                method: "POST",
                body: data,
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });

            if (response.status === 429) {
                // The server's throttle interval is one second.
                savePending = true;
                await delay(1100);
                continue;
            }

            if (!response.ok) {
                throw new Error("Save failed");
            }

            status.textContent = "✅";
        }
    })();

    try {
        await saveRun;
    } finally {
        saveRun = null;
    }
}

choices.forEach(choice => {
    choice.addEventListener("change", () => {
        moveSelectedToTop();
        updateChoices();
        scheduleSave();
    });
});

// Wait for pending saves before following same-site links.
document.addEventListener("click", event => {
    const link = event.target.closest("a");

    if (
        !link ||
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey ||
        link.target === "_blank" ||
        link.hasAttribute("download")
    ) {
        return;
    }

    const url = new URL(link.href, window.location.href);

    if (
        url.origin !== window.location.origin ||
        !["http:", "https:"].includes(url.protocol)
    ) {
        return;
    }

    const hasPendingSave =
        saveTimer !== null ||
        savePending ||
        saveRun !== null;

    if (!hasPendingSave) {
        return;
    }

    event.preventDefault();
    clearTimeout(saveTimer);
    saveTimer = null;
    savePending = true;

    flushSaves()
        .then(() => {
            window.location.assign(url.href);
        })
        .catch(() => {
            status.textContent = "❌";
        });
});

// Prevent sending form when user hits enter in the filter input field
form.addEventListener("submit", event => {
    event.preventDefault();
});

moveSelectedToTop();
updateChoices();