import { showAlert } from './utils.js';

export function initClassRollLogic(manager) {
  if (manager.mode === 'add' || !manager.hasOtherSessions) {
    setupNewStudentLogic(manager);
  } else {
    setupOldStudentLogic(manager);
  }
}

export function setupNewStudentLogic(manager) {
  const classSelect = document.getElementById('CLASS');
  const admissionSessionSelect = document.getElementById('admission_session_id');
  const admissionClassSelect = document.getElementById('Admission_Class');
  const rollInput = document.getElementById('ROLL');
  const studentStatusRadios = document.querySelectorAll('input[name="student_status"]');
  const checkedStatusRadio = document.querySelector('input[name="student_status"]:checked');

  manager.originalAcademicValues = {
    admissionSession: admissionSessionSelect?.dataset.originalSession || admissionSessionSelect?.value || '',
    admissionClass: admissionClassSelect?.dataset.originalAdmissionClass || admissionClassSelect?.value || '',
    currentClass: classSelect?.dataset.originalCurrentClass || classSelect?.value || '',
    roll: rollInput?.dataset.originalRoll || rollInput?.value || ''
  };

  manager.handleStudentStatusChange = status => handleStudentStatusChange(manager, status);
  manager.handleAdmissionClassChange = () => handleAdmissionClassChange(manager);

  studentStatusRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      manager.handleStudentStatusChange(radio.value);
    });
  });

  if (classSelect) {
    classSelect.addEventListener('change', () => {
      updateRollForClass(manager, classSelect.value);
    });
  }

  if (checkedStatusRadio) {
    manager.handleStudentStatusChange(checkedStatusRadio.value);
  }
}

export function setupOldStudentLogic(manager) {
  const classSelect = document.getElementById('CLASS');
  const admissionSessionSelect = document.getElementById('admission_session_id');
  const admissionClassSelect = document.getElementById('Admission_Class');

  if (classSelect) {
    classSelect.disabled = true;
    const msg = document.createElement('p');
    msg.className = 'text-xs text-red-400';
    msg.textContent = 'You can change the class from Promotions page.';
    classSelect.parentNode.insertBefore(msg, classSelect.nextSibling);
  }

  if (admissionClassSelect?.disabled) {
    admissionClassSelect.title = 'Cannot modify: Student has past academic records';
  }

  if (admissionSessionSelect?.disabled) {
    admissionSessionSelect.title = 'Cannot modify: Student has past academic records';
  }
}

export function handleStudentStatusChange(manager, status) {
  const admissionClassSelect = document.getElementById('Admission_Class');
  const classSelect = document.getElementById('CLASS');
  const admissionSessionSelect = document.getElementById('admission_session_id');
  const rollInput = document.getElementById('ROLL');

  if (status === 'new') {
    const currentSession = admissionSessionSelect?.dataset.currentSession;
    if (currentSession) {
      admissionSessionSelect.value = currentSession;
    }
    if (admissionClassSelect && classSelect) {
      classSelect.value = admissionClassSelect.value;
    }

    if (classSelect) classSelect.disabled = true;
    if (admissionSessionSelect) admissionSessionSelect.disabled = true;

    admissionClassSelect?.removeEventListener('change', manager.handleAdmissionClassChange);
    admissionClassSelect?.addEventListener('change', manager.handleAdmissionClassChange);

    if (classSelect?.value) {
      updateRollForClass(manager, classSelect.value);
    }
  } else {
    if (classSelect) classSelect.disabled = false;
    if (admissionSessionSelect) admissionSessionSelect.disabled = false;
    admissionClassSelect?.removeEventListener('change', manager.handleAdmissionClassChange);

    if (manager.originalAcademicValues) {
      if (admissionSessionSelect && manager.originalAcademicValues.admissionSession) {
        admissionSessionSelect.value = manager.originalAcademicValues.admissionSession;
      }
      if (admissionClassSelect && manager.originalAcademicValues.admissionClass) {
        admissionClassSelect.value = manager.originalAcademicValues.admissionClass;
      }
      if (classSelect && manager.originalAcademicValues.currentClass) {
        classSelect.value = manager.originalAcademicValues.currentClass;
      }
      if (rollInput && manager.originalAcademicValues.roll) {
        rollInput.value = manager.originalAcademicValues.roll;
      }
    }
  }
}

export async function updateRollForClass(manager, classId) {
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
      showAlert(resp.status, result.message);
      return;
    }

    rollInput.value = result.next_roll;
    showRollHint(result.gapped_rolls, result.next_roll);
  } catch (err) {
    console.error('Error fetching next roll:', err);
  }
}

function showRollHint(gappedRolls, nextRoll) {
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
