// Student Form JavaScript - Organized and Scalable

class StudentFormManager {
  constructor() {
    this.avatarUploader = null;
    this.form = document.getElementById('DataForm');
    this.submitBtn = document.getElementById('FormSubmit');
    this.spinner = document.getElementById('btn-spinner');
    this.btnText = document.getElementById('btn-text');
    this.mode = window.MODE;
    this.studentId = window.STUDENT_ID;
    this.hasOtherSessions = window.has_other_sessions;
    this.originalAcademicValues = null;
  }

  init() {
    this.initImageUploader();
    this.initFormBehaviors();
    this.initEventListeners();
  }

  initImageUploader() {
    const uniqueSuffix = "_" + this.mode + '_' + this.studentId;
    this.avatarUploader = new ImageUploader(uniqueSuffix);
    this.avatarUploader.onChange((blob, status) => console.log('Avatar:', status, blob));
  }

  initFormBehaviors() {
    this.initAadharFormatting();
    this.initDateMasks();
    this.initRteToggle();
    this.initClassRollLogic();
  }

  initAadharFormatting() {
    ['AADHAAR', 'FATHERS_AADHAR', 'MOTHERS_AADHAR'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', () => this.formatAadharNumber(el));
    });
  }

  initDateMasks() {
    this.attachDateMask('#DOB', 'DD-MM-YYYY');
    this.attachDateMask('#ADMISSION_DATE', 'DD-MM-YYYY');
    this.initAgeCalculation();
  }

  initAgeCalculation() {
    const dobEl = document.querySelector('#DOB');
    if (!dobEl) return;

    let ageDisplay = dobEl.parentNode.querySelector('.age-display');
    if (!ageDisplay) {
      ageDisplay = document.createElement('div');
      ageDisplay.className = 'age-display text-sm text-gray-400 mt-1';
      dobEl.parentNode.insertBefore(ageDisplay, dobEl.nextSibling);
    }

    const updateDisplays = () => {
      const value = dobEl.value;
      if (value.length === 10 && /^\d{2}-\d{2}-\d{4}$/.test(value)) {
        const age = this.calculateAge(value);
        ageDisplay.textContent = `Age: ${age} years`;
        this.updateClassSuggestion(age);
      } else {
        ageDisplay.textContent = '';
        this.updateClassSuggestion(null);
      }
    };

    dobEl.addEventListener('input', updateDisplays);

    // Check initial value
    if (dobEl.value) {
      updateDisplays();
    }
  }

  calculateAge(dobString) {
    const [day, month, year] = dobString.split('-').map(Number);
    const birthDate = new Date(year, month - 1, day);
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }
    return age;
  }

  updateClassSuggestion(age) {
    const classEl = document.getElementById('CLASS');
    if (!classEl) return;

    let suggestionEl = classEl.parentNode.querySelector('.class-suggestion');
    if (!suggestionEl) {
      suggestionEl = document.createElement('div');
      suggestionEl.className = 'class-suggestion text-sm text-blue-400 mt-1';
      classEl.parentNode.insertBefore(suggestionEl, classEl.nextSibling);
    }

    if (age !== null) {
      const suggestedClass = this.getSuggestedClass(age);
      suggestionEl.textContent = `Suggested class: ${suggestedClass}`;
    } else {
      suggestionEl.textContent = '';
    }
  }

  getSuggestedClass(age) {
    if (age === 3) return 'Nursery or Pre-Nursery';
    if (age === 4) return 'Nursery';
    if (age === 5) return 'LKG';
    if (age === 6) return 'UKG';
    if (age === 7) return '1st';
    if (age === 8) return '2nd';
    if (age === 9) return '3rd';
    if (age === 10) return '4th';
    if (age === 11) return '5th';
    if (age === 12) return '6th';
    if (age === 13) return '7th';
    if (age === 14) return '8th';
    if (age === 15) return '9th';
    if (age === 16) return '10th';
    if (age === 17) return '11th';
    if (age > 17) return 'Above 12th';
    if (age < 3) return 'Too young for admission';
    return 'Age not suitable';
  }

  showRollHint(gappedRolls, nextRoll) {
    let rollHint = document.getElementById('rollHint');
    if (!rollHint) {
      rollHint = document.createElement('div');
      rollHint.id = 'rollHint';
      rollHint.className = 'text-sm text-gray-400 mt-1';
      document.getElementById('ROLL').parentNode.insertBefore(rollHint, document.getElementById('ROLL').nextSibling);
    }
    const allowedRolls = [...gappedRolls, nextRoll].join(', ');
    rollHint.textContent = `Available rolls: ${allowedRolls}`;
  }

  initRteToggle() {
    const rteCheckbox = document.getElementById('is_RTE');
    const rteFields = document.getElementById('rteFields');
    if (rteCheckbox && rteFields) {
      rteCheckbox.addEventListener('change', () => {
        rteFields.classList.toggle('hidden', !rteCheckbox.checked);
      });
    }
  }

  initClassRollLogic() {
    if (this.mode === 'add' || !this.hasOtherSessions) {
      this.setupNewStudentLogic();
    } else {
      this.setupOldStudentLogic();
    }
  }

  setupNewStudentLogic() {
    const classSelect = document.getElementById('CLASS');
    const admissionSessionSelect = document.getElementById('admission_session_id');
    const admissionClassSelect = document.getElementById('Admission_Class');
    const rollInput = document.getElementById('ROLL');
    const studentStatusRadios = document.querySelectorAll('input[name="student_status"]');
    const checkedStatusRadio = document.querySelector('input[name="student_status"]:checked');

    this.originalAcademicValues = {
      admissionSession: admissionSessionSelect?.dataset.originalSession || admissionSessionSelect?.value || '',
      admissionClass: admissionClassSelect?.dataset.originalAdmissionClass || admissionClassSelect?.value || '',
      currentClass: classSelect?.dataset.originalCurrentClass || classSelect?.value || '',
      roll: rollInput?.dataset.originalRoll || rollInput?.value || ''
    };

    // Status change
    studentStatusRadios.forEach(radio => {
      radio.addEventListener('change', () => {
        this.handleStudentStatusChange(radio.value);
      });
    });

    // CLASS change → ALWAYS update roll
    if (classSelect) {
      classSelect.addEventListener('change', () => {
        if (admissionClassSelect?.disabled) {
          admissionClassSelect.value = classSelect.value;
        }
        this.updateRollForClass(classSelect.value);
      });
    }

    // Initialize UI state based on current selection
    if (checkedStatusRadio) {
      this.handleStudentStatusChange(checkedStatusRadio.value);
    }
  }
  

  setupOldStudentLogic() {
    const classSelect = document.getElementById('CLASS');
    const admissionSessionSelect = document.getElementById('admission_session_id');
    const admissionClassSelect = document.getElementById('Admission_Class');

    // Disable in edit mode (authoritative)
    if (classSelect) classSelect.disabled = true;
    const msg = document.createElement("p");
    msg.className = "text-xs text-red-400";
    msg.textContent = "You can change the class from Promotions page.";
    classSelect.parentNode.insertBefore(msg, classSelect.nextSibling);
    // if (admissionSessionSelect) admissionSessionSelect.disabled = true;

    // // Roll logic (kept for safety / future reuse)
    // classSelect?.addEventListener('change', () => {
    // });

    // Optional UX clarity
    if (admissionClassSelect?.disabled) {
      admissionClassSelect.title = 'Cannot modify: Student has past academic records';
    }

    if (admissionSessionSelect?.disabled) {
      admissionSessionSelect.title = 'Cannot modify: Student has past academic records';
    }
  }


  handleStudentStatusChange(status) {
    const admissionClassSelect = document.getElementById('Admission_Class');
    const classSelect = document.getElementById('CLASS');
    const admissionSessionSelect = document.getElementById('admission_session_id');
    const rollInput = document.getElementById('ROLL');

    this.showRollHint([], ''); // Clear previous hints

    if (status === 'new') {
      const currentSession = admissionSessionSelect?.dataset.currentSession;
      if (currentSession) {
        admissionSessionSelect.value = currentSession;
      }
      if (admissionClassSelect && classSelect) {
        classSelect.value = admissionClassSelect.value;
      }

      if (admissionClassSelect) admissionClassSelect.disabled = true;
      if (classSelect) classSelect.disabled = false;
      if (admissionSessionSelect) admissionSessionSelect.disabled = true;

      admissionClassSelect?.removeEventListener(
        'change',
        this.handleAdmissionClassChange
      );

      if (classSelect?.value) {
        this.updateRollForClass(classSelect.value);
      }
    } else {
      if (admissionClassSelect) admissionClassSelect.disabled = false;
      if (classSelect) classSelect.disabled = false;
      if (admissionSessionSelect) admissionSessionSelect.disabled = false;
      admissionClassSelect?.removeEventListener(
        'change',
        this.handleAdmissionClassChange
      );

      if (this.originalAcademicValues) {
        if (admissionSessionSelect && this.originalAcademicValues.admissionSession) {
          admissionSessionSelect.value = this.originalAcademicValues.admissionSession;
        }
        if (admissionClassSelect && this.originalAcademicValues.admissionClass) {
          admissionClassSelect.value = this.originalAcademicValues.admissionClass;
        }
        if (classSelect && this.originalAcademicValues.currentClass) {
          classSelect.value = this.originalAcademicValues.currentClass;
        }
        if (rollInput && this.originalAcademicValues.roll) {
          rollInput.value = this.originalAcademicValues.roll;
        }
      }
    }
  }

  handleAdmissionClassChange = () => {
    const admissionClassSelect = document.getElementById('Admission_Class');
    if (!admissionClassSelect) return;

    this.updateRollForClass(admissionClassSelect.value);
  };


  async updateRollForClass(classId) {
    const rollInput = document.getElementById('ROLL');
    
    if (!classId || !rollInput) return;

    try {
      const resp = await fetch('/get_new_roll_api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ class_id: classId })
      });
      const result = await resp.json();
      if (!resp.ok) {
        this.showAlert(resp.status, result.message);
        return;
      }
      rollInput.value = result.next_roll;
      this.showRollHint(result.gapped_rolls, result.next_roll);
    } catch (err) {
      console.error('Error fetching next roll:', err);
    }
  }



  initEventListeners() {
    this.submitBtn.addEventListener('click', (e) => this.handleSubmit(e));
    if (this.mode === 'add') {
      const finalSubmitBtn = document.getElementById('finalSubmit');
      finalSubmitBtn?.addEventListener('click', (e) => this.handleFinalSubmit(e));
      document.querySelectorAll('.cancelModal').forEach(el => {
        el.addEventListener('click', () => this.closeVerificationModal());
      });
    }
  }

  async handleSubmit(e) {

    e.preventDefault();
    this.resetErrors();

    try {
      this.submitBtn.disabled = true;
      this.spinner.classList.remove('hidden');

      const formData = this.getFormData();
      const { ok, pydanticData } = await this.pydanticVerification(formData);
      if (!ok) {
        return;
      }
      if (this.mode === 'add') {
        this.openVerificationModal(pydanticData.verifiedData);
      } else {
        await this.submitForm(pydanticData.verifiedData);
      }
    } catch (error) {
      this.showAlert(400, 'Unexpected error occurred!');
      console.error('Error:', error);
    }
    finally {
      this.spinner.classList.add('hidden');
      this.submitBtn.disabled = false;
    }
  }

  async handleFinalSubmit(e) {
    if (e) e.preventDefault();
    const finalSubmitBtn = document.getElementById('finalSubmit');
    if (finalSubmitBtn) {
      finalSubmitBtn.disabled = true;
      finalSubmitBtn.textContent = 'Submitting...';
    }

    try {
      const formData = this.getFormData();
      const { ok, pydanticData } = await this.pydanticVerification(formData);
      if (!ok) {
        closeStudentModal();
        if (finalSubmitBtn) {
          finalSubmitBtn.disabled = false;
          finalSubmitBtn.textContent = 'Submit Admission';
        }
        return;
      }
      await this.submitForm(pydanticData.verifiedData);
    } catch (error) {
      this.showAlert(400, 'Unexpected error occurred!');
      console.error('Error:', error);
      if (finalSubmitBtn) {
        finalSubmitBtn.disabled = false;
        finalSubmitBtn.textContent = 'Submit Admission';
      }
    }
  }

  resetErrors() {
    document.getElementById('validationSummary').classList.add('hidden');
    document.getElementById('errorList').innerHTML = '';
    document.querySelectorAll('.error-message').forEach(el => {
      el.classList.remove('show');
      el.textContent = '';
      // remove error border to form-field
      const formField = el.closest('.form-field');
      if (formField) {
        formField.classList.remove('error-border');
      }
    });
  }

  getFormData() {
    const formData = new FormData(this.form);
    // Include disabled fields (needed for proper form submission)
    // Backend validation will prevent unauthorized changes
    this.form.querySelectorAll('input[disabled], select[disabled]').forEach(field => {
      if (field.type !== 'hidden') formData.set(field.name, field.value);
    });
    return formData;
  }

  async pydanticVerification(formData) {
    const formDataObject = Object.fromEntries(formData.entries());
    formDataObject['is_RTE'] = formDataObject['is_RTE'] === 'true';

    try {
      const resp = await fetch('/api/pydantic_verification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formDataObject)
      });
      const data = await resp.json();
      if (!resp.ok) {
        this.displayValidationErrors(data.errors);
        return { ok: false, pydanticData: data };
      }

      return { ok: true, pydanticData: data };
    } catch (err) {
      this.showAlert(404, 'An error occurred while verifying the form data.');
      console.error('Error:', err);
      return { ok: false, pydanticData: null };
    }
  }

  displayValidationErrors(errors) {
    errors.forEach(error => {
      const field = document.getElementById(error.field);
      if (!field) return;
      const formField = field.closest('.form-field');
      if (field) {
        const errorEl = formField.querySelector('.error-message');
        if (errorEl) {
          errorEl.classList.add('show');
          errorEl.textContent = error.message;
          formField.classList.add('error-border');
        }
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

  async submitForm(verifiedData) {
    try {

      let endpoint, payload;
      const base64Image = await this.prepareImage();
      if (this.mode === 'add') {
        endpoint = '/api/add_student';
        payload = { image: base64Image, verifiedData };
      } else if (this.mode === 'edit') {
        endpoint = '/api/update_student';
        payload = { student_id: this.studentId, image: base64Image, image_status: this.avatarUploader?.getStatus() || 'unchanged', verifiedData };
      } else {
        this.showAlert(400, "Invalid Operation! Relode the page and try again.");
        if (this.mode === 'add') closeStudentModal();
        return;
      }

      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (!resp.ok) {
        this.renderValidationErrors(data);

        if (this.mode === 'add') closeStudentModal();
        return;
      }
      this.showAlert(resp.status, data.message);
      if (this.mode === 'add') {
        closeStudentModal();
        this.showAdmissionDoneModal(data.student_id);
      }

    } catch (error) {
      this.showAlert(400, 'Unexpected error occurred!');
      console.error('Error:', error);
    } finally {
      if (this.mode === 'add') {
        const finalSubmitBtn = document.getElementById('finalSubmit');
        if (finalSubmitBtn) {
          finalSubmitBtn.disabled = false;
          finalSubmitBtn.textContent = 'Confirm';
        }
      }
    }
  }

  renderValidationErrors(errorData) {
    let errorMessages = [];
    const errorList = document.getElementById('errorList');
    errorList.innerHTML = '';

    errorData.forEach(error => {
      const li = document.createElement('li');
      li.textContent = error.message;
      errorList.appendChild(li);
      errorMessages.push(error.message);

      this.showAlert(400, error.message || 'Conflict found');

      if (error.field) {
        // Show error below the input field
        const field = document.getElementById(error.field);
        if (field) {
          const formField = field.closest('.form-field');
          if (formField) {
            let errorEl = formField.querySelector('.error-message');
            if (errorEl) {
              errorEl.textContent = error.message;
              errorEl.classList.add('show');
              formField.classList.add('error-border');
            }
          }
        }
      }

    });

    document.getElementById('validationSummary').classList.remove('hidden');
  }

  async prepareImage() {
    if (this.mode === 'add') {
      const blob = this.avatarUploader?.getBlob?.();
      return blob ? await this.convertBlobToBase64(blob) : null;
    } else {
      const status = this.avatarUploader?.getStatus?.();
      if (status === 'updated') {
        const blob = this.avatarUploader?.getBlob?.();
        return blob ? await this.convertBlobToBase64(blob) : null;
      }
      return null;
    }
  }

  openVerificationModal(verifiedData) {
    if (window.loadAdmissionPreview) {
      window.loadAdmissionPreview(verifiedData, this.avatarUploader?.getBlob?.());
    }
  }

  showAdmissionDoneModal(studentId) {
    document.getElementById('successModal').classList.remove('hidden');
    document.body.classList.add('overflow-hidden');
    document.getElementById('sendWhatsAppBTN').onclick = () => sendMessage(studentId);
    document.getElementById('printFormBTN').onclick = () => printAdmissionForm(studentId);
  }

  closeModal(modalID) {
    document.getElementById(modalID).classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
  }


  convertBlobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  formatAadharNumber(input) {
    let value = input.value.replace(/\D/g, '');
    if (value.length <= 12) {
      value = value.replace(/(\d{4})(\d{1,4})/, '$1-$2');
      value = value.replace(/(\d{4})(\d{1,4})/, '$1-$2');
      value = value.replace(/(\d{4})(\d{1,4})$/, '$1-$2');
    }
    input.value = value;
  }

  attachDateMask(selector, format) {
    const el = document.querySelector(selector);
    if (!el) return;
    el.addEventListener('input', e => {
      let value = e.target.value;
      let numbers = value.replace(/\D/g, '').slice(0, 8);
      let newValue = '';
      if (format === 'DD-MM-YYYY') {
        if (numbers.length >= 5) newValue = `${numbers.slice(0, 2)}-${numbers.slice(2, 4)}-${numbers.slice(4)}`;
        else if (numbers.length >= 3) newValue = `${numbers.slice(0, 2)}-${numbers.slice(2)}`;
        else newValue = numbers;
      }
      if (newValue !== value) e.target.value = newValue;
    });
  }

  showAlert(status, message) {
    // Assuming showAlert is defined elsewhere, e.g., in a global script
    if (typeof showAlert === 'function') showAlert(status, message);
  }
}

// Initialize on DOM load
let globalFormManager = null;
document.addEventListener('DOMContentLoaded', () => {
  globalFormManager = new StudentFormManager();
  globalFormManager.init();

  // Expose finalSubmitAdmission function globally for modal button
  if (globalFormManager.mode === 'add') {
    window.finalSubmitAdmission = function () {
      const finalSubmitBtn = document.getElementById('finalSubmit');
      if (finalSubmitBtn) {
        globalFormManager.handleFinalSubmit({
          preventDefault() { }
        });
      }
    };
  }
});