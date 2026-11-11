# Putting RecoMart online (PythonAnywhere, free)

This guide puts the demo store at `https://USERNAME.pythonanywhere.com` so recruiters can try it. Replace
`USERNAME` everywhere with your PythonAnywhere username. Setup takes about 30 minutes, and most of that is
waiting for `pip install`.

**Why PythonAnywhere:**
- the free Beginner plan is always on: no "waking up" delay for the first visitor
- it needs no card
- it keeps the SQLite database, the product photos and the trained model on a disk that survives restarts

**Limits of the free plan that this guide works around:**

| Limit | What we do |
|---|---|
| 512 MB of disk | Install packages with `--no-cache-dir`. Everything fits in about 350 MB. |
| Internet access only to allowed sites. PyPI and GitHub are allowed, DummyJSON is not. | Upload the product photos once as a zip. The catalog itself is already in the repo. |
| The web app stops after 1 month unless you extend it | Click **Run until 1 month from today** on the Web tab. PythonAnywhere emails a reminder. |
| No scheduled tasks on new free accounts | Reset the demo by hand when needed (see [Resetting the demo](#resetting-the-demo)). |
| 1 web worker | Fine for a demo, and it suits our per-process caches. |

## What demo mode does
`DEMO_MODE=True` in `.env` turns the site into a safe public demo:
- **One-click demo accounts on the login page.** One button logs in as **Priya**, a customer with order
  history, so "Recommended for you" is filled in. The other opens the **admin dashboard**.
- **The shared accounts can look but not break.** They can open every page and retrain the model. Saving in the
  dashboard (products, categories, orders, stock, the A/B switch) and editing their profile are switched off.
  Django's `/admin/` is closed to them. All of these rules are in `accounts/middleware.py`.
- **Guests see a slim banner** saying the shoppers, orders and payments are simulated.
- **Visitors can still register their own account** and shop, review and check out normally.
- **You keep a private superuser** with full access. Never share its password.

## 1. On your laptop: zip the product photos
DummyJSON can't be reached from a free account, so take the photos your laptop already downloaded:
```powershell
Compress-Archive -Path media\products -DestinationPath recomart-media.zip
```
This makes a zip of about 16 MB.

## 2. Create the account
Sign up for a **Beginner** account at <https://www.pythonanywhere.com>. Your username becomes the address.

## 3. Get the code and install packages
Open **Consoles → Bash** and run:
```bash
git clone https://github.com/SAHIL-AGARWAL-IN/RecoMart.git
cd RecoMart
mkvirtualenv --python=/usr/bin/python3.12 recomart     # use python3.13 if 3.12 isn't listed
pip install --no-cache-dir -r requirements.txt           # slow; --no-cache-dir saves disk space
```
Next time you open a console, run `workon recomart` to get back into the virtualenv.

## 4. Upload the photos
On the **Files** tab, open `/home/USERNAME/RecoMart/` and upload `recomart-media.zip`. Then, in the Bash console:
```bash
cd ~/RecoMart
unzip -q recomart-media.zip -d media && rm recomart-media.zip
ls media/products | wc -l                               # about 290 files
```
Skipping this step still works: `seed_data --offline` draws simple placeholder pictures instead of photos.

## 5. Create `.env`
Make a secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```
Then `nano .env`, paste this in, put your key and username in, save (Ctrl+O, Enter) and exit (Ctrl+X):
```ini
SECRET_KEY=paste-the-generated-key-here
DEBUG=False
ALLOWED_HOSTS=USERNAME.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://USERNAME.pythonanywhere.com
HTTPS=True
SSL_REDIRECT=False
DEMO_MODE=True
```
`SSL_REDIRECT=False` is set because PythonAnywhere's own **Force HTTPS** switch (step 7) does the redirect.

## 6. Build the database, the model and the static files
```bash
python manage.py migrate
python manage.py seed_data --offline        # catalog from the repo, photos from step 4
python manage.py train_recommender
python manage.py collectstatic --noinput
python manage.py createsuperuser            # YOUR private admin; never share this password
```

## 7. Create the web app
On the **Web** tab:
1. Click **Add a new web app**, then **Next**. Choose **Manual configuration** (not "Django"), and pick the same
   Python version as your virtualenv.
2. **Code:** set *Source code* and *Working directory* to `/home/USERNAME/RecoMart`.
3. **Virtualenv:** `/home/USERNAME/.virtualenvs/recomart`
4. **WSGI configuration file:** click the link, delete everything in it, and paste:
   ```python
   import os
   import sys

   path = "/home/USERNAME/RecoMart"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"  # settings.py reads the rest from .env

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
   Save.
5. **Static files:** add two rows.

   | URL | Directory |
   |---|---|
   | `/static/` | `/home/USERNAME/RecoMart/staticfiles` |
   | `/media/` | `/home/USERNAME/RecoMart/media` |

6. **Security:** turn on **Force HTTPS**.
7. Click the big green **Reload** button at the top.

## 8. Check it
Open `https://USERNAME.pythonanywhere.com` in a private window and check:
- [ ] The home page has colours, fonts and product photos, and the teal demo banner is at the top.
- [ ] The login page shows the two demo buttons. **Shop as Priya** shows "Recommended for you" on the home page.
- [ ] **Open the admin dashboard** shows charts and the "Read-only demo" notice. ML Insights has the cluster
  chart, and **Retrain** works.
- [ ] Editing a product as the demo admin shows "saving changes is switched off".
- [ ] `/admin/` with your own superuser works.

Then put the link at the top of your README and your CV.

## Updating after you push new code
```bash
cd ~/RecoMart && workon recomart
git pull
pip install --no-cache-dir -r requirements.txt   # only if requirements.txt changed
python manage.py migrate
python manage.py collectstatic --noinput
```
Then click **Reload** on the Web tab.

## Resetting the demo
If visitors buy up the stock, or you want fresh data:
```bash
cd ~/RecoMart && workon recomart
python manage.py seed_data --fresh --offline && python manage.py train_recommender
```
Then click **Reload**, so the web worker loads the new model. `--fresh` deletes the visitors' accounts and
orders. Your superuser is kept.

## Troubleshooting

| What you see | Fix |
|---|---|
| Pages have no styling | Check the `/static/` row on the Web tab and run `collectstatic` again |
| No product photos | Check the `/media/` row, and that `media/products/` has files (step 4) |
| "CSRF verification failed" when submitting a form | `CSRF_TRUSTED_ORIGINS` must be exactly `https://USERNAME.pythonanywhere.com` |
| "Too many redirects" | Set `SSL_REDIRECT=False` in `.env` and reload |
| "Bad Request (400)" | `ALLOWED_HOSTS` must be `USERNAME.pythonanywhere.com` |
| "Server Error (500)" | Web tab → **Error log**: the full traceback is printed there |
| "Disk quota exceeded" | Run `du -hs ~/.cache ~/.virtualenvs ~/RecoMart`, then `rm -rf ~/.cache/pip` |
| "This site has expired" page | Web tab → **Run until 1 month from today** |
