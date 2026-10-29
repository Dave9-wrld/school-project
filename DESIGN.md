# Dave University — Academic Portal

## Direction
An institutional university portal for students, lecturers and administrators. Academic content and clarity take precedence over developer information. Use the user-provided Dave name.

## Identity
- Navy #122438, burgundy #852E40, muted gold #B39A66, paper #F6F5F1 and white surfaces.
- Book-and-shield crest, serif university wordmark and custom architectural campus illustration.
- Georgia headings with Segoe UI / system sans-serif for forms and academic records.
- Modest corners, fine borders, restrained motion and readable academic tables.
- Public masthead and campus/sign-in layout. Authenticated pages have an academic navigation rail, account header and role-specific summaries.

## Product language
- University, student, lecturer, course, assessment, examination, results and academic session.
- Never expose API indexes, Django links, backend explanations, database IDs, tokens or internal field names in the product.
- Do not invent university claims, GPA calculations, fees, timetables, course credits or unavailable services.
- All counts, courses and results come from actual records. Assessment weighting follows the existing 40/60 model.

## Flows
- Registration creates a student account, then displays sign-in with a success message and username filled in. Never automatically log in after registration.
- Explicit sign-in loads the role's dashboard. Sign-out and expired sessions clear this tab's saved credentials.
- Students can filter real results by academic session and download the displayed results as CSV.
- Lecturers see their assigned courses and class groups, then select a named student and course and see the combined mark before saving. A list of recorded results shows the students, courses, sessions and scores for the lecturer's assigned courses; it refreshes after saving. IDs are transmitted behind the scenes only.
- Administration shows actual university totals and class management: create a class, assign or remove a lecturer, and place, move or remove a student from a class. Students see their assigned class. No developer tools in product navigation.

## Implementation
- The new React / Next.js frontend is in `frontend/` and runs on port 3000, with its own `frontend/DESIGN.md`. It connects to the existing Django API through a Next.js server route. See `frontend/README.md` for startup and verification.
- Local frontend: /app/, served by Django on the same origin as /api/.
- Assets: portal/static/portal/university.css, university.js and campus.svg.
- Token authentication uses session storage. Dynamic content is HTML-escaped. Server permissions remain authoritative.
- The student directory follows the existing grade-entry scope: active student accounts, available only to lecturers with an assigned course. The current data model does not associate subject enrolment with students; add enrolment restrictions when that relationship exists.
- Validate registration separately from login, error states, lecturer permissions and responsive layouts. Use an isolated test database for browser QA.
