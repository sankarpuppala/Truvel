# Truvel — Easy Deployment Guide

This guide describes the **easiest, cleanest, and most reliable** way to deploy Truvel online for free.

---

## Architecture: Unified Fullstack Service

Instead of splitting the frontend (Vercel) and backend (Render) across different domains—which creates CORS errors, cookie blocking, and cold-start loading delays—Truvel is packaged as a **Unified Fullstack Service**:

```
           User Browser / Phone (HTTPS)
                         │
                         ▼
        ┌───────────────────────────────────┐
        │        Render Web Service         │
        │                                   │
        │  FastAPI (Port 8000 / $PORT)      │
        │  ├── /api/*   (REST Endpoints)    │
        │  ├── /media/* (Uploaded Media)    │
        │  └── /*       (React SPA Build)   │
        │                                   │
        │  SQLite DB (truvel.db, 23.6 MB)   │
        │  8,646 genuine places & photos    │
        └───────────────────────────────────┘
```

### Why this works so well:
1. **Zero CORS Issues**: Frontend and API live on the exact same domain (`https://truvel.onrender.com`).
2. **Zero Cookie / Auth Problems**: Session cookies are 100% first-party; you stay signed in seamlessly across all browsers (Safari, Chrome, Firefox, Brave, Mobile).
3. **No External Database Setup**: The SQLite database (`truvel.db`) with FTS5 search for all 23 Indian scripts is included in the deployment repository—no need to configure Neon, Postgres extensions, or connection pools.
4. **Instant HTTPS**: Free SSL certificate is automatically provisioned, so GPS Geolocation (`navigator.geolocation`) works immediately on phones and laptops.
5. **Single URL to Share**: One clean link for demos, project evaluation, and friends.

---

## Method 1: Deploy on Render (Recommended, 100% Free)

### Step 1: Push your code to GitHub
Ensure all latest changes are committed and pushed to your GitHub repository (`Project-5` on `master` or `main`).

### Step 2: Open Render Dashboard
1. Go to [dashboard.render.com](https://dashboard.render.com/) and sign in with your GitHub account.
2. Click the **"New +"** button at the top right and select **"Blueprint"** (or **"Web Service"**).

#### If choosing Blueprint (Fastest — 1 Click):
- Select your `Project-5` repository.
- Render will automatically read `render.yaml` from your repo.
- Click **"Apply"**.
- Render will automatically build the Docker container and start your app!

#### If choosing Web Service manually:
- Connect your GitHub repository `Project-5`.
- **Name**: `truvel` (or whatever you prefer)
- **Region**: `Singapore` (closest to India for best speed)
- **Language**: `Docker`
- **Instance Type**: `Free`
- Click **"Create Web Service"**.

### Step 3: Wait for Build & Deployment
- Render will pull your repository, build the frontend (`npm run build`), install Python requirements, copy `truvel.db`, and start `uvicorn`.
- When the status turns green to **"Live"**, your URL will be ready at:
  `https://truvel.onrender.com` (or your chosen service name).

---

## Method 2: Deploy on Railway (Alternative)

Railway provides another instant, zero-config deployment option:

1. Go to [railway.com](https://railway.com/) and sign in with GitHub.
2. Click **"New Project"** -> **"Deploy from GitHub repo"**.
3. Select your `Project-5` repository.
4. Railway will automatically detect `Dockerfile` at the root and begin building.
5. Once deployed, click on the service -> **Settings** -> **Networking** -> click **"Generate Domain"**.
6. Your app is live with HTTPS!

---

## Post-Deployment Verification Checklist

Once your deployment is live, check these five items:

1. **Health Check**:
   - Open `https://<your-app-url>/api/health`
   - Should return `{"ok": true, "city_default": "hyderabad", ...}`.
2. **Web App Loading**:
   - Open `https://<your-app-url>/`
   - The Nearby Discovery Deck loads with Hyderabad/Bangalore places.
3. **Search & Explore**:
   - Go to `/explore` and search for "Lalbagh", "Charminar", or "Bhuvanagiri".
   - Confirm 50 results load and "Show more" appends places.
4. **Watch Screen & Comments**:
   - Go to `/watch`
   - Tap a video, open comments, and tap `@username` to verify creator account profiles open cleanly.
5. **Mobile Geolocation**:
   - Open the link on your phone.
   - Allow location access when prompted to see places within 5km/10km/25km near you.
