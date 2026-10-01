# 🚀 Diya ko START kaise karein

Server **hamesha band rehta hai** (GPU quota bachane ke liye) aur 5 minute
idle hone pe khud band ho jaata hai. To har baar use karne se pehle
start karna padta hai.

Teen tarike hain — sabse upar wala sabse aasan.

---

## 1️⃣ Telegram se (apne aap) — ⭐ RECOMMENDED

Bas bot ko message bhejo:

```
/night
```

Bas. GitHub Actions har 5 minute me Telegram check karta hai, naya message
dekhte hi Kaggle server start kar deta hai.

- Server start hone me **~3-4 min** lagte hain (model load)
- Taiyaar hote hi bot khud "Server ready" bhejta hai
- Phir tumhara message process ho jaata hai

**Pehli baar ek setup chahiye** (ek hi baar, 2 minute) — neeche "GitHub setup" dekho.

---

## 2️⃣ Kaggle website se (bina kisi setup ke, abhi kaam karta hai)

1. Kholo: https://www.kaggle.com/code/ukboy7u787/diya-rai-server
2. Upar right me **"Run All"** (ya Edit → Run All)
3. ~3-4 min baad Telegram pe "Server ready" message aayega

---

## 3️⃣ Computer se (ek command)

```bash
cd aspto
./start.sh
```

Pehli baar `.env` me `KAGGLE_KEY` hona chahiye (already hai).

---

## ⛔ BAND kaise karein

| tarika | kab |
|---|---|
| Telegram pe `/sleep` | turant band |
| kuch mat karo | 5 min idle ke baad khud band |
| `/stay 20` | idle timeout 20 min kar do |

Khud band hona hi default hai — bhoolne pe bhi quota nahi jalti.

---

## GitHub setup (ek baar, tarika 1 ke liye)

GitHub repo → **Settings → Secrets and variables → Actions → New secret**.
Chaar secret daalo:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | tumhara bot token |
| `TELEGRAM_CHAT_ID` | `6486771356` |
| `KAGGLE_USERNAME` | `ukboy7u787` |
| `KAGGLE_KEY` | tumhara `KGAT_...` token |

Phir **Actions** tab → **Diya Waker** → **Enable workflow**.

Ho gaya. Ab sirf Telegram pe message bhejna kaafi hai.

---

## 🔑 Instagram ke liye (ek baar)

Kaggle kernel → **Add-ons → Secrets** me daalo:

| Name | Value |
|---|---|
| `IG_PASSWORD` | `@diyarai_016` ka password |

`IG_USERNAME` already inject ho jaata hai. Phir Telegram pe `/ig` se check,
aur `/post` se last photo Instagram pe chali jaayegi.

---

## Server start hone ke baad

```
/best          sabse acchi quality (~40s per photo)
/fast          jaldi (~15s)

/day           din ka scene
/night         raat ka scene
/monsoon       baarish
/food          khana peena
/daily         roz ka din

/post          last photo Instagram pe
/sleep         GPU band karo
```

Ya seedha apna prompt likh do — command ki zaroorat nahi.
