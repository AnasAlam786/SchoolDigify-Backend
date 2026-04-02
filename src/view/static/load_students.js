// Load students data on page mount
document.addEventListener('DOMContentLoaded', function() {
    loadStudentsData();
});

function addSkeletonLoaders(count = 12) {
    const container = document.getElementById('StudentData');
    container.innerHTML = ''; // Clear existing content
    
    for (let i = 0; i < count; i++) {
        const skeleton = document.createElement('div');
        skeleton.className = 'student-card skeleton-card overflow-hidden';
        skeleton.innerHTML = `
            <div class="flex items-center justify-between px-3 py-0.5 bg-gray-800 bg-opacity-40 border-b border-gray-700">
                <div class="flex space-x-1 p-1">
                    <div class="bg-gray-700 h-5 w-8 rounded animate-pulse"></div>
                </div>
                <div class="flex items-center space-x-2">
                    <div class="h-8 w-8 rounded-full bg-gray-700 animate-pulse"></div>
                    <div class="h-8 w-8 rounded-full bg-gray-700 animate-pulse"></div>
                </div>
            </div>
            
            <div class="p-4">
                <div class="flex items-start">
                    <div class="relative mr-4 flex-shrink-0">
                        <div class="student-image bg-gray-700 animate-pulse"></div>
                        <div class="absolute -bottom-0 -right-1 roll-badge rounded-full w-8 h-8 bg-gray-700 animate-pulse"></div>
                    </div>
                    
                    <div class="flex-1 min-w-0">
                        <div class="h-6 bg-gray-700 rounded mb-2 animate-pulse"></div>
                        <div class="h-5 bg-gray-700 rounded mb-2 w-3/4 animate-pulse"></div>
                        <div class="h-8 bg-gray-700 rounded mb-2 w-1/2 animate-pulse"></div>
                        <div class="h-4 bg-gray-700 rounded mb-2 w-1/3 animate-pulse"></div>
                        <div class="h-8 bg-gray-700 rounded w-2/3 animate-pulse"></div>
                    </div>
                </div>
            </div>
            
            <div class="grid grid-cols-2 border-t border-gray-700 mt-auto">
                <div class="h-12 bg-gray-700 animate-pulse"></div>
                <div class="h-12 bg-gray-700 animate-pulse"></div>
            </div>
        `;
        container.appendChild(skeleton);
    }
}

async function loadStudentsData() {
    try {
        // Show skeleton loaders while fetching
        addSkeletonLoaders();
        
        // Fetch student data from API
        const response = await fetch('/api/get_students_data');
        
        if (!response.ok) {
            throw new Error('Failed to fetch student data');
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
            // Update stats if they exist
            if (result.stats) {
                renderStats(result.stats);
            }
            
            renderStudents(result.students);
            
            // Set global variables for search/filter/sort functionality
            window.studentsData = result.students;
            window.createStudentCard = createStudentCard;
            
            // Apply initial filters after data is loaded
            if (window.applyFilters) window.applyFilters();
        } else {
            showNoDataMessage();
        }
    } catch (error) {
        console.error('Error loading students:', error);
        showErrorMessage();
    }
}

