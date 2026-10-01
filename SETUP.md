# ⚙️ Ek baar ka setup — phir sirf Telegram

Iske baad kabhi Kaggle kholna nahi padega. Bas Telegram pe message bhejo,
GPU khud jaagega, photo banegi, aur 5 min baad khud band ho jaayega.

**Total time: ~10 minute.** Teen parts hain, teeno zaroori hain.

---

## ⚠️ Pehle ye samajh lo

GitHub pe secrets daalne se **akela kaam nahi hoga**, kyunki jo workflow
unhe use karta hai wo **abhi GitHub pe hai hi nahi**. Wo files sirf
tumhare computer pe bani hain.

Isliye order ye hai:

```
PART 1  code GitHub pe bhejo      <- ye pehle
PART 2  4 secrets daalo
PART 3  workflow enable karo
```

---

# PART 1 — Code GitHub pe bhejo

Apne computer pe repo folder me terminal kholo aur ye chalao:

```bash
git add .github/workflows/diya-waker.yml \
        scripts/waker.py \
        scripts/push_kaggle.py \
        kaggle/diya_server.py \
        kaggle/kernel-metadata-live.json \
        training/kaggle_lora_train.py \
        training/kernel-metadata.json \
        START.md SETUP.md PROMPTS.md RUN_GUIDE.md start.sh
```

Check karo ki `.env` galti se add na ho gaya ho:

```bash
git status --short | grep "\.env$"
```

**Kuch nahi aana chahiye.** Agar `.env` dikhe to ruk jao —
`git reset .env` chalao, phir aage badho.

Ab commit aur push:

```bash
git commit -m "Telegram auto-wake: waker + workflow + realism server"
git push origin main
```

✅ **Check:** GitHub pe jaake dekho ki `.github/workflows/diya-waker.yml`
file dikh rahi hai. Nahi dikhi to aage mat badho.

---

# PART 2 — 4 Secrets daalo

GitHub pe apna repo kholo:

> **Settings** → left sidebar me **Secrets and variables** → **Actions**
> → green button **New repository secret**

Chaar baar ye repeat karo:

| # | Name (bilkul aise hi) | Value |
|---|---|---|
| 1 | `TELEGRAM_BOT_TOKEN` | BotFather wala token |
| 2 | `TELEGRAM_CHAT_ID` | `6486771356` |
| 3 | `KAGGLE_USERNAME` | `ukboy7u787` |
| 4 | `KAGGLE_KEY` | tumhara `KGAT_...` token |

**Dhyan rakho:**
- Name me koi space nahi, capital letters exactly aise hi
- Value paste karte waqt aage-peeche space na aaye
- Secret save hone ke baad dikhai nahi dega — ye normal hai

✅ **Check:** Actions secrets list me chaaron naam dikhne chahiye.

---

# PART 3 — Workflow enable karo

> Repo me upar **Actions** tab → left me **Diya Waker**
> → agar "This workflow was disabled" dikhe to **Enable workflow** dabao

Ab turant test karo:

> **Diya Waker** → right me **Run workflow** → **Run workflow**

~30 second baad run green ✅ hona chahiye.

Log kholke dekho, in me se ek line aayegi:
- `koi naya prompt nahi` → sab sahi, bas Telegram pe kuch bheja nahi tha
- `kernel already RUNNING` → sab sahi
- `GPU jaga raha hoon` → server start ho raha hai 🎉

❌ Agar `Authentication required` aaye → `KAGGLE_KEY` galat hai
❌ Agar `TELEGRAM_BOT_TOKEN missing` aaye → secret ka naam galat likha hai

---

# ✅ Ho gaya — ab kaise use karein

Bas Telegram pe bhejo:

```
/night
```

Peeche ye hoga:

```
tumhara message
   ↓  (max 5 min)
GitHub Actions dekhta hai
   ↓
Kaggle GPU start
   ↓  (~3-4 min model load)
"Server ready" Telegram pe
   ↓
photo ban ke aa jaati hai
   ↓  (5 min koi message nahi)
GPU khud band 🔋
```

Pehli photo me **~8 min** lagenge (jagna + load). Uske baad jab tak
server chalu hai, har photo **~40 second**.

---

## 🔋 Quota kaise bachti hai

| | |
|---|---|
| Waker CPU pe chalta hai | GitHub Actions, **free**, GPU quota zero |
| GPU sirf tab chalta hai jab tum prompt bhejo | idle me kabhi nahi |
| 5 min khaali rahe to khud band | bhool jao tab bhi safe |
| `/stay 20` | lamba session chahiye to |
| `/sleep` | abhi band karo |

---

## 📸 Instagram (optional, alag se)

Ye GitHub ka nahi, **Kaggle ka** secret hai:

> Kaggle kernel kholo → **Add-ons** → **Secrets** → **Add secret**

| Name | Value |
|---|---|
| `IG_PASSWORD` | `@diyarai_016` ka password |

`IG_USERNAME` push ke waqt khud chala jaata hai.

Phir Telegram pe `/ig` se check karo, `/post` ya `/story` se daalo.

---

## 🧯 Kuch kaam na kare to

| problem | wajah | hal |
|---|---|---|
| message bheja, kuch nahi hua | workflow disabled | Actions → Diya Waker → Enable |
| Actions me run hi nahi dikhta | PART 1 nahi hua | workflow file GitHub pe hai? check karo |
| run red ❌ | secret galat | log kholo, naam/value check karo |
| 10 min baad bhi photo nahi | Kaggle quota khatam | Kaggle → Settings me baaki hours dekho |
| `Maximum batch GPU session count of 2` | 2 session chal rahe | Kaggle pe purana Stop Session karo |

---

## 🔒 Kabhi mat karna

- `.env` ko **kabhi commit mat karna** — usme Kaggle key aur bot token hai
- Token ko kisi public jagah paste mat karna
- `kaggle/diya_server.py` me token hardcode mat karna — push ke waqt
  automatic inject hota hai, repo me kabhi nahi jaata
