# 🚀 Deployment Guide — Speech-to-Melody Converter

Three deployment paths are ready. Pick the one that suits you.

---

## 0. Push to GitHub first (required for Railway & Render)

```bash
# Inside the speech_to_melody/ folder:
git init
git add .
git commit -m "Initial commit — Speech-to-Melody"

# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/speech-to-melody.git
git push -u origin main
```

CI runs automatically — the GitHub Actions workflow will test the pipeline
and build the Docker image on every push to `main`.

---

## 1. Railway (Recommended — easiest, ~2 minutes)

Railway auto-detects the `railway.json` + `Dockerfile` and deploys with one click.

### Steps

1. Go to **https://railway.app** → sign in with GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `speech-to-melody` repository
4. Railway detects the Dockerfile automatically → click **Deploy**
5. Once deployed, go to **Settings → Networking → Generate Domain**
6. Your app is live at `https://speech-to-melody-xxxx.railway.app`

### Environment variables (set in Railway dashboard → Variables tab)

| Variable | Value | Why |
|----------|-------|-----|
| `MPLBACKEND` | `Agg` | Non-interactive matplotlib |
| `STORAGE_DIR` | `/tmp/speech_melody` | Writable storage on Railway's ephemeral FS |
| `PORT` | *(set automatically by Railway)* | Don't override this |

### Free tier limits
- 500 hours/month compute (enough for a personal project)
- 512 MB RAM — librosa + a 10s audio file fits comfortably
- Files in `/tmp` are ephemeral — they disappear on redeploy. That's fine since downloads are immediate.

---

## 2. Render (Free tier, zero credit card)

Render picks up `render.yaml` automatically.

### Steps

1. Go to **https://render.com** → sign in with GitHub
2. Click **"New"** → **"Web Service"**
3. Connect your GitHub repo → select `speech-to-melody`
4. Render reads `render.yaml` → **click "Create Web Service"**
5. First deploy takes ~8 min (building librosa + numba is slow on free tier)
6. App is live at `https://speech-to-melody.onrender.com`

### Render free tier gotcha
Free services **spin down after 15 min of inactivity**. The first request after
sleep takes ~30s to cold-start. To avoid this, use Render's paid Starter plan
($7/month) or ping the service every 10 minutes with a free uptime monitor like
**https://uptimerobot.com**.

### Environment variables (already in render.yaml, but set here if needed)

| Variable | Value |
|----------|-------|
| `MPLBACKEND` | `Agg` |
| `STORAGE_DIR` | `/tmp/speech_melody` |

---

## 3. Docker — Self-Host on Any VPS (DigitalOcean, Hetzner, AWS EC2, etc.)

### 3a. Build and run locally

```bash
# Build
docker build -t speech-to-melody .

# Run
docker run -p 8000:8000 \
  -e MPLBACKEND=Agg \
  -e STORAGE_DIR=/tmp/speech_melody \
  speech-to-melody

# Open http://localhost:8000
```

### 3b. Deploy to a VPS (e.g. DigitalOcean $6/month Droplet)

```bash
# On your local machine — build and push to Docker Hub
docker login
docker build -t YOUR_DOCKERHUB_USERNAME/speech-to-melody:latest .
docker push YOUR_DOCKERHUB_USERNAME/speech-to-melody:latest

# SSH into your VPS
ssh root@YOUR_VPS_IP

# On the VPS:
docker pull YOUR_DOCKERHUB_USERNAME/speech-to-melody:latest

docker run -d \
  --name speech-melody \
  --restart unless-stopped \
  -p 80:8000 \
  -e MPLBACKEND=Agg \
  -e STORAGE_DIR=/tmp/speech_melody \
  YOUR_DOCKERHUB_USERNAME/speech-to-melody:latest
```

App is now live at `http://YOUR_VPS_IP`.

### 3c. Add HTTPS with Nginx + Certbot (optional but recommended)

```bash
# On your VPS
apt install nginx certbot python3-certbot-nginx -y

# Create Nginx config
cat > /etc/nginx/sites-available/speech-melody << 'EOF'
server {
    listen 80;
    server_name YOUR_DOMAIN.com;

    client_max_body_size 30M;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
EOF

ln -s /etc/nginx/sites-available/speech-melody /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Get free HTTPS cert
certbot --nginx -d YOUR_DOMAIN.com
```

---

## Quick Reference

| Platform | Cost | Deploy time | Cold start | Custom domain |
|----------|------|-------------|------------|---------------|
| Railway | Free (500h/mo) | ~3 min | None | ✅ (free) |
| Render | Free | ~8 min | 30s (free tier) | ✅ (free) |
| Docker/VPS | $4–6/mo | ~5 min | None | ✅ |

---

## Troubleshooting

**`No module named 'librosa'`** — make sure you're using the Dockerfile (not Python buildpack). Railway/Render should auto-detect it from `railway.json` / `render.yaml`.

**`OSError: sndfile library not found`** — the Dockerfile installs `libsndfile1`. If you're using a raw Python buildpack without Docker, add a `packages.txt` file containing `libsndfile1` and `ffmpeg`.

**Timeout on large files** — gunicorn's `--timeout 120` gives 2 minutes per request. Increase it if needed for very long recordings.

**`/tmp` files missing after redeploy** — this is expected on Railway/Render. Files are ephemeral. Downloads must happen in the same session. For persistent storage, attach a volume (Railway) or use S3/R2.