function renderStats(stats) {
    const statsContainer = document.getElementById('statsContainer');
    if (!statsContainer) return;

    const increColor = stats.increased_students > 0 ? 'text-green-500' : 'text-red-500';
    const growthColor = stats.new_students_growth_percentage > 0 ? 'text-green-500' : 'text-red-500';
    const growthArrow = stats.new_students_growth_percentage > 0 ? 'fas fa-arrow-up' : 'fas fa-arrow-down';

    statsContainer.innerHTML = `
        <div id="statsAccordion" class="flex justify-between items-center bg-gradient-to-br from-[#1a1a2e] to-[#16213e] rounded-xl p-3 cursor-pointer shadow-md transition-all duration-300 hover:from-[#16213e] hover:to-[#0f3460] hover:border-[#4361ee] hover:shadow-xl">
            <h2 class="flex items-center text-[#8f94fb] font-semibold text-lg"><i class="fas fa-chart-line mr-3 text-xl"></i> Student Statistics Overview</h2>
            <span class="accordion-icon text-[#8f94fb] transition-transform duration-300"><i class="fas fa-chevron-down"></i></span>
        </div>
        <div class="accordion-content overflow-hidden transition-all duration-500 ease-in-out mt-4 max-h-0">
            <div class="pb-4">
                <div class="grid gap-6 justify-center" style="grid-template-columns: repeat(auto-fit, minmax(200px, 420px));">
                    <div class="stat-card relative w-full bg-gradient-to-br from-[#1e1e1e] to-[#2a2a2a] rounded-2xl p-6 shadow-md hover:shadow-xl hover:-translate-y-1.5 hover:border-[#4361ee] transition-all duration-300 overflow-hidden">
                        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#4e54c8] to-[#8f94fb]"></div>
                        <div class="stat-icon w-12 h-12 flex items-center justify-center rounded-full bg-[#4f54c820] text-[#8f94fb] text-2xl mb-4"><i class="fas fa-user-plus"></i></div>
                        <h3 class="stat-title text-[#a0a7ff] font-medium mb-2 text-lg">Total Students</h3>
                        <div class="stat-value text-white text-3xl font-bold mb-2">${stats.total_students}</div>
                        <div class="stat-meta flex items-center font-bold text-sm mb-4 ${increColor}"><span>${stats.increased_students > 0 ? '+' : ''}${stats.increased_students} students YoY</span><i class="fas fa-chart-line ml-2"></i></div>
                        <ul class="stat-details text-[#8a92b2] text-sm border-t border-[#333] pt-4 space-y-2">
                            <li class="flex justify-between"><span>New Admissions:</span> <span class="text-white font-medium">${stats.new_students}</span></li>
                            <li class="flex justify-between"><span>Old Students:</span> <span class="text-white font-medium">${stats.old_students}</span></li>
                        </ul>
                    </div>
                    <div class="stat-card relative w-full bg-gradient-to-br from-[#1e1e1e] to-[#2a2a2a] rounded-2xl p-6 shadow-md hover:shadow-xl hover:-translate-y-1.5 hover:border-[#4361ee] transition-all duration-300 overflow-hidden">
                        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#4e54c8] to-[#8f94fb]"></div>
                        <div class="stat-icon w-12 h-12 flex items-center justify-center rounded-full bg-[#4f54c820] text-[#8f94fb] text-2xl mb-4"><i class="fas fa-chart-bar"></i></div>
                        <h3 class="stat-title text-[#a0a7ff] font-medium mb-2 text-lg">Student Growth</h3>
                        <div class="stat-value text-white text-3xl font-bold mb-2">${stats.total_growth_percentage !== null ? (stats.total_growth_percentage > 0 ? '+' : '') + stats.total_growth_percentage.toFixed(1) : 'N/A'}%</div>
                        <div class="stat-meta flex items-center text-sm font-bold ${growthColor} mb-4"><span>${stats.new_students_growth_percentage !== null ? (stats.new_students_growth_percentage > 0 ? '+' : '') + stats.new_students_growth_percentage.toFixed(1) : 'N/A'}% from last year</span><i class="f ml-2 ${growthArrow}"></i></div>
                        <ul class="stat-details text-[#8a92b2] text-sm border-t border-[#333] pt-4 space-y-2">
                            <li class="flex justify-between"><span>Last Year New Admissions:</span> <span class="text-white font-medium">${stats.new_students_prev}</span></li>
                            <li class="flex justify-between"><span>Last Year Students:</span> <span class="text-white font-medium">${stats.previous_year_students_total}</span></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    `;

    const header = document.getElementById('statsAccordion');
    const content = header.nextElementSibling;
    const icon = header.querySelector('.accordion-icon');
    header.addEventListener('click', () => {
        const isOpen = content.style.maxHeight && content.style.maxHeight !== "0px";
        content.style.maxHeight = isOpen ? "0" : content.scrollHeight + "px";
        icon.classList.toggle('rotate-180');
    });
}

