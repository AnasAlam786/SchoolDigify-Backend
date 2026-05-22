import { initAadharFormatting, initDateMasks, initRteToggle } from './behavior.js';
import { initClassRollLogic } from './roll.js';
import { bindEventListeners } from './events.js';

export default class StudentFormManager {
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
    const uniqueSuffix = `_${this.mode}_${this.studentId}`;
    this.avatarUploader = new ImageUploader(uniqueSuffix);
    this.avatarUploader.onChange((blob, status) => console.log('Avatar:', status, blob));
  }

  initFormBehaviors() {
    initAadharFormatting();
    initDateMasks();
    initRteToggle();
    initClassRollLogic(this);
  }

  initEventListeners() {
    bindEventListeners(this);
  }
}
