import { handleSubmit, handleFinalSubmit } from './submit.js';

export function bindEventListeners(manager) {
  if (manager.submitBtn) {
    manager.submitBtn.addEventListener('click', e => handleSubmit(manager, e));
  }

  if (manager.mode === 'add') {
    const finalSubmitBtn = document.getElementById('finalSubmit');
    if (finalSubmitBtn) {
      finalSubmitBtn.addEventListener('click', e => handleFinalSubmit(manager, e));
    }

    document.querySelectorAll('.cancelModal').forEach(el => {
      el.addEventListener('click', () => {
        if (typeof closeStudentModal === 'function') {
          closeStudentModal();
        }
      });
    });
  }
}
