# NDK Pack List Org

iPad-friendly packing list organizer for Next Day Koi.

Upload a WooCommerce packing list → sorted by greenhouse → mark issues → Customer Service report.

---

## Host on the web (Render – free)

### 1. Create a free Render account
Go to: https://render.com → **Get Started** → sign up with Google or email.

### 2. Put the app on GitHub (required by Render)
1. Create a free account at https://github.com if you don’t have one
2. Create a **New repository** named `NDK-Pack-List-Org` (public is fine)
3. Upload all files from this `NDK_Pack_List_Org` folder into that repository
   (or use GitHub Desktop to drag the folder in)

### 3. Deploy on Render
1. In Render, click **New +** → **Web Service**
2. Connect your GitHub account and select the `NDK-Pack-List-Org` repo
3. Settings:
   - **Name:** `ndk-pack-list-org` (or any name you like)
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
4. Click **Create Web Service**
5. Wait 2–5 minutes for the first deploy

### 4. Open your app
Render will give you a link like:
`https://ndk-pack-list-org.onrender.com`

- Open that link on any computer or iPad
- On iPad: Safari → Share → **Add to Home Screen** → name it **NDK Pack List Org**

### 5. (Optional but recommended) Set a secret key
In Render → your service → **Environment** → Add:
`SECRET_KEY` = any long random string (e.g. `ndk-koi-2026-secret-xyz`)

---

## Important free-tier notes

- The free service **sleeps after ~15 minutes of no use**. The first open of the day may take 30–60 seconds to wake up — that is normal.
- Uploaded packing lists and issue marks are stored on the server for the day. If the service restarts overnight, you may need to upload again the next morning (typical for free hosting).
- For a full packing day, keep using the app so it stays awake.

---

## Daily use

1. Open the web link (or Home Screen icon on iPad)
2. Upload today’s packing list PDF from WooCommerce
3. Pack from the sorted screens
4. Tap **NIT / Color Change / Sores** when needed
5. Open **Customer Service Report** when finished

---

## Local backup (optional, Mac)

If the website is ever down, you can still run it on a Mac:

```bash
cd NDK_Pack_List_Org
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000
Or double-click `launch_ndk.command`.
