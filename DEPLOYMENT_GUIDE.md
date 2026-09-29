# 🚀 AI-INFLUENCER-OS — Zero Laptop Load Deployment Guide

**Ab tumhara laptop 100% free rahega.**
Sara compute **Hugging Face ZeroGPU** par chalega aur orchestration **GitHub Actions** sambhalega.

---

## 📋 System Architecture

```
[links.txt] (Target Reels)
       │
       ▼
[GitHub Actions CRON] (10 AM & 6 PM daily auto-trigger)
       │
       ├─► [Hugging Face Space: video-gen]
       │       ├─ yt-dlp (Downloads Reel)
       │       ├─ DWPose (133 Body Motion Keypoints)
       │       ├─ SD 1.5 + LoRA (Your Character Avatar in Dress/BG)
       │       ├─ Wan2.1 (Image-to-Video Dance Motion Transfer)
       │       └─ Llama 3.1 8B (Viral Caption & Hashtags)
       │
       ├─► [Hugging Face Space: upscaler]
       │       └─ Real-ESRGAN (Crisp 4K Upscale)
       │
       ├─► [Instagram Auto-Post] (instagrapi)
       │
       └─► [Telegram Notification] ──► "👑 Done Boss! Aaj ki Reel Ban Gayi!"
```

---

## 🛠️ Step 1: Hugging Face Par 2 Spaces Banao (Free ZeroGPU)

1. [huggingface.co](https://huggingface.co) par login karo.
2. **Space 1 (`video-gen`):**
   - Click **New Space** → Name: `video-gen`
   - License: `mit`
   - SDK: **Docker** (Blank)
   - Hardware: **ZeroGPU (Free)**
   - Files upload karo:
     - `spaces/video-gen/Dockerfile`
     - `spaces/video-gen/requirements.txt`
     - `spaces/video-gen/app.py`
     - *(Optional)* Apna trained LoRA model file: `models/lora/my_face.safetensors`
3. **Space 2 (`upscaler`):**
   - Click **New Space** → Name: `upscaler`
   - SDK: **Gradio**
   - Hardware: **ZeroGPU (Free)**
   - Files upload karo:
     - `spaces/upscaler/requirements.txt`
     - `spaces/upscaler/app.py`

4. **Hugging Face Tokens:**
   - Go to [Hugging Face Settings → Access Tokens](https://huggingface.co/settings/tokens)
   - Create 1–3 read tokens (e.g. `hf_account1`, `hf_account2` for multi-account auto-rotation).

---

## 🔐 Step 2: GitHub Repository & Secrets Setup

1. Is folder ko apne GitHub par push karo:
   ```bash
   git init
   git add .
   git commit -m "feat: AI-INFLUENCER-OS zero laptop load"
   git branch -M main
   git remote add origin https://github.com/<YOUR_USERNAME>/ai-influencer-os.git
   git push -u origin main
   ```

2. GitHub Repo kholo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret Name | Value Example | Description |
| :--- | :--- | :--- |
| `HF_VIDEO_SPACE` | `<your-hf-username>/video-gen` | Video Gen Space Name |
| `HF_UPSCALER_SPACE` | `<your-hf-username>/upscaler` | Real-ESRGAN Upscaler Space |
| `HF_TOKENS` | `hf_token1,hf_token2,hf_token3` | Multi-account rotation tokens |
| `IG_USERNAME` | `your_ai_influencer_handle` | Instagram account username |
| `IG_PASSWORD` | `your_ig_password` | Instagram account password |
| `TELEGRAM_BOT_TOKEN`| `123456789:ABCdef...` | Telegram bot token from @BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | `987654321` | Your personal Telegram user ID |

---

## 📅 Step 3: Kaise Kaam Karega?

1. **Automatic Mode (Roz 10 AM & 6 PM):**
   - GitHub Actions apne aap `links.txt` se agla link uthayega.
   - Space ko call karega, reel banayega, 4K upscale karega, Instagram pe post karega.
   - Tumhare phone pe message aayega: **"Done Boss! Aaj ki Reel Ban Gayi!"** sath mein preview video.

2. **Manual Run (Jab bhi man kare):**
   - GitHub repo pe jao → **Actions** tab → **AI Influencer Daily Automation** → **Run workflow**.
   - Custom Instagram link, dress aur scene daalo aur click **Run workflow**!
