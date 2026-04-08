
async function submit(button, inputID) {

    const input = document.getElementById(inputID);
    let score = input.value;

    let marks_id = button.dataset.id;
    const evaluation_type = button.dataset.evaluation_type;
    const student_id = button.dataset.student_id;
    const subject_id = button.dataset.subject_id;
    const exam_id = button.dataset.exam_id;

    if (evaluation_type === 'grading') {
        if (!["A", "B", "C", "D", "E", "F", ""].includes(score)) {
            input.setCustomValidity("Invalid grade! Please enter A, B, C, D, E, or F.");
            input.reportValidity();
            return;
        } else {
            input.setCustomValidity("");
        }
    }

    if (marks_id === '' || marks_id === 'None') {
        marks_id = null;
    }

    // --- Validate Numeric ---
    if (evaluation_type === "numeric") {
        if (score === "") {
            // empty string → treat as null
            score = null;
        } else {
            const num = parseFloat(score);

            if (isNaN(num)) {
                input.setCustomValidity("Please enter a valid number.");
                input.reportValidity();
                return;
            }

            const min = parseFloat(input.min) || 0;
            const max = parseFloat(input.max) || 100;

            if (num < min || num > max) {
                input.setCustomValidity(`Score must be between ${min} and ${max}.`);
                input.reportValidity();
                return;
            } else {
                input.setCustomValidity("");
            }
        }
    }

    const originalButtonHTML = button.innerHTML;
    const originalBgClasses = [...button.classList].filter(c => c.includes("bg-"));
    button.disabled = true;
    button.innerHTML = "SUBMITTING...";


    try {
        const response = await fetch("/update_marks_api", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ marks_id, score, student_id, subject_id, exam_id })
        });

        const data = await response.json();


        if (!response.ok) {
            showAlert(response.status, data.message || "Failed to update marks.");
            console.error("Error:", data.message);
        }

        button.innerHTML = '<span class="inline-flex items-center gap-2"><i class="fas fa-check"></i> SUBMITTED</span>';
        button.classList.remove(...originalBgClasses);
        button.classList.add("bg-green-600", "hover:bg-green-700");

        // Revert after 3 seconds
        setTimeout(() => {
            button.innerHTML = originalButtonHTML;
            button.classList.remove("bg-green-600", "hover:bg-green-700");
            button.classList.add(...originalBgClasses);
        }, 3000);

        input.classList.remove("border-red-500");
        input.classList.add("is-valid");

        if (data.new_mark_id) {
            button.dataset.id = data.new_mark_id
        }

        // Focus on next input in the same table
        const container = input.closest("table") || input.closest("#marks-mobile-container");

        const allInputs = Array.from(container.querySelectorAll("input"));
        const index = allInputs.indexOf(input);
        const nextInput = allInputs[index + 1];

        if (nextInput) {
            nextInput.focus();
            nextInput.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    } catch (error) {
        // ❌ Network or unexpected error
        console.error("Error:", error);
        input.classList.add("border-red-500");
        // showAlert(400, "Unexpected error occurred. Please try again.");
    } finally {
        // --- Reset UI back to normal ---
        button.disabled = false;
        if (button.innerHTML === "SUBMITTING...") {
            button.innerHTML = originalButtonHTML;
        }
    }
}
