# RecoMart: guide for Claude Code sessions

RecoMart is a Django e-commerce store with an ML recommendation engine. It is a B.Tech CSE Sem-5 Full Stack Lab project for a team of 4. Code must be clean and easy for students to explain in a viva.

**Start every session by reading `docs/PLAN.md`.** It has the full approved plan and a phase checklist. Continue from the first unchecked phase, and stop at the end of each phase so the user can test.

## Fixed stack (from the approved synopsis, do not change)
- **Backend:** Python 3.12 (`.venv`), Django 5.2 LTS, Django ORM. SQLite for development. Postgres is used when `DB_ENGINE=postgres` is set in `.env`.
- **Frontend:** Django Templates that inherit from `templates/base.html`, Bootstrap 5.3, Bootstrap Icons, and vanilla JS `fetch()` for AJAX. **No React, Vue or Next.js.**
- **ML:** scikit-learn (TF-IDF, K-Means, cosine similarity, PCA), NumPy, Pandas, Joblib.
- **Charts:** Chart.js.
- **Vendored assets:** Bootstrap, Icons, Chart.js and the fonts live in `static/vendor/` so the demo works offline. Never add CDN links.
- **Secrets:** read from `.env` via python-dotenv. Copy `.env.example` to create it.

## Layout
- **`config/`:** settings and the root urls.
- **`accounts/`:** custom `User` with a `role` field (customer/admin), auth views, `admin_required` / `StoreAdminRequiredMixin`.
- **`store/`:** catalog, cart, orders, reviews and wishlist. The pieces:
  - `cart.py`: cart service
  - `services.py`: checkout and interaction logging
  - `api.py`: JSON endpoints
  - `seed/`: seed helpers
  - `management/commands/seed_data.py`
- **`recommender/`:** all ML logic lives in `features.py` and `engine.py`, never in views. `services.py` holds the DB glue (A/B, events, FBT). `models/` holds the Joblib files (git-ignored). The training command is `management/commands/train_recommender.py`.
- **`dashboard/`:** admin analytics, CRUD and the ML Insights page.
- **`templates/`** has `base.html`, `partials/` and one folder per app. **`static/`** has `css/theme.css`, `js/*.js` and `vendor/`.
- **`docs/`:**
  - `PLAN.md`
  - `VIVA_NOTES.md`: append one section per phase covering what was built, the key decisions, and likely viva Q&A in simple language
  - `screenshots/`

## Conventions
- Function-based views for the storefront and APIs. Generic class-based views for dashboard CRUD.
- APIs return `JsonResponse`. Every POST checks CSRF; JS sends the `X-CSRFToken` header via the helper in `static/js/main.js`.
- Business logic goes in `services.py`, `cart.py` or `engine.py`. Views stay thin.
- Money is `DecimalField`, in INR, shown with Indian grouping (₹1,29,999) through the `inr` template filter. Timezone is `Asia/Kolkata`.
- Use `select_related` / `prefetch_related` on list pages. No raw SQL.
- Interaction data in the demo DB is **simulated by `seed_data`**. Say so wherever it is shown (README, ML Insights).
- Comments explain *why*, briefly. Keep functions small and well named; students have to read this code aloud.

## Design rules (UI work uses the frontend-design skill)
- It must not look like default Bootstrap. All colours, radii, shadows and spacing are CSS custom properties in `static/css/theme.css`, and Bootstrap's `--bs-*` variables are overridden from there. Light and dark tokens go under `[data-bs-theme]`.
- Brand: deep teal primary, marigold accent for deals and badges, warm neutral grays. Plus Jakarta Sans for headings, Inter for body text.
- Cards are rounded with soft shadows, subtle hover lifts and fade-ins. Use skeleton loaders while AJAX content loads, and friendly empty states.
- Must be responsive at 375, 768 and 1280 px.
- Must be accessible: alt text, labels, visible focus states, AA contrast, `aria-live` on toasts.
- Never use JS `alert()` / `confirm()`. Use Bootstrap modals or confirm pages instead.

## Commands (Windows PowerShell, from the repo root)
```powershell
.\.venv\Scripts\Activate.ps1
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py seed_data --fresh        # first run needs internet for product images
python manage.py train_recommender
python manage.py runserver                # http://127.0.0.1:8000
```
Demo logins: `admin / Admin@123` (admin role) and `priya / Customer@123` (customer).

## Workflow
- Work on a branch per phase (`phase-N-<name>`) and commit after every working step. Merge into `main` only after the user approves the phase.
- Verify before claiming done: `check`, migrations check and tests must pass. For UI changes, take Playwright screenshots of `http://127.0.0.1:8000` at 375, 768 and 1280 px, then critique and fix.
- At the end of each phase, update the checklist in `docs/PLAN.md` and add a section to `docs/VIVA_NOTES.md`.
