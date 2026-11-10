# Milestone 1: Course Enrollment and Attendance

## What was added

This milestone adds a real relationship between students, courses, and academic sessions before attendance or new lecturer-entered grades are recorded.

### Data models

1. `CourseEnrollment`
   - Links one `StudentProfile`, one `Subject`, and one `AcademicSession`.
   - Uses a uniqueness constraint so the same student cannot be enrolled twice in the same course and session.
   - Supports `ACTIVE`, `COMPLETED`, and `WITHDRAWN` states.

2. `AttendanceSession`
   - Represents one lecture attendance event for a course and academic session.
   - Stores the lecture date, start time, optional end time, and `OPEN` or `CLOSED` state.
   - Records the user who created it.

3. `AttendanceRecord`
   - Links an attendance session to an existing course enrollment.
   - Supports `PRESENT`, `ABSENT`, `LATE`, and `EXCUSED` states.
   - Prevents duplicate attendance for the same student in one lecture.

## Why attendance uses course enrollment

Attendance is not attached directly to a student and subject because that would not prove the student registered for that course in that academic session. Linking attendance to `CourseEnrollment` makes the rule explicit and keeps historical sessions separate.

## Authorization rules

| Role | Course enrollment | Attendance |
|---|---|---|
| Administrator | Read all and create or update | Read all and manage sessions or records |
| Lecturer | Read enrollments for assigned courses | Manage only assigned-course sessions and records |
| Student | Read own enrollments | Read own sessions and records only |

Lecturers can now record a grade only when the student has an active enrollment for that course in the current academic session.

## Data migration decision

The migration does not guess which courses students take. It creates historical course enrollments only where an existing grade already proves a student-course-session relationship. A grade in the current session becomes an active enrollment; a grade in an older session becomes completed. The historical enrollment date is left unknown instead of inventing one.

## Existing architecture preserved

- Django REST Framework remains the backend API.
- Next.js App Router remains the frontend.
- The existing `ADMIN`, `TEACHER`, and `STUDENT` role system remains in place.
- Existing grade records and score rules remain unchanged.
- The project uses expiring DRF token authentication, not JWT. This milestone preserves the real authentication system rather than replacing it unnecessarily.

## API routes

- `GET, POST /api/course-enrollments/`
- `PATCH /api/course-enrollments/<id>/`
- `GET, POST /api/attendance-sessions/`
- `PATCH /api/attendance-sessions/<id>/`
- `GET, POST /api/attendance-records/`
- `PATCH /api/attendance-records/<id>/`

Every list is filtered on the server according to the signed-in user's role. Frontend hiding is for usability; backend authorization provides the security boundary.

## Frontend behavior

- Administrators can enroll a student in a course and session.
- Lecturers can view enrolled students, open a lecture attendance session, mark attendance, and close the session.
- Students can view their registered courses and personal attendance history.
- The student attendance rate counts present and late records as attended and excludes excused records from the denominator.

## SIWES defense answers

**Why did you create a separate enrollment model?**

Because a student's class does not prove registration for every course. The enrollment model records the exact student-course-session relationship and supports withdrawal or completion without deleting history.

**How do you prevent duplicate data?**

Database uniqueness constraints prevent duplicate course registrations and duplicate attendance records. Serializer validation returns understandable API errors before invalid state is saved.

**How is role security enforced?**

Permissions first decide whether a role may use an operation. Role-scoped querysets then limit which records that user can read or modify. A lecturer cannot manage another lecturer's course, and a student receives only personal records.

**Why can a closed attendance session not reopen?**

Closing is a deliberate finalization step. Preventing reopening reduces silent changes to an already finalized lecture record. Corrections must happen while the session is open in this milestone.

**How did you protect existing data?**

The migration derives enrollments only from existing grade relationships. It preserves all grades and creates no attendance records automatically because the project has no evidence of historical attendance.

## Verification

- Django system check passes.
- All 81 backend tests pass.
- Frontend attendance tests pass.
- TypeScript type checking passes.
