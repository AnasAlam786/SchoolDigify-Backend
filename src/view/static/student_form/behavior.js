import { attachDateMask, calculateAge, formatAadharNumber, getSuggestedClass } from './utils.js';

export function initAadharFormatting() {
  ['AADHAAR', 'FATHERS_AADHAR', 'MOTHERS_AADHAR'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', () => formatAadharNumber(el));
    }
  });
}

export function initDateMasks() {
  attachDateMask('#DOB', 'DD-MM-YYYY');
  attachDateMask('#ADMISSION_DATE', 'DD-MM-YYYY');
  initAgeCalculation();
}

export function initAgeCalculation() {
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
      const age = calculateAge(value);
      ageDisplay.textContent = `Age: ${age} years`;
      updateClassSuggestion(age);
    } else {
      ageDisplay.textContent = '';
      updateClassSuggestion(null);
    }
  };

  dobEl.addEventListener('input', updateDisplays);

  if (dobEl.value) {
    updateDisplays();
  }
}

export function initRteToggle() {
  const rteCheckbox = document.getElementById('is_RTE');
  const rteFields = document.getElementById('rteFields');
  if (rteCheckbox && rteFields) {
    rteCheckbox.addEventListener('change', () => {
      rteFields.classList.toggle('hidden', !rteCheckbox.checked);
    });
  }
}

function updateClassSuggestion(age) {
  const classEl = document.getElementById('CLASS');
  if (!classEl) return;

  let suggestionEl = classEl.parentNode.querySelector('.class-suggestion');
  if (!suggestionEl) {
    suggestionEl = document.createElement('div');
    suggestionEl.className = 'class-suggestion text-sm text-blue-400 mt-1';
    classEl.parentNode.insertBefore(suggestionEl, classEl.nextSibling);
  }

  suggestionEl.textContent = age !== null ? `Suggested class: ${getSuggestedClass(age)}` : '';
}
