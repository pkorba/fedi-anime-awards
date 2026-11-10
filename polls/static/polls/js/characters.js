const selectedTray = document.getElementById("selected-tray");
const selectedItems = document.getElementById("selected-items");
const form = document.getElementById("nomination-form");
const searchForm = document.getElementById("character-search");
const choices = [...document.querySelectorAll(".selection-choice")];
const counter = document.getElementById("selection-count");
const status = document.getElementById("save-status");
const maxSelections = JSON.parse(
    document.getElementById("max-selections").textContent
);
const fieldset = form.querySelector("fieldset");
const options = [...fieldset.querySelectorAll(".character-option")];

let saveTimer = null;
let savePending = false;
let saveRun = null;
let isDirty = false;


function moveSelectedToTop() {
    const selected = options.filter(option =>
        option.querySelector(".selection-choice").checked
    );
    const unselected = options.filter(option =>
        !option.querySelector(".selection-choice").checked
    );

    [...selected, ...unselected].forEach(option => fieldset.appendChild(option));
}

function updateSelectedTray() {
    selectedItems.replaceChildren();

    const selected = choices.filter(choice => choice.checked);
    selectedTray.hidden = selected.length === 0;

    selected.forEach(choice => {
        const option = choice.closest(".character-option");
        const title = option.querySelector(".character-title").textContent.trim();

        const chip = document.createElement("div");
        chip.className = "selected-chip";

        const poster = option.querySelector(".poster-frame img");
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

            if (!isDirty) {
                continue;
            }
            // Capture the latest state when sending, not when the click occurred.
            const selected = choices
                .filter(choice => choice.checked)
                .map(choice => choice.value);

            isDirty = false;

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
                isDirty = true;
                savePending = true;
                await delay(1100);
                continue;
            }

            if (!response.ok) {
                throw new Error("Save failed");
            }
            if (!isDirty) {
                status.textContent = "✅";
            }
        }
    })();

    try {
        await saveRun;
    } catch (error) {
        isDirty = true;
        status.textContent = "❌";
        throw error;
    } finally {
        saveRun = null;
    }
}

choices.forEach(choice => {
    choice.addEventListener("change", () => {
        isDirty = true;
        moveSelectedToTop();
        updateChoices();
        scheduleSave();
    });
});

searchForm.addEventListener("submit", async event => {
    event.preventDefault();

    // Flush the debounce timer and save the latest selection before searching.
    clearTimeout(saveTimer);
    saveTimer = null;
    if (isDirty) {
        savePending = true;
    }

    try {
        await flushSaves();
        searchForm.submit();
    } catch {
        // Keep the current page open if saving failed.
    }
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
        isDirty ||
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

moveSelectedToTop();
updateChoices();