import { showAlert } from './utils.js';

export function resetErrors() {
  const validationSummary = document.getElementById('validationSummary');
  const errorList = document.getElementById('errorList');

  if (validationSummary) {
    validationSummary.classList.add('hidden');
  }
  if (errorList) {
    errorList.innerHTML = '';
  }

  document.querySelectorAll('.error-message').forEach(el => {
    el.classList.remove('show');
    el.textContent = '';
    const formField = el.closest('.form-field');
    if (formField) {
      formField.classList.remove('error-border');
    }
  });
}

export async function pydanticVerification(formData) {
  const formDataObject = Object.fromEntries(formData.entries());
  formDataObject.is_RTE = formDataObject.is_RTE === 'true';

  try {
    const resp = await fetch('/api/pydantic_verification', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formDataObject)
    });
    const data = await resp.json();

    if (!resp.ok) {
      displayValidationErrors(data.errors || []);
      return { ok: false, pydanticData: data };
    }

    return { ok: true, pydanticData: data };
  } catch (err) {
    showAlert(404, 'An error occurred while verifying the form data.');
    console.error('Error:', err);
    return { ok: false, pydanticData: null };
  }
}

export function displayValidationErrors(errors) {
  errors.forEach(error => {
    const field = document.getElementById(error.field);
    if (!field) return;
    const formField = field.closest('.form-field');
    if (!formField) return;

    const errorEl = formField.querySelector('.error-message');
    if (errorEl) {
      errorEl.classList.add('show');
      errorEl.textContent = error.message;
      formField.classList.add('error-border');
    }
  });

  if (errors.length > 0) {
    const firstField = document.getElementById(errors[0].field);
    if (firstField) {
      firstField.focus();
      firstField.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
}

export function renderValidationErrors(errorData) {
  const errorList = document.getElementById('errorList');
  if (!errorList) return;

  errorList.innerHTML = '';
  errorData.forEach(error => {
    const li = document.createElement('li');
    li.textContent = error.message;
    errorList.appendChild(li);
    showAlert(400, error.message || 'Conflict found');

    if (error.field) {
      const field = document.getElementById(error.field);
      if (!field) return;
      const formField = field.closest('.form-field');
      if (!formField) return;

      const errorEl = formField.querySelector('.error-message');
      if (errorEl) {
        errorEl.textContent = error.message;
        errorEl.classList.add('show');
        formField.classList.add('error-border');
      }
    }
  });

  const validationSummary = document.getElementById('validationSummary');
  if (validationSummary) {
    validationSummary.classList.remove('hidden');
  }
}