function renderStudents(students) {
    const container = document.getElementById('StudentData');
    
    if (!students || students.length === 0) {
        showNoDataMessage();
        return;
    }
    
    container.innerHTML = '';
    
    students.forEach(student => {
        const studentCard = createStudentCard(student);
        container.appendChild(studentCard);
    });
}

function createStudentCard(student) {
    const card = document.createElement('div');
    card.className = 'student-card overflow-hidden';
    card.setAttribute('data-name', student.STUDENTS_NAME);
    card.setAttribute('data-class', student.CLASS);
    card.setAttribute('data-father', student.FATHERS_NAME);
    card.setAttribute('data-PEN', student.PEN);
    card.setAttribute('data-roll', student.ROLL);
    card.setAttribute('data-status', student.student_status);
    
    // Detect new admission based on admission number matching current session
    // This logic should match the backend logic in get_students_data_api.py
    const currentSession = student.ADMISSION_SESSION;
    const isAdmissionFromCurrentSession = student.ADMISSION_NO && 
        String(student.ADMISSION_NO).startsWith(String(currentSession).slice(-2));
    student.is_new = isAdmissionFromCurrentSession;
    
    const imageUrl = student.IMAGE 
        ? `https://lh3.googleusercontent.com/d/${student.IMAGE}=s200`
        : (student.GENDER.toLowerCase() === 'male' 
            ? '/static/no-student-boy-image.png'
            : '/static/no-student-girl-image.png');
    
    const rteTag = student.is_RTE ? '<span class="bg-yellow-500 text-gray-900 text-[9px] font-bold px-1.5 py-[2px] rounded">RTE</span>' : '';
    const newTag = student.student_status === 'new' ? '<span class="bg-blue-500 text-[9px] font-bold px-1.5 py-[2px] rounded">NEW</span>' : '';
    const aadhaarTag = (!student.AADHAAR || student.AADHAAR === '' || student.AADHAAR === '999999999999') 
        ? '<span class="bg-red-500 text-[9px] font-bold px-1.5 py-[2px] rounded">No Aadhaar</span>' 
        : '';
    const penTag = (!student.PEN || student.PEN === '' || student.PEN === '999999999999') 
        ? '<span class="bg-orange-500 text-[9px] font-bold px-1.5 py-[2px] rounded">No PEN</span>' 
        : '';
    
    card.innerHTML = `
        <!-- TOP BAR -->
        <div class="flex items-center justify-between px-3 py-0.5 bg-gray-800 bg-opacity-40 border-b border-gray-700">
            <!-- LEFT: Badges -->
            <div class="flex space-x-1 p-1">
                ${rteTag}
                ${newTag}
                ${aadhaarTag}
                ${penTag}
            </div>

            <!-- RIGHT: Quick Actions + Menu -->
            <div class="flex items-center space-x-2">
                <!-- VIEW ICON -->
                <button onclick="viewStudentDetails('${student.id}', '${student.PHONE}')"
                        class="relative group p-1.5 hover:bg-gray-700 rounded-full">
                    <i class="fas fa-eye text-blue-400 text-lg"></i>
                    <span class="absolute right-1/2 translate-x-1/2 -top-7 hidden group-hover:block 
                                bg-black text-white text-xs px-2 py-1 rounded shadow-lg">
                        View
                    </span>
                </button>

                <!-- EDIT ICON -->
                <button onclick="window.location.href='/update_student/${student.id}'"
                        class="relative group p-1.5 hover:bg-gray-700 rounded-full">
                    <i class="fas fa-edit text-green-400 text-lg"></i>
                    <span class="absolute right-1/2 translate-x-1/2 -top-7 hidden group-hover:block 
                                bg-black text-white text-xs px-2 py-1 rounded shadow-lg">
                        Edit
                    </span>
                </button>
            </div>
        </div>

        <!-- Student Card Content -->
        <div class="p-4">
            <div class="flex items-start">
                <!-- Student Image on LEFT -->
                <div class="relative mr-4 flex-shrink-0">
                    <img src="${imageUrl}" alt="Student Image" class="student-image" loading="lazy">
                    <div class="absolute -bottom-0 -right-1 roll-badge rounded-full w-8 h-8 flex items-center justify-center border-2 border-gray-800">
                        <span class="text-xl font-bold text-white">${student.ROLL}</span>
                    </div>
                </div>

                <!-- Student Details on RIGHT -->
                <div class="flex-1 min-w-0">
                    <h3 class="text-xl font-bold text-blue-400 mb-0 truncate">
                        <a class="cursor-pointer hover:text-blue-300"
                            onclick="viewStudentDetails('${student.id}', '${student.PHONE}')">${student.STUDENTS_NAME}</a>
                    </h3>
                    <p class="text-gray-400 text-md mb-2 truncate">C/O ${student.FATHERS_NAME}</p>

                    <!-- Larger class badge -->
                    <div class="bg-blue-900 bg-opacity-50 text-blue-400 px-2 py-1 rounded text-base font-medium mb-1 inline-block">
                        ${student.CLASS}
                    </div>

                    <div class="text-gray-400 text-sm truncate mb-2">
                        <span class="text-lg">🎂</span>
                        ${student.DOB}
                    </div>

                    <!-- Contact -->
                    <a href="tel:${student.PHONE}" class="phone-badge">
                        <i class="fas fa-phone text-blue-400 mr-2"></i>
                        <span class="text-white text-sm font-semibold">${student.PHONE}</span>
                    </a>
                </div>
            </div>
        </div>

        <!-- Action Buttons at Bottom -->
        <div class="grid grid-cols-2 border-t border-gray-700 mt-auto">
            <button
                class="action-button bg-blue-800 bg-opacity-20 text-blue-400 hover:text-white hover:bg-[rgba(67,97,238,0.2)] rounded-bl-lg"
                onclick="viewStudentDetails('${student.id}', '${student.PHONE}')">
                <i class="fas fa-user-circle mr-2"></i> Details
            </button>
            <button
                class="action-button bg-green-800 bg-opacity-20 text-green-400 hover:bg-[rgba(65,233,135,0.2)] hover:text-white rounded-br-lg"
                onclick="openDrawer('${student.student_session_id}', '${student.PHONE}')">
                <i class="fa-solid fa-indian-rupee-sign mr-2"></i> Pay Fees
            </button>
        </div>
    `;
    
    return card;
}

function showNoDataMessage() {
    const container = document.getElementById('StudentData');
    container.innerHTML = `
        <div class="col-span-3">
            <div class="bg-yellow-900 bg-opacity-30 border border-yellow-700 rounded-xl p-6 text-center">
                <i class="fas fa-exclamation-triangle text-yellow-500 text-4xl mb-4"></i>
                <h3 class="text-xl font-bold text-white mb-2">No Students Found</h3>
                <p class="text-gray-400">Try adjusting your search criteria or add new students</p>
            </div>
        </div>
    `;
}

function showErrorMessage() {
    const container = document.getElementById('StudentData');
    container.innerHTML = `
        <div class="col-span-3">
            <div class="bg-red-900 bg-opacity-30 border border-red-700 rounded-xl p-6 text-center">
                <i class="fas fa-exclamation-circle text-red-500 text-4xl mb-4"></i>
                <h3 class="text-xl font-bold text-white mb-2">Error Loading Data</h3>
                <p class="text-gray-400">Failed to load student data. Please try refreshing the page.</p>
            </div>
        </div>
    `;
}
