import { convertBlobToBase64, showAlert } from './utils.js';
import { pydanticVerification, resetErrors } from './validation.js';

export function getFormData(form) {
  const formData = new FormData(form);
  form.querySelectorAll('input[disabled], select[disabled]').forEach(field => {
    if (field.type !== 'hidden') {
      formData.set(field.name, field.value);
    }
  });
  return formData;
}

export async function submitForm(manager, verifiedData) {
  try {
    let endpoint;
    let payload;
    const base64Image = await prepareImage(manager);

    if (manager.mode === 'add') {
      endpoint = '/api/add_student';
      payload = { image: base64Image, verifiedData };
    } else if (manager.mode === 'edit') {
      endpoint = '/api/update_student';
      payload = {
        student_id: manager.studentId,
        image: base64Image,
        image_status: manager.avatarUploader?.getStatus() || 'unchanged',
        verifiedData
      };
    } else {
      showAlert(400, 'Invalid Operation! Reload the page and try again.');
      if (manager.mode === 'add') {
        closeStudentModal();
      }
      return;
    }

    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await resp.json();

    if (!resp.ok) {
      renderValidationErrors(data);
      if (manager.mode === 'add') {
        closeStudentModal();
      }
      return;
    }

    showAlert(resp.status, data.message);
    if (manager.mode === 'add') {
      closeStudentModal();
      showAdmissionDoneModal(data.student_id);
    }
  } catch (error) {
    showAlert(400, 'Unexpected error occurred!');
    console.error('Error:', error);
  } finally {
    if (manager.mode === 'add') {
      const finalSubmitBtn = document.getElementById('finalSubmit');
      if (finalSubmitBtn) {
        finalSubmitBtn.disabled = false;
        finalSubmitBtn.textContent = 'Confirm';
      }
    }
  }
}

export async function handleSubmit(manager, e) {
  e.preventDefault();
  resetErrors();

  try {
    manager.submitBtn.disabled = true;
    manager.spinner.classList.remove('hidden');

    const formData = getFormData(manager.form);
    const { ok, pydanticData } = await pydanticVerification(formData);
    if (!ok) {
      return;
    }
    if (manager.mode === 'add') {
      openVerificationModal(manager, pydanticData.verifiedData);
    } else {
      await submitForm(manager, pydanticData.verifiedData);
    }
  } catch (error) {
    showAlert(400, 'Unexpected error occurred!');
    console.error('Error:', error);
  } finally {
    manager.spinner.classList.add('hidden');
    manager.submitBtn.disabled = false;
  }
}

export async function handleFinalSubmit(manager, e) {
  if (e) e.preventDefault();
  const finalSubmitBtn = document.getElementById('finalSubmit');
  if (finalSubmitBtn) {
    finalSubmitBtn.disabled = true;
    finalSubmitBtn.textContent = 'Submitting...';
  }

  try {
    const formData = getFormData(manager.form);
    const { ok, pydanticData } = await pydanticVerification(formData);
    if (!ok) {
      closeStudentModal();
      if (finalSubmitBtn) {
        finalSubmitBtn.disabled = false;
        finalSubmitBtn.textContent = 'Submit Admission';
      }
      return;
    }
    await submitForm(manager, pydanticData.verifiedData);
  } catch (error) {
    showAlert(400, 'Unexpected error occurred!');
    console.error('Error:', error);
    if (finalSubmitBtn) {
      finalSubmitBtn.disabled = false;
      finalSubmitBtn.textContent = 'Submit Admission';
    }
  }
}

export async function prepareImage(manager) {
  if (manager.mode === 'add') {
    const blob = manager.avatarUploader?.getBlob?.();
    return blob ? await convertBlobToBase64(blob) : null;
  }

  const status = manager.avatarUploader?.getStatus?.();
  if (status === 'updated') {
    const blob = manager.avatarUploader?.getBlob?.();
    return blob ? await convertBlobToBase64(blob) : null;
  }

  return null;
}

export function openVerificationModal(manager, verifiedData) {
  if (window.loadAdmissionPreview) {
    window.loadAdmissionPreview(verifiedData, manager.avatarUploader?.getBlob?.());
  }
}

export function showAdmissionDoneModal(studentId) {
  const successModal = document.getElementById('successModal');
  if (successModal) {
    successModal.classList.remove('hidden');
    document.body.classList.add('overflow-hidden');
  }
  document.getElementById('sendWhatsAppBTN').onclick = () => sendMessage(studentId);
  document.getElementById('printFormBTN').onclick = () => printAdmissionForm(studentId);
}

function renderValidationErrors(errorData) {
  const errorList = document.getElementById('errorList');
  if (errorList) {
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
}
