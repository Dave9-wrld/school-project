const app = document.querySelector('#app');
const sessionKey = 'campus.api-session';
let session = readSession();
let authMode = 'login';
let allGrades = [];
let selectedSession = 'all';
let studentProfile = null;
let adminClasses = [];
let adminStudents = [];
let adminLecturers = [];
let recoveryChallenge = null;

const iconPaths = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  book: '<path d="M12 5c-3-2-7-2-10-1v15c3-1 7-1 10 1 3-2 7-2 10-1V4c-3-1-7-1-10 1Zm0 0v15"/>',
  results: '<path d="M6 3h12v18H6zM9 7h6M9 11h6M9 15h3"/>',
  people: '<circle cx="9" cy="7" r="3"/><path d="M2 21v-3a7 7 0 0 1 14 0v3M17 4a3 3 0 0 1 0 6m2 4a6 6 0 0 1 3 5v2"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  logout: '<path d="M9 4H4v16h5m0-8h12m-5-5 5 5-5 5"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2"/>',
  chart: '<path d="M4 4v16h17M8 16v-4m5 4V8m5 8V4"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',
  refresh: '<path d="M20 9a8 8 0 1 0 0 7M20 3v6h-6"/>',
  edit: '<path d="m4 16 12-12 4 4L8 20H4v-4Zm9-9 4 4"/>',
};
function icon(name) { return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.book}</svg>`; }
function brand() {
  return `<div class="brand"><svg class="crest" viewBox="0 0 56 66" fill="none" aria-hidden="true"><path d="M3 3h50v31c0 15-14 25-25 29C17 59 3 49 3 34V3Z" stroke="currentColor" stroke-width="2"/><path d="M7 7h42v27c0 12-12 21-21 25C19 55 7 46 7 34V7Z" fill="currentColor"/><path d="M28 21c-5-3-10-3-15-1v20c5-2 10-2 15 1 5-3 10-3 15-1V20c-5-2-10-2-15 1Zm0 0v20M17 25h6m-6 5h6m10-5h6m-6 5h6" stroke="#fff" stroke-width="1.5"/><path d="m28 10 1.4 3h3.3L30 15l1 3-3-2-3 2 1-3-2.7-2h3.3Z" fill="#fff"/></svg><div><div class="brand-name">Dave University</div><div class="brand-subtitle">Academic portal</div></div></div>`;
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[char]);
}
function readSession() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(sessionKey) || 'null');
    if (saved?.token && (!saved.expires_at || Date.parse(saved.expires_at) > Date.now())) return saved;
    sessionStorage.removeItem(sessionKey);
  } catch { /* A blocked or unavailable store should not prevent sign-in. */ }
  return null;
}
function saveSession(value) {
  session = value;
  try { sessionStorage.setItem(sessionKey, JSON.stringify(value)); } catch { /* Keep this page's login in memory. */ }
}
function clearSession() {
  session = null;
  allGrades = [];
  selectedSession = 'all';
  studentProfile = null;
  adminClasses = [];
  adminStudents = [];
  adminLecturers = [];
  try { sessionStorage.removeItem(sessionKey); } catch { /* Storage may be unavailable. */ }
}
function apiError(payload, status) {
  if (status >= 500) return 'The portal is temporarily unavailable. Please try again shortly.';
  if (status === 403) return 'Your account does not have access to this service.';
  if (status === 429) return 'Too many attempts. Please wait a moment before trying again.';
  if (payload?.detail || payload?.error) return String(payload.detail || payload.error);
  const entry = payload && typeof payload === 'object' ? Object.entries(payload)[0] : null;
  if (!entry) return 'We could not complete your request. Please try again.';
  const labels = { non_field_errors: '', username: 'Username', password: 'Password', email: 'Email', student: 'Student', subject: 'Course', name: 'Class name', class_teacher: 'Lecturer', current_class: 'Class', continous_assessment_score: 'Continuous assessment', exam_score: 'Examination score' };
  const message = Array.isArray(entry[1]) ? entry[1].join(' ') : String(entry[1]);
  const label = labels[entry[0]] ?? 'Please check your details';
  if (['student', 'subject'].includes(entry[0])) return `Please select a valid ${label.toLowerCase()}.`;
  return label ? `${label}: ${message}` : message;
}
async function api(path, options = {}) {
  const { public: isPublic, ...requestOptions } = options;
  const headers = { Accept: 'application/json', ...requestOptions.headers };
  if (requestOptions.body) headers['Content-Type'] = 'application/json';
  if (session?.token && !isPublic) headers.Authorization = `Token ${session.token}`;
  let response;
  try { response = await fetch(path, { ...requestOptions, headers }); }
  catch { throw new Error('We could not connect. Check your connection and try again.'); }
  const text = await response.text();
  let payload = null;
  try { if (text) payload = JSON.parse(text); } catch { /* HTML errors are not shown to users. */ }
  if (!response.ok) {
    if (response.status === 401 && !isPublic) {
      clearSession(); authMode = 'login';
      renderAuth('Your session has ended. Please sign in again.');
    }
    throw new Error(apiError(payload, response.status));
  }
  return payload;
}
function notice(message, type = 'error') {
  return message ? `<div class="notice${type === 'success' ? ' notice-success' : ''}" role="${type === 'success' ? 'status' : 'alert'}">${escapeHtml(message)}</div>` : '';
}
function passwordField(id, label, autocomplete) {
  return `<div class="field"><label for="${id}">${label}</label><div class="password-wrap"><input class="input" id="${id}" name="${id}" type="password" autocomplete="${autocomplete}" required><button class="show-password" type="button" data-password="${id}" aria-label="Show ${label.toLowerCase()}" aria-pressed="false">Show</button></div></div>`;
}
function renderAuth(message = '', type = 'error', username = '') {
  const registering = authMode === 'register';
  const forgot = authMode === 'forgot';
  const resetting = authMode === 'reset';
  const pageTitle = registering ? 'Create account' : forgot ? 'Password recovery' : resetting ? 'Reset password' : 'Sign in';
  document.title = `${pageTitle} | Dave University`;

  let panelEyebrow = 'University portal';
  let panelTitle = 'Welcome back';
  let panelIntro = 'Students, lecturers and administrators all sign in here with their assigned username and password.';
  let formContent = '';
  let switchContent = '';

  if (registering) {
    panelEyebrow = 'Student registration';
    panelTitle = 'Create your account';
    panelIntro = 'Enter your details to set up your student account. You’ll sign in once registration is complete.';
    formContent = `
      <div class="field-row">
        <div class="field"><label for="first_name">First name</label><input class="input" id="first_name" name="first_name" autocomplete="given-name" maxlength="150" required autofocus></div>
        <div class="field"><label for="last_name">Last name</label><input class="input" id="last_name" name="last_name" autocomplete="family-name" maxlength="150" required></div>
      </div>
      <div class="field"><label for="email">Email address</label><input class="input" id="email" name="email" type="email" autocomplete="email" required></div>
      <div class="field"><label for="username">Username</label><input class="input" id="username" name="username" autocomplete="username" value="${escapeHtml(username)}" maxlength="150" placeholder="Enter your username" required></div>
      <div class="field"><label for="admission_number">Admission number (optional)</label><input class="input" id="admission_number" name="admission_number" maxlength="20" placeholder="Enter your assigned admission number"></div>
      ${passwordField('password', 'Password', 'new-password')}
      ${passwordField('confirm_password', 'Confirm password', 'new-password')}
      <button class="btn" type="submit">Create student account ${icon('arrow')}</button>
    `;
    switchContent = `Already registered? <button class="text-button" type="button" data-auth-mode="login">Sign in</button>`;
  } else if (forgot) {
    panelEyebrow = 'Account recovery';
    panelTitle = 'Forgot password';
    panelIntro = 'Enter your account username and registered email address to receive a 6-digit recovery code.';
    formContent = `
      <div class="field"><label for="username">Username</label><input class="input" id="username" name="username" autocomplete="username" maxlength="150" placeholder="Enter your account username" required autofocus></div>
      <div class="field"><label for="email">Email address</label><input class="input" id="email" name="email" type="email" autocomplete="email" placeholder="you@example.com" required></div>
      <button class="btn" type="submit">Send verification code ${icon('arrow')}</button>
    `;
    switchContent = `<button class="text-button" type="button" data-auth-mode="login">Back to sign in</button>`;
  } else if (resetting) {
    panelEyebrow = 'Account recovery';
    panelTitle = 'Choose new password';
    panelIntro = 'Enter the 6-digit verification code sent to your email along with your desired new password.';
    formContent = `
      <div class="field"><label for="code">Verification code</label><input class="input" id="code" name="code" inputmode="numeric" pattern="[0-9]{6}" minlength="6" maxlength="6" placeholder="6-digit code" required autofocus style="letter-spacing:0.3em;font-size:16px;"></div>
      ${passwordField('new_password', 'New password', 'new-password')}
      ${passwordField('confirm_password', 'Confirm new password', 'new-password')}
      <button class="btn" type="submit">Reset password ${icon('arrow')}</button>
    `;
    switchContent = `<button class="text-button" type="button" data-auth-mode="forgot">Send new code</button> &nbsp;·&nbsp; <button class="text-button" type="button" data-auth-mode="login">Back to sign in</button>`;
  } else {
    panelEyebrow = 'University portal';
    panelTitle = 'Welcome back';
    panelIntro = 'Students, lecturers and administrators all sign in here with their assigned username and password.';
    formContent = `
      <div class="field"><label for="username">Username</label><input class="input" id="username" name="username" autocomplete="username" value="${escapeHtml(username)}" maxlength="150" placeholder="Enter your username" required autofocus></div>
      ${passwordField('password', 'Password', 'current-password')}
      <div style="display:flex;justify-content:flex-end;margin:-4px 0 16px;"><button class="text-button" type="button" data-auth-mode="forgot" style="font-size:12px;cursor:pointer;">Forgot password?</button></div>
      <button class="btn" type="submit">Sign in to portal ${icon('arrow')}</button>
    `;
    switchContent = `New student? <button class="text-button" type="button" data-auth-mode="register">Create student account</button>`;
  }

  app.innerHTML = `<header class="public-masthead">${brand()}<div class="masthead-right"><span>Students · Lecturers · Administrators</span><button class="text-button" type="button" data-auth-mode="${registering ? 'login' : 'register'}">${registering ? 'Back to sign in' : 'New student? Register'}</button></div></header>
    <main class="public-main${registering ? ' register-mode' : ''}">
      <section class="campus-cover" aria-label="Welcome to Dave University"><img src="/static/portal/campus.svg" alt="" width="1000" height="1100"><div class="cover-label">Dave University · Academic services</div><div class="cover-copy"><div class="cover-rule"></div><div class="eyebrow">Knowledge. Opportunity. Growth.</div><h1>Your university.<br>Your journey.<br><em>Your future.</em></h1><p>A home for your academic life. Access your results, manage your courses, and take your next step with confidence.</p></div></section>
      <section class="access-panel" aria-labelledby="access-title"><div class="eyebrow">${panelEyebrow}</div><h2 id="access-title">${panelTitle}</h2><p class="access-intro">${panelIntro}</p>
        <div id="auth-feedback">${notice(message, type)}</div><form id="auth-form">
          ${formContent}
        </form><div class="access-switch">${switchContent}</div><div class="access-note">${icon('lock')}<span>Lecturer and administrator accounts are provided by university administration.</span></div>
      </section>
    </main><footer class="public-footer"><span>© ${new Date().getFullYear()} <strong>Dave University.</strong> Academic services.</span><span>Student · Lecturer · Administration</span></footer>`;
}
function roleLabel(role) { return ({ADMIN:'Administrator',TEACHER:'Lecturer',STUDENT:'Student'})[role] || 'Member'; }
function renderShell() {
  const name = session.display_name || session.username;
  const initials = name.split(/\s+/).map(part => part[0]).slice(0,2).join('').toUpperCase();
  const links = session.role === 'STUDENT' ? `<a class="side-link" href="#academic-record">${icon('results')}My results</a>` : session.role === 'TEACHER' ? `<a class="side-link" href="#courses">${icon('book')}My courses</a><a class="side-link" href="#teacher-classes">${icon('people')}My classes</a><a class="side-link" href="#grade-card">${icon('edit')}Record results</a><a class="side-link" href="#recorded-results">${icon('results')}Recorded results</a>` : `<a class="side-link" href="#institution-summary">${icon('people')}University overview</a><a class="side-link" href="#class-management">${icon('book')}Manage classes</a>`;
  document.title = `${roleLabel(session.role)} portal | Dave University`;
  app.innerHTML = `<div class="portal"><aside class="sidebar">${brand()}<div class="side-heading">Academic services</div><nav aria-label="Portal navigation"><a class="side-link active" href="#dashboard-content">${icon('grid')}Dashboard</a>${links}</nav><div class="sidebar-end"><div class="eyebrow">Dave University</div><p>Learning today.<br>Leading tomorrow.</p></div></aside>
    <div class="portal-main"><header class="portal-topbar"><div class="breadcrumb">Academic portal &nbsp; / &nbsp; <strong>Dashboard</strong></div><div class="topbar-account"><span class="avatar" aria-hidden="true">${escapeHtml(initials)}</span><div class="account-label"><strong>${escapeHtml(name)}</strong><span>${roleLabel(session.role)}</span></div><button class="signout" id="logout" type="button">${icon('logout')}Sign out</button></div></header><main class="dashboard" id="dashboard-content"><div class="loading"><div><div class="spinner"></div>Loading your academic portal…</div></div></main></div></div>`;
}
function welcome(kicker, title, description) {
  const date = new Date().toLocaleDateString('en-GB', {day:'numeric',month:'long',year:'numeric'});
  return `<section class="welcome"><div><div class="eyebrow">${kicker}</div><h1>${escapeHtml(title)}</h1><p>${escapeHtml(description)}</p></div><div class="date-label"><strong>${date}</strong>Dave University</div></section>`;
}
function banner(kicker, title, text, href, buttonText) {
  return `<section class="academic-banner"><div><div class="eyebrow">${kicker}</div><h2>${title}</h2><p>${text}</p></div>${href ? `<a class="btn" href="${href}">${buttonText}${icon('arrow')}</a>` : ''}</section>`;
}
function metric(value, title, note, symbol, suffix = '') {
  return `<article class="metric"><div class="metric-top"><span>${title}</span><span class="metric-icon">${icon(symbol)}</span></div><div class="metric-value">${escapeHtml(value)}${suffix ? `<small>${suffix}</small>` : ''}</div><div class="metric-note">${note}</div></article>`;
}
function footer() { return `<footer class="footer"><span>Dave University · Academic portal</span><span>© ${new Date().getFullYear()} Dave University</span></footer>`; }
function empty(title, text) { return `<div class="empty">${icon('book')}<h3>${title}</h3><p>${text}</p></div>`; }

function renderAdmin(data, classes, lecturers, students, feedback = '') {
  adminClasses = classes;
  adminLecturers = lecturers;
  adminStudents = students;
  const total = data.total_students + data.total_teachers;
  const percent = value => total ? Math.round(value / total * 100) : 0;
  const classOptions = classes.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join('');
  const lecturerOptions = lecturers.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} · ${escapeHtml(item.employee_id || item.username)}</option>`).join('');
  const studentOptions = students.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} · ${escapeHtml(item.admission_number || item.username)}</option>`).join('');
  const classRows = classes.map(item => `<tr><td><strong>${escapeHtml(item.name)}</strong></td><td>${escapeHtml(item.teacher_name || 'Unassigned')}</td><td>${escapeHtml(item.student_count)}</td><td><button class="text-button choose-class" data-class="${escapeHtml(item.id)}" type="button">Manage</button></td></tr>`).join('');
  document.querySelector('#dashboard-content').innerHTML = `${welcome('Administration', 'University overview', 'A summary of the people and courses in your university.')}
    ${banner('Academic administration', 'Put every student in the right class.', 'Create class groups, assign lecturers and place students where they belong.', '#class-management', 'Manage classes')}
    <div class="metrics">${metric(data.total_students,'Students','Registered student accounts','people')}${metric(data.total_teachers,'Lecturers','Teaching staff accounts','people')}${metric(data.total_subjects,'Courses','Courses in the catalogue','book')}</div>
    <div class="admin-grid" id="institution-summary"><section class="panel"><div class="panel-head"><div><h2>University community</h2><p>Students and teaching staff</p></div><button class="btn btn-outline btn-small" id="refresh" type="button">${icon('refresh')}Refresh</button></div><div class="panel-body"><div class="composition-row"><span>Students</span><strong>${data.total_students}</strong></div><div class="composition-bar"><span style="width:${percent(data.total_students)}%"></span></div><div class="composition-row"><span>Lecturers</span><strong>${data.total_teachers}</strong></div><div class="composition-bar blue"><span style="width:${percent(data.total_teachers)}%"></span></div><p class="helper" style="margin-top:24px">${total} student and lecturer accounts in total.</p></div></section><section class="panel"><div class="panel-head"><div><h2>Academic summary</h2><p>Current university records</p></div></div><div class="panel-body"><div class="breakdown"><span>Course catalogue</span><strong>${data.total_subjects} courses</strong></div><div class="breakdown"><span>Class groups</span><strong>${classes.length} classes</strong></div><div class="breakdown"><span>Students without a class</span><strong>${students.filter(item => !item.current_class).length}</strong></div></div></section></div>
    <section id="class-management" class="allocation-section"><div class="allocation-heading"><div><div class="eyebrow">Academic allocation</div><h2 class="serif">Manage classes</h2><p>Create class groups, choose their lecturers and assign students.</p></div><span class="allocation-count">${classes.length} class${classes.length === 1 ? '' : 'es'}</span></div>
      <div id="admin-feedback">${notice(feedback, 'success')}</div>
      <section class="panel"><div class="panel-head"><div><h2>Class directory</h2><p>Current groups and allocations</p></div></div>${classRows ? `<div class="table-scroll"><table class="data-table"><thead><tr><th scope="col">Class</th><th scope="col">Lecturer</th><th scope="col">Students</th><th scope="col">Action</th></tr></thead><tbody>${classRows}</tbody></table></div>` : empty('No classes yet', 'Create your first class below to begin allocating students.')}</section>
      <div class="allocation-forms">
        <section class="panel"><div class="panel-head"><div><h2>Create a class</h2><p>Add a class group to the university</p></div></div><div class="panel-body"><form id="create-class-form"><div class="field"><label for="new-class-name">Class name</label><input class="input" id="new-class-name" name="name" maxlength="20" placeholder="e.g. Year 1 A" required></div><div class="field"><label for="new-class-lecturer">Lecturer (optional)</label><select class="input" id="new-class-lecturer" name="class_teacher"><option value="">Assign later</option>${lecturerOptions}</select></div><button class="btn" type="submit">Create class ${icon('arrow')}</button></form></div></section>
        <section class="panel"><div class="panel-head"><div><h2>Assign a lecturer</h2><p>Choose who leads a class</p></div></div><div class="panel-body"><form id="assign-lecturer-form"><div class="field"><label for="manage-class">Class</label><select class="input" id="manage-class" name="class_id" required ${classes.length ? '' : 'disabled'}><option value="">Select a class</option>${classOptions}</select></div><div class="field"><label for="manage-lecturer">Lecturer</label><select class="input" id="manage-lecturer" name="class_teacher"><option value="">No lecturer assigned</option>${lecturerOptions}</select><p id="selected-class-lecturer" class="helper">Select a class to see its lecturer.</p></div><button class="btn" type="submit" ${classes.length ? '' : 'disabled'}>Save lecturer ${icon('arrow')}</button></form></div></section>
        <section class="panel"><div class="panel-head"><div><h2>Place a student</h2><p>Assign or change a student's class</p></div></div><div class="panel-body"><form id="assign-student-form"><div class="field"><label for="manage-student">Student</label><select class="input" id="manage-student" name="student_id" required ${students.length && classes.length ? '' : 'disabled'}><option value="">Select a student</option>${studentOptions}</select><p id="selected-student-class" class="helper">Select a student to see their current class.</p></div><div class="field"><label for="student-class">Class</label><select class="input" id="student-class" name="current_class"><option value="">No class assigned</option>${classOptions}</select></div><button class="btn" type="submit" ${students.length && classes.length ? '' : 'disabled'}>Save class ${icon('arrow')}</button></form></div></section>
        <section class="panel"><div class="panel-head"><div><h2>Add a lecturer</h2><p>Create a teaching account</p></div></div><div class="panel-body"><form id="create-lecturer-form">
          <div class="field-row"><div class="field"><label for="lecturer-first">First name</label><input class="input" id="lecturer-first" name="first_name" maxlength="150" required></div><div class="field"><label for="lecturer-last">Last name</label><input class="input" id="lecturer-last" name="last_name" maxlength="150" required></div></div>
          <div class="field"><label for="lecturer-username">Username</label><input class="input" id="lecturer-username" name="username" maxlength="150" autocomplete="off" required></div>
          <div class="field"><label for="lecturer-email">Email address</label><input class="input" id="lecturer-email" name="email" type="email" required></div>
          <div class="field"><label for="employee-id">Employee ID (optional)</label><input class="input" id="employee-id" name="employee_id" maxlength="20"></div>
          ${passwordField('password', 'Password', 'new-password')}
          ${passwordField('confirm_password', 'Confirm password', 'new-password')}
          <button class="btn" type="submit">Create lecturer account ${icon('arrow')}</button>
        </form></div></section>
      </div>
    </section>${footer()}`;
}

function recordedResultsTable(grades) {
  const rows = grades.map(item => `<tr><td><strong>${escapeHtml(item.student_name || 'Student')}</strong></td><td class="course-name">${escapeHtml(item.subject_name || 'Course')}</td><td>${escapeHtml(item.session_name || '—')}</td><td>${escapeHtml(item.continous_assessment_score)}</td><td>${escapeHtml(item.exam_score)}</td><td><span class="score">${escapeHtml(item.total_score)}</span></td></tr>`).join('');
  return rows ? `<div class="table-scroll"><table class="data-table"><thead><tr><th scope="col">Student</th><th scope="col">Course</th><th scope="col">Session</th><th scope="col">CA / 40</th><th scope="col">Exam / 60</th><th scope="col">Total / 100</th></tr></thead><tbody>${rows}</tbody></table></div><div class="table-foot">${grades.length} recorded result${grades.length === 1 ? '' : 's'} across your assigned courses.</div>` : empty('No results recorded yet', 'Results for your assigned courses will appear here after you save them.');
}

function renderTeacher(subjects, students, classes, grades) {
  const courseOptions = subjects.map(item => `<option value="${item.id}">${escapeHtml(item.name)} · ${escapeHtml(item.code)}</option>`).join('');
  const studentOptions = students.map(item => `<option value="${item.id}">${escapeHtml(item.name)} · ${escapeHtml(item.admission_number || item.username)}</option>`).join('');
  const rows = subjects.map(item => `<tr><td><strong>${escapeHtml(item.code)}</strong></td><td class="course-name">${escapeHtml(item.name)}</td><td><button class="text-button choose-course" data-subject="${item.id}" type="button">Record result</button></td></tr>`).join('');
  const classRows = classes.map(item => `<tr><td><strong>${escapeHtml(item.name)}</strong></td><td>${escapeHtml(item.student_count)} student${item.student_count === 1 ? '' : 's'}</td></tr>`).join('');
  const canRecord = subjects.length > 0 && students.length > 0;
  document.querySelector('#dashboard-content').innerHTML = `${welcome('Lecturer portal','Teaching & assessment','Manage your assigned courses and record student results.')}
    ${banner('Your teaching desk','Every result is a step forward.','Choose a course and student to record their assessment and examination marks.','#grade-card','Record results')}
    <div class="metrics">${metric(subjects.length,'Assigned courses','Courses you teach','book')}${metric(classes.length,'My classes','Class groups you lead','people')}${metric(students.length,'Student directory','Students available for assessment','results')}</div>
    <div class="lecturer-grid"><div class="lecturer-list"><section class="panel" id="courses"><div class="panel-head"><div><h2>My courses</h2><p>Your current teaching assignments</p></div></div>${rows ? `<div class="table-scroll"><table class="data-table"><thead><tr><th scope="col">Code</th><th scope="col">Course</th><th scope="col">Assessment</th></tr></thead><tbody>${rows}</tbody></table></div>` : empty('No courses assigned','Your courses will appear here once assigned by university administration.')}</section>
    <section class="panel" id="teacher-classes"><div class="panel-head"><div><h2>My classes</h2><p>Groups assigned to you</p></div></div>${classRows ? `<div class="table-scroll"><table class="data-table"><thead><tr><th scope="col">Class</th><th scope="col">Students</th></tr></thead><tbody>${classRows}</tbody></table></div>` : empty('No classes assigned','Your class groups will appear here when university administration assigns them.')}</section></div>
    <section class="panel" id="grade-card"><div class="panel-head"><div><h2>Record a result</h2><p>Current academic session</p></div></div><div class="panel-body"><div id="action-feedback"></div>${!canRecord ? notice(subjects.length ? 'There are no student accounts available for assessment yet.' : 'A course must be assigned to you before you can record results.') : ''}<form id="grade-form"><div class="field"><label for="subject">Course</label><select class="input" id="subject" name="subject" required ${!canRecord ? 'disabled' : ''}><option value="">Select a course</option>${courseOptions}</select></div><div class="field"><label for="student">Student</label><select class="input" id="student" name="student" required ${!canRecord ? 'disabled' : ''}><option value="">Select a student</option>${studentOptions}</select></div><div class="field-row"><div class="field"><label for="ca">Assessment / 40</label><input class="input" id="ca" name="ca" type="number" min="0" max="40" step="0.01" required></div><div class="field"><label for="exam">Examination / 60</label><input class="input" id="exam" name="exam" type="number" min="0" max="60" step="0.01" required></div></div><div class="score-total"><span>Total score</span><strong><output id="score-preview" aria-live="polite">0</output> <small>/ 100</small></strong></div><button class="btn" type="submit" ${!canRecord ? 'disabled' : ''}>Save result ${icon('arrow')}</button><p class="helper" style="margin-top:14px">Saving again replaces this student’s result for the selected course in the current academic session.</p></form></div></section></div>
    <section class="panel recorded-results" id="recorded-results"><div class="panel-head"><div><h2>Recorded results</h2><p>Students you have results for in your assigned courses</p></div></div><div id="recorded-results-content">${recordedResultsTable(grades)}</div></section>${footer()}`;
}

function visibleGrades() { return allGrades.filter(item => selectedSession === 'all' || String(item.session) === selectedSession); }
function renderStudent() {
  const grades = visibleGrades();
  const totals = grades.map(item => Number(item.total_score)).filter(Number.isFinite);
  const average = totals.length ? (totals.reduce((a,b) => a+b,0)/totals.length).toFixed(1) : '—';
  const highest = totals.length ? Math.max(...totals).toFixed(1) : '—';
  const sessions = [...new Map(allGrades.map(item => [String(item.session), item.session_name || 'Academic session'])).entries()].sort((a,b) => b[1].localeCompare(a[1]));
  const choices = sessions.map(([id,label]) => `<option value="${escapeHtml(id)}" ${selectedSession === id ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('');
  const rows = grades.map(item => `<tr><td class="course-name"><strong>${escapeHtml(item.subject_name || 'Course')}</strong></td><td>${escapeHtml(item.session_name || '—')}</td><td>${escapeHtml(item.continous_assessment_score)}</td><td>${escapeHtml(item.exam_score)}</td><td><span class="score">${escapeHtml(item.total_score)}</span></td></tr>`).join('');
  const firstName = (session.display_name || session.username).split(' ')[0];
  const classDescription = studentProfile?.current_class_name ? `Your class: ${studentProfile.current_class_name}. Explore your results below.` : 'Your class has not been assigned yet. You can still view your results below.';
  document.querySelector('#dashboard-content').innerHTML = `${welcome('Student portal',`Welcome, ${firstName}.`,classDescription)}
    ${banner('Academic records','Make your progress count.','View your course results and keep track of your academic performance.','#academic-record','View my results')}
    <div class="metrics">${metric(new Set(grades.map(item => item.subject)).size,'Courses with results','In the selected academic session','book')}${metric(average,'Average score','Across the results shown below','chart','/ 100')}${metric(highest,'Highest score','Your highest recorded mark','results','/ 100')}</div>
    <div class="content-grid"><section class="panel" id="academic-record"><div class="panel-head"><div><h2>My results</h2><p>Continuous assessment and examination marks</p></div><div class="panel-actions"><select class="input" id="result-session" aria-label="Academic session"><option value="all">All sessions</option>${choices}</select><button class="btn btn-outline btn-small" id="download-results" type="button" ${!grades.length ? 'disabled' : ''}>${icon('download')}Download</button></div></div>
    ${rows ? `<div class="table-scroll"><table class="data-table"><thead><tr><th scope="col">Course</th><th scope="col">Session</th><th scope="col">CA / 40</th><th scope="col">Exam / 60</th><th scope="col">Total</th></tr></thead><tbody>${rows}</tbody></table></div><div class="table-foot">${grades.length} result${grades.length === 1 ? '' : 's'} · Scores are shown out of 100.</div>` : empty('Your results will appear here','Once your lecturer records a result, you’ll be able to view it on this page.')}</section>
    <aside class="aside-column"><section class="panel aside-panel"><div class="panel-body"><h3>Understanding your result</h3><div class="breakdown"><span>Continuous assessment</span><strong>40%</strong></div><div class="breakdown"><span>Examination</span><strong>60%</strong></div><div class="assessment-bar" aria-hidden="true"><span></span><span></span></div><p>Your total combines your assessment and examination marks for each course.</p></div></section><section class="panel note-panel aside-panel"><div class="panel-body"><div class="eyebrow">Academic support</div><h3>Something looks wrong?</h3><p>Contact your course lecturer if a result is missing or a recorded score needs to be reviewed.</p></div></section></aside></div>${footer()}`;
}
async function loadDashboard() {
  if (!session) return renderAuth();
  const currentSession = session;
  renderShell();
  try {
    if (session.role === 'ADMIN') {
      const [data, classes, lecturers, students] = await Promise.all([
        api('/api/admin/stats/'), api('/api/admin/classes/'),
        api('/api/admin/teachers/'), api('/api/admin/students/'),
      ]);
      if (session === currentSession) renderAdmin(data, classes, lecturers, students);
    } else if (session.role === 'TEACHER') {
      const [courses, students, classes, grades] = await Promise.all([
        api('/api/teacher/subjects/'), api('/api/teacher/students/'),
        api('/api/teacher/classes/'), api('/api/teacher/grades/'),
      ]);
      if (session === currentSession) renderTeacher(courses, students, classes, grades);
    } else if (session.role === 'STUDENT') {
      const [grades, profile] = await Promise.all([api('/api/student/grades/'), api('/api/student/profile/')]);
      if (session === currentSession) { allGrades = grades; studentProfile = profile; renderStudent(); }
    } else throw new Error('Please contact university administration to check your account access.');
  } catch (error) {
    const target = document.querySelector('#dashboard-content');
    if (target && session === currentSession) target.innerHTML = `${welcome('Academic services','Unable to load your portal','Please try again in a moment.')}${notice(error.message)}<button class="btn" id="refresh" type="button">Try again</button>`;
  }
}
async function refreshAdmin(message = '') {
  const [data, classes, lecturers, students] = await Promise.all([
    api('/api/admin/stats/'), api('/api/admin/classes/'),
    api('/api/admin/teachers/'), api('/api/admin/students/'),
  ]);
  if (!session || session.role !== 'ADMIN') return;
  renderAdmin(data, classes, lecturers, students, message);
  document.querySelector('#class-management').scrollIntoView({behavior:'smooth', block:'start'});
}
function syncSelectedStudent() {
  const student = adminStudents.find(item => String(item.id) === document.querySelector('#manage-student').value);
  document.querySelector('#selected-student-class').textContent = student
    ? `Current class: ${student.current_class_name || 'not assigned'}.`
    : 'Select a student to see their current class.';
  document.querySelector('#student-class').value = student?.current_class ? String(student.current_class) : '';
}
function syncSelectedClass() {
  const classroom = adminClasses.find(item => String(item.id) === document.querySelector('#manage-class').value);
  document.querySelector('#selected-class-lecturer').textContent = classroom
    ? `Current lecturer: ${classroom.teacher_name || 'not assigned'}.`
    : 'Select a class to see its lecturer.';
  document.querySelector('#manage-lecturer').value = classroom?.class_teacher ? String(classroom.class_teacher) : '';
}
function downloadResults() {
  const rows = [['Course','Academic session','Assessment / 40','Examination / 60','Total / 100'],...visibleGrades().map(item => [item.subject_name,item.session_name || '',item.continous_assessment_score,item.exam_score,item.total_score])];
  const csv = rows.map(row => row.map(cell => {
    let value = String(cell ?? '');
    if (/^[=+\-@\t\r]/.test(value)) value = "'" + value;
    return '"' + value.replaceAll('"','""') + '"';
  }).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob(['\ufeff' + csv], {type:'text/csv;charset=utf-8;'}));
  const link = document.createElement('a'); link.href = url; link.download = 'dave-university-results.csv'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

app.addEventListener('click', async event => {
  const auth = event.target.closest('[data-auth-mode]');
  if (auth) { authMode = auth.dataset.authMode; renderAuth(); }
  const reveal = event.target.closest('[data-password]');
  if (reveal) {
    const input = document.getElementById(reveal.dataset.password);
    const showing = input.type === 'password'; input.type = showing ? 'text' : 'password';
    reveal.textContent = showing ? 'Hide' : 'Show'; reveal.setAttribute('aria-pressed', String(showing));
    reveal.setAttribute('aria-label', `${showing ? 'Hide' : 'Show'} ${reveal.dataset.password.replace('_',' ')}`);
  }
  const logout = event.target.closest('#logout');
  if (logout) {
    logout.disabled = true;
    try { await api('/api/logout/', {method:'POST'}); } catch { /* Always remove access from this tab. */ }
    clearSession(); authMode = 'login'; renderAuth();
  }
  if (event.target.closest('#refresh')) loadDashboard();
  const chooseClass = event.target.closest('.choose-class');
  if (chooseClass) {
    document.querySelector('#manage-class').value = chooseClass.dataset.class;
    syncSelectedClass();
    document.querySelector('#assign-lecturer-form').scrollIntoView({behavior:'smooth',block:'center'});
  }
  const choose = event.target.closest('.choose-course');
  if (choose) {
    document.querySelector('#subject').value = choose.dataset.subject;
    document.querySelector('#grade-card').scrollIntoView({behavior:'smooth',block:'start'});
    document.querySelector('#student').focus({preventScroll:true});
  }
  if (event.target.closest('#download-results')) downloadResults();
});
app.addEventListener('change', event => {
  if (event.target.id === 'manage-student') syncSelectedStudent();
  if (event.target.id === 'manage-class') syncSelectedClass();
  if (event.target.id === 'result-session') {
    selectedSession = event.target.value; renderStudent();
    document.querySelector('#result-session').focus({preventScroll:true});
  }
});
app.addEventListener('input', event => {
  if (['ca','exam'].includes(event.target.id)) {
    const total = Number(document.querySelector('#ca').value || 0) + Number(document.querySelector('#exam').value || 0);
    document.querySelector('#score-preview').textContent = total.toFixed(2).replace(/\.00$/,'');
  }
});
app.addEventListener('submit', async event => {
  if (event.target.id === 'auth-form') {
    event.preventDefault();
    const form = event.target;
    const button = form.querySelector('button[type=submit]');
    const fields = Object.fromEntries(new FormData(form));
    const mode = authMode;
    button.disabled = true;
    try {
      if (mode === 'register') {
        if (fields.password !== fields.confirm_password) throw new Error('Your passwords do not match. Please enter the same password twice.');
        delete fields.confirm_password;
        await api('/api/register/', {method:'POST',body:JSON.stringify(fields),public:true});
        clearSession(); authMode = 'login';
        renderAuth('Your account has been created. Sign in below to continue.', 'success', fields.username);
        document.querySelector('#password').focus({preventScroll:true});
        return;
      }
      if (mode === 'forgot') {
        const data = await api('/api/password-reset/', {method:'POST',body:JSON.stringify({username:fields.username.trim(),email:fields.email.trim()}),public:true});
        recoveryChallenge = { challenge_id: data.challenge_id, username: fields.username.trim(), email: fields.email.trim() };
        authMode = 'reset';
        renderAuth('A 6-digit verification code was sent to your registered email. Enter it below to set your new password.', 'success');
        return;
      }
      if (mode === 'reset') {
        if (!recoveryChallenge?.challenge_id) throw new Error('Please request a verification code first.');
        if (fields.new_password !== fields.confirm_password) throw new Error('Your passwords do not match. Please enter the same password twice.');
        await api('/api/password-reset/confirm/', {method:'POST',body:JSON.stringify({
          challenge_id: recoveryChallenge.challenge_id,
          code: fields.code.trim(),
          new_password: fields.new_password,
          confirm_password: fields.confirm_password,
        }),public:true});
        recoveryChallenge = null;
        authMode = 'login';
        renderAuth('Your password has been changed successfully. Sign in with your new password.', 'success');
        return;
      }
      const data = await api('/api/login/', {method:'POST',body:JSON.stringify({username:fields.username,password:fields.password}),public:true});
      saveSession(data); await loadDashboard();
    } catch (error) {
      const feedback = document.querySelector('#auth-feedback');
      if (feedback) feedback.innerHTML = notice(error.message);
    } finally { if (button.isConnected) button.disabled = false; }
  }
  if (['create-lecturer-form', 'create-class-form', 'assign-lecturer-form', 'assign-student-form'].includes(event.target.id)) {
    event.preventDefault();
    const form = event.target;
    const fields = Object.fromEntries(new FormData(form));
    const button = form.querySelector('button[type=submit]');
    const feedback = document.querySelector('#admin-feedback');
    button.disabled = true;
    try {
      let message;
      if (form.id === 'create-lecturer-form') {
        if (fields.password !== fields.confirm_password) throw new Error('The passwords do not match.');
        delete fields.confirm_password;
        await api('/api/admin/users/', {method:'POST',body:JSON.stringify({...fields,role:'TEACHER'})});
        message = 'Lecturer account created. They can now sign in.';
      } else if (form.id === 'create-class-form') {
        await api('/api/admin/classes/', {method:'POST',body:JSON.stringify({
          name:fields.name.trim(), class_teacher:fields.class_teacher ? Number(fields.class_teacher) : null,
        })});
        message = `Class ${fields.name.trim()} created.`;
      } else if (form.id === 'assign-lecturer-form') {
        await api(`/api/admin/classes/${encodeURIComponent(fields.class_id)}/`, {method:'PATCH',body:JSON.stringify({
          class_teacher:fields.class_teacher ? Number(fields.class_teacher) : null,
        })});
        message = fields.class_teacher ? 'Lecturer assigned to the class.' : 'Lecturer removed from the class.';
      } else {
        await api(`/api/admin/students/${encodeURIComponent(fields.student_id)}/class/`, {method:'PATCH',body:JSON.stringify({
          current_class:fields.current_class ? Number(fields.current_class) : null,
        })});
        message = fields.current_class ? 'Student placed in the class.' : 'Student class assignment removed.';
      }
      await refreshAdmin(message);
    } catch (error) { if (feedback.isConnected) feedback.innerHTML = notice(error.message); }
    finally { if (button.isConnected) button.disabled = false; }
    return;
  }
  if (event.target.id === 'grade-form') {
    event.preventDefault();
    const form = event.target;
    const fields = Object.fromEntries(new FormData(form));
    const button = form.querySelector('button[type=submit]');
    const feedback = document.querySelector('#action-feedback');
    button.disabled = true;
    try {
      const result = await api(`/api/teacher/grades/record/${encodeURIComponent(fields.subject)}/`, {method:'POST',body:JSON.stringify({student:Number(fields.student),continous_assessment_score:fields.ca,exam_score:fields.exam})});
      if (!form.isConnected) return;
      feedback.innerHTML = notice(`Result saved successfully. Total: ${result.total_score} / 100.`, 'success');
      form.reset(); document.querySelector('#score-preview').textContent = '0';
      try {
        const grades = await api('/api/teacher/grades/');
        const list = document.querySelector('#recorded-results-content');
        if (list && form.isConnected) list.innerHTML = recordedResultsTable(grades);
      } catch (error) {
        if (feedback.isConnected) feedback.innerHTML += notice(`Result saved, but the list could not refresh: ${error.message}`);
      }
    } catch (error) { if (feedback.isConnected) feedback.innerHTML = notice(error.message); }
    finally { if (button.isConnected) button.disabled = false; }
  }
});

if (session) loadDashboard(); else renderAuth();
