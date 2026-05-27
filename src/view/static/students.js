const studentData = document.getElementById('StudentData');

/*
  Student Search / Filter / Sort Engine
  ------------------------------------
  Requirements:
  - window.studentsData = [...]  (array)
  - window.createStudentCard(student) function
  - <div id="StudentData"></div>
*/

(function () {
  "use strict";

  /* ===================== DOM ===================== */
  const studentsContainer = document.getElementById("StudentData");

  // Desktop elements
  const searchInput   = document.getElementById("search-input");
  const searchIn      = document.getElementById("search-in");
  const classView     = document.getElementById("classView");
  const sortBy        = document.getElementById("sort-by");
  const sortDir       = document.getElementById("sort-dir");

  const filterRTE     = document.getElementById("filter-rte");
  const filterPEN     = document.getElementById("filter-pen");
  const filterGender  = document.getElementById("filter-gender");
  const filterNewAdmission = document.getElementById("filter-new-admission");

  const clearBtn      = document.getElementById("clear-filters");

  // Mobile elements
  const searchInputMobile   = document.getElementById("search-input-mobile");
  const searchInMobile      = document.getElementById("search-in-mobile");
  const classViewMobile     = document.getElementById("classView-mobile");
  const sortByMobile        = document.getElementById("sort-by-mobile");
  const sortDirMobile       = document.getElementById("sort-dir-mobile");

  const filterRTEMobile     = document.getElementById("filter-rte-mobile");
  const filterPENMobile     = document.getElementById("filter-pen-mobile");
  const filterGenderMobile  = document.getElementById("filter-gender-mobile");
  const filterNewAdmissionMobile = document.getElementById("filter-new-admission-mobile");

  const clearBtnMobile      = document.getElementById("clear-filters-mobile");

  // Counter elements
  const visibleCountEl = document.getElementById("visible-count");
  const totalCountEl   = document.getElementById("total-count");
  const visibleCountMobileEl = document.getElementById("visible-count-mobile");
  const totalCountMobileEl   = document.getElementById("total-count-mobile");

  // Removed initial check since data loads asynchronously
  // Will be called after data is loaded

  /* ===================== HELPERS ===================== */

  const norm = v => v === null || v === undefined ? "" : String(v).toLowerCase();

  function debounce(fn, delay = 180) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), delay);
    };
  }

  /* ===================== SEARCH ===================== */

  const GLOBAL_FIELDS = [
    "STUDENTS_NAME",
    "FATHERS_NAME",
    "SR",
    "ROLL",
    "PHONE",
    "AADHAAR",
    "PEN"
  ];

  function fieldMatch(student, field, token) {
    const value = norm(student[field]);
    if (!value) return false;

    // numeric-aware behavior
    if (field === "ROLL") {
      return String(student.ROLL) === token || value.endsWith(token);
    }

    if (field === "PHONE" || field === "AADHAAR") {
      return value.endsWith(token) || value.includes(token);
    }

    return value.includes(token);
  }

  function matchesSearch(student) {
    const q = norm(searchInput.value);
    if (!q) return true;

    const tokens = q.split(/\s+/);
    const field = searchIn.value;

    return tokens.every(token => {
      if (field !== "all") {
        return fieldMatch(student, field, token);
      }
      return GLOBAL_FIELDS.some(f => fieldMatch(student, f, token));
    });
  }

  /* ===================== FILTERS ===================== */

  function matchesFilters(student) {

    if (classView.value !== "All" &&
        String(student.CLASS) !== classView.value) {
      return false;
    }

    if (filterRTE.checked && !student.is_RTE) {
      return false;
    }

    if (filterPEN.value === "present" &&
        (!student.PEN || String(student.PEN).trim() === "")) {
      return false;
    }

    if (filterPEN.value === "missing" &&
        student.PEN && String(student.PEN).trim() !== "") {
      return false;
    }

    if (filterGender.value !== "any" &&
        norm(student.GENDER) !== filterGender.value) {
      return false;
    }

    // New Admission Filter
    if (filterNewAdmission.value !== "any" && 
        student.student_status !== filterNewAdmission.value) {
      return false;
    }

    return true;
  }

  /* ===================== SORTING ===================== */

  function defaultSort(a, b) {
    const da = parseInt(a.display_order);
    const db = parseInt(b.display_order);

    if (!isNaN(da) && !isNaN(db) && da !== db) {
      return da - db;
    }

    // Then by roll
    const ra = parseInt(a.ROLL);
    const rb = parseInt(b.ROLL);
    if (!isNaN(ra) && !isNaN(rb)) {
      return ra - rb;
    }

    return String(a.ROLL).localeCompare(String(b.ROLL));
  }

  const SORTERS = {
    "STUDENTS_NAME": (a, b) =>
      String(a.STUDENTS_NAME).localeCompare(String(b.STUDENTS_NAME)),
    "ADMISSION_DATE": (a, b) =>
      new Date(b.ADMISSION_DATE) - new Date(a.ADMISSION_DATE),
    "ADMISSION_NO": (a, b) =>
      String(a.ADMISSION_NO).localeCompare(String(b.ADMISSION_NO)),
    "DOB": (a, b) =>
      new Date(a.DOB) - new Date(b.DOB)
  };

  function applySorting(list) {
    const key = sortBy.value;
    const dir = sortDir.value === "desc" ? -1 : 1;

    if (!key) {
      return list.sort(defaultSort);
    }

    return list.sort((a, b) => {
      const r = SORTERS[key](a, b);
      return r === 0 ? defaultSort(a, b) : r * dir;
    });
  }

  /* ===================== RENDER ===================== */

  function render(list) {
    studentsContainer.innerHTML = "";

    if (!list.length) {
      studentsContainer.innerHTML =
        '<div class="text-gray-400 p-4">No students found</div>';
      return;
    }

    const frag = document.createDocumentFragment();
    list.forEach(s => frag.appendChild(createStudentCard(s)));
    studentsContainer.appendChild(frag);
  }

  /* ===================== MAIN ===================== */

  function updateCounter(visibleCount, totalCount) {
    if (visibleCountEl) visibleCountEl.textContent = visibleCount;
    if (totalCountEl) totalCountEl.textContent = totalCount;
    if (visibleCountMobileEl) visibleCountMobileEl.textContent = visibleCount;
    if (totalCountMobileEl) totalCountMobileEl.textContent = totalCount;
  }

  function applyFilters() {
    let result = window.studentsData
      .filter(matchesSearch)
      .filter(matchesFilters);

    result = applySorting(result);
    render(result);
    
    // Update counter
    updateCounter(result.length, window.studentsData?.length || 0);
  }

  /* ===================== EVENTS ===================== */

  // Desktop events
  searchInput.addEventListener("input", debounce(applyFilters));
  searchIn.addEventListener("change", applyFilters);
  classView.addEventListener("change", applyFilters);
  sortBy.addEventListener("change", applyFilters);
  sortDir.addEventListener("change", applyFilters);
  filterRTE.addEventListener("change", applyFilters);
  filterPEN.addEventListener("change", applyFilters);
  filterGender.addEventListener("change", applyFilters);
  filterNewAdmission.addEventListener("change", applyFilters);

  clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    searchIn.value = "all";
    classView.value = "All";
    sortBy.value = "";
    sortDir.value = "asc";
    filterRTE.checked = false;
    filterPEN.value = "any";
    filterGender.value = "any";
    filterNewAdmission.value = "any";
    applyFilters();
  });

  // Mobile events - sync to desktop
  if (searchInputMobile) {
    searchInputMobile.addEventListener("input", debounce((e) => {
      searchInput.value = e.target.value;
      applyFilters();
    }));
  }
  if (searchInMobile) {
    searchInMobile.addEventListener("change", (e) => {
      searchIn.value = e.target.value;
      applyFilters();
    });
  }
  if (classViewMobile) {
    classViewMobile.addEventListener("change", (e) => {
      classView.value = e.target.value;
      applyFilters();
    });
  }
  if (sortByMobile) {
    sortByMobile.addEventListener("change", (e) => {
      sortBy.value = e.target.value;
      applyFilters();
    });
  }
  if (sortDirMobile) {
    sortDirMobile.addEventListener("change", (e) => {
      sortDir.value = e.target.value;
      applyFilters();
    });
  }
  if (filterRTEMobile) {
    filterRTEMobile.addEventListener("change", (e) => {
      filterRTE.checked = e.target.checked;
      applyFilters();
    });
  }
  if (filterPENMobile) {
    filterPENMobile.addEventListener("change", (e) => {
      filterPEN.value = e.target.value;
      applyFilters();
    });
  }
  if (filterGenderMobile) {
    filterGenderMobile.addEventListener("change", (e) => {
      filterGender.value = e.target.value;
      applyFilters();
    });
  }
  if (filterNewAdmissionMobile) {
    filterNewAdmissionMobile.addEventListener("change", (e) => {
      filterNewAdmission.value = e.target.value;
      applyFilters();
    });
  }
  if (clearBtnMobile) {
    clearBtnMobile.addEventListener("click", () => {
      searchInput.value = "";
      searchIn.value = "all";
      classView.value = "All";
      sortBy.value = "";
      sortDir.value = "asc";
      filterRTE.checked = false;
      filterPEN.value = "any";
      filterGender.value = "any";
      filterNewAdmission.value = "any";
      // Also clear mobile
      if (searchInputMobile) searchInputMobile.value = "";
      if (searchInMobile) searchInMobile.value = "all";
      if (classViewMobile) classViewMobile.value = "All";
      if (sortByMobile) sortByMobile.value = "";
      if (sortDirMobile) sortDirMobile.value = "asc";
      if (filterRTEMobile) filterRTEMobile.checked = false;
      if (filterPENMobile) filterPENMobile.value = "any";
      if (filterGenderMobile) filterGenderMobile.value = "any";
      if (filterNewAdmissionMobile) filterNewAdmissionMobile.value = "any";
      applyFilters();
    });
  }

  // Sort direction toggle buttons
  const sortDirToggle = document.getElementById("sort-dir-toggle");
  const sortDirToggleMobile = document.getElementById("sort-dir-toggle-mobile");

  if (sortDirToggle) {
    sortDirToggle.addEventListener("click", () => {
      const current = sortDir.value;
      const newDir = current === "asc" ? "desc" : "asc";
      sortDir.value = newDir;
      sortDirToggle.setAttribute("data-direction", newDir);
      const icon = sortDirToggle.querySelector("#sort-dir-icon");
      if (icon) {
        icon.innerHTML = newDir === "asc" 
          ? '<svg class="w-5 h-5 text-amber-400 group-hover:text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/></svg>'
          : '<svg class="w-5 h-5 text-amber-400 group-hover:text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>';
      }
      applyFilters();
    });
  }

  if (sortDirToggleMobile) {
    sortDirToggleMobile.addEventListener("click", () => {
      const current = sortDir.value;
      const newDir = current === "asc" ? "desc" : "asc";
      sortDir.value = newDir;
      sortDirMobile.value = newDir;
      sortDirToggleMobile.setAttribute("data-direction", newDir);
      const icon = sortDirToggleMobile.querySelector("#sort-dir-icon-mobile");
      if (icon) {
        icon.innerHTML = newDir === "asc" 
          ? '<svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/></svg>'
          : '<svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>';
      }
      applyFilters();
    });
  }

  /* ===================== INIT ===================== */
  // Expose applyFilters globally for async data loading
  window.applyFilters = applyFilters;
})();


// ---------------- Student Modall Code START ----------------

function viewStudentDetails(studentId, phone) {
  try {
    response = updatePage('/student_modal_data_api', 'studentsDetailsModalBody', {student_id: studentId, phone: phone})
    if (!response) {
      console.log("Error fetching student details");
      return;
    }
    openModal()
  }
  catch (error) {
    console.error("Error fetching student details:", error);
    return;
  }
}

function openModal() {
    document.getElementById('studentDetailsModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}


