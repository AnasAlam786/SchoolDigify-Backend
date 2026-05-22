import StudentFormManager from './studentFormManager.js';

document.addEventListener('DOMContentLoaded', () => {
  const globalFormManager = new StudentFormManager();
  globalFormManager.init();

  if (globalFormManager.mode === 'add') {
    window.finalSubmitAdmission = function () {
      const finalSubmitBtn = document.getElementById('finalSubmit');
      if (finalSubmitBtn) {
        globalFormManager.handleFinalSubmit({ preventDefault() {} });
      }
    };
  }
});
