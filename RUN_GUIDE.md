# 👑 Diya Rai — Train karo, phir Telegram + Website dono se chalao

Sab fix ho gaya. Ab sirf **2 kernel** hain — ek train karta hai, ek chalata hai.

```
  STEP 1                        STEP 2
  ┌──────────────────┐          ┌─────────────────────────────────┐
  │ kaggle_lora_train│          │        diya_server.py           │
  │  15 real photos  │  .safe   │  ┌──────────┐                   │
  │       ↓          │ tensors  │  │ Website  │─┐                 │
  │  SDXL LoRA       │ ───────► │  │ Dashboard│ │   JOB QUEUE     │
  │  ~32 min, 1 baar │          │  └──────────┘ ├─► (background) ─► GPU ─► image
  └──────────────────┘          │  ┌──────────┐ │                 │
                                │  │ Telegram │─┘                 │
                                │  └──────────┘                   │
                                └─────────────────────────────────┘
```

---

## 🗑️ Jo delete kar diya (sab toota hua tha)

| File | Kyun hataya |
|---|---|
| `kaggle_run_model/` (poora folder) | `AutopipelineForText2Image` typo pe crash; turbo + galat scheduler se dhundhli images |
| `kaggle/diya_cloud_worker.py` | wahi bugs + hardcoded token |
| `kaggle/diya_rai_cloud_gpu_worker.ipynb` | wahi copy, token leak |
| `kaggle/kaggle_live_worker.py` | LoRA kabhi exist hi nahi karti thi, Gradio share flaky |
| `kaggle/face_gen_NOBOM.py`, `face_consistent_gen.py`, `complete_az_generator.py` | 3 adhoore duplicates, kahin se call nahi hote |
| `exact_face_swap.py`, `send_test_preview.py` | root me pade scratch scripts |

Bacha: `kaggle/kernel.py` (video/StableAnimator pipeline — wo alag kaam karta hai).

---

## 🚨 BADI KHABAR — tumhari LoRA pehle se BANI HUI HAI

Kaggle check karne pe pata chala: `ukboy7u787/diyarai-sdxl-lora` dataset me
**pehle se ek proper trained LoRA padi hai** (228 MB). Uska metadata padha:

| | |
|---|---|
| Trainer | kohya `sd-scripts` |
| Dataset | `10_diyarai woman` — **wahi 15 photos**, 10 repeats |
| Steps | 1500 (10 epochs) |
| Rank / Alpha | 32 / 16 |
| Base | `sd_xl_base_1.0` @ 1024 buckets |
| Text encoders | **dono trained** (te1 + te2) — trigger word strong hai |
| Optimizer | AdamW8bit, cosine, lr 1e-4 |

**Matlab training kabhi problem thi hi nahi. Tum pehle hi sahi train kar chuke the.**

Asli problem: **purana code us LoRA ko load hi nahi karta tha.**
- `diya_gpu_master.py` → sdxl-turbo use karta tha, LoRA ka naam tak nahi tha
- `kaggle_live_worker.py` → LoRA dhoondta tha par wo script kabhi chali hi nahi

Naya `diya_server.py` isko **auto-detect karke load karta hai** (diffusers kohya format
convert kar leta hai). Isliye:

### 👉 Tumhe retrain karne ki ZAROORAT NAHI. Seedha Step 2 pe jao.

Step 1 (training) tab chalana jab:
- likeness aur strong chahiye → `--steps 2000 --rank 48`
- naye photos add karo → dataset update karke retrain

> **Note:** purani LoRA `sd_xl_base_1.0` pe train hui hai, aur server default
> `RealVisXL_V4.0` use karta hai (zyada photoreal). Aam taur pe ye combo behtar
> dikhta hai. Agar likeness thoda off lage to maximum match ke liye:
> `!python diya_server.py --base stabilityai/stable-diffusion-xl-base-1.0`

---

## 🟣 STEP 1 — LoRA train karo (ek baar, ~32 min)

**Yeh sabse zaroori step hai.** Iske bina chehra kabhi exact nahi aayega —
purana code sirf `inswapper_128` use karta tha jo 128×128 pe kaam karta hai,
usse bas "milta-julta" chehra banta hai.

### Dataset upload
1. `training/diyarai_lora_dataset.zip` kholo → andar `10_diyarai woman/` folder hai
   (15 photos + captions — **yeh bilkul sahi hai, isme kuch mat badlo**)
2. Kaggle → **Datasets → New Dataset** → wo folder upload → naam: **`diya-lora-dataset`**

### Train chalao
Naya Notebook → **GPU T4 x2** + **Internet ON** → dataset attach karo:

```bash
!python kaggle_lora_train.py --data "/kaggle/input/diya-lora-dataset" --steps 1500
```

Telegram secrets daal do (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) to har 250 step pe
**preview image Telegram pe aayegi** — live dekh sakte ho chehra kitna match kar raha hai.

**Output:** `/kaggle/working/diyarai_sdxl_lora.safetensors`
→ download karo → Kaggle Dataset banao → naam **`diyarai-sdxl-lora`**

**Trainer tez kyun hai:**
- VAE latents + text embeddings **ek baar** cache → phir dono text encoders RAM se delete (~5 GB VRAM free)
- Sirf UNet attention LoRA (rank 32), 8-bit Adam, gradient checkpointing, Min-SNR γ=5
- T4 pe ~1.2 s/step → **1500 steps ≈ 32 min**

**Agar chehra abhi bhi off lage:** `--steps 2000` ya `--rank 48`
**Agar har image same pose/background de (over-fit):** `--steps 1000`

---

## 🟣 STEP 2 — Server chalao (Telegram + Website saath me)

Naya Notebook → **GPU T4 x2** + **Internet ON**
Datasets: **`diyarai-sdxl-lora`** attach karo (face polish chahiye to `diya-model-identity` bhi)

**Secrets** (Add-ons → Secrets):
```
TELEGRAM_BOT_TOKEN = <naya token>
TELEGRAM_CHAT_ID   = 6486771356
```

```bash
!python diya_server.py
```

Console me aur Telegram pe public URL aa jaayega:
```
========================================================
  DASHBOARD LIVE:  https://xxxx-xxxx.trycloudflare.com
========================================================
```

### 🌐 Website dashboard
- Prompt box + 6 ready-made preset chips (cafe / saree / street / gym / traditional / night)
- Sliders: **Images 1-4**, **Identity (LoRA) 0.3-1.2**, **Steps 15-40**, face-polish toggle
- **Generate** dabao → card **foran** dikh jaata hai with live stopwatch (queued → generating → done)
- Output gallery — image pe click karo full-screen
- Top bar me live: model ready, LoRA naam, queue, kitni bani, GPU + VRAM
- Phone pe bhi chalta hai, wahi URL

### 📱 Telegram
| Command | Kaam |
|---|---|
| `red saree, terrace sunset` | bas prompt likh do — command ki zaroorat nahi |
| `/photo <prompt>` | same cheez |
| `cafe` / `saree` / `street` / `gym` / `night` | preset ka naam |
| `/n 2` | ek prompt pe 2 images |
| `/scale 0.95` | LoRA identity strength (1.0 = max likeness) |
| `/steps 30` | quality vs speed |
| `/swap on` | GFPGAN face polish |
| `/queue` | queue me kya hai |
| `/status` | GPU, VRAM, uptime, count |
| `/web` | dashboard link |
| `/stop` | server band |

**Dono ek hi queue share karte hain** — Telegram se bheja job dashboard pe bhi dikhega aur ulta bhi.

---

## 🔋 GPU QUOTA BACHAO — Auto sleep + auto wake

Pehle server hamesha chalta rehta tha aur khaali baithe bhi quota khaata tha
(30h/week me se). Ab aisa hai:

```
   Telegram pe prompt
          │
          ▼
  GitHub Actions waker  (har 5 min, CPU, FREE — GPU kharch 0)
   • Telegram "peek" karta hai, messages CONSUME nahi karta
   • kernel pehle se RUNNING? -> kuch mat karo
   • warna -> Kaggle GPU kernel start karo
          │
          ▼
   Kaggle GPU server boot (~2 min)
   • Telegram ka backlog khud padh leta hai
   • images banata hai, bhejta hai
   • 5 min koi kaam nahi -> KHUD BAND
          │
          ▼
      GPU soya, quota safe
```

### Sabse zaroori trick
Telegram tabhi message ko "pada hua" maanta hai jab tum `offset` ke saath
getUpdates call karo. Waker **offset bhejta hi nahi** — isliye messages queue me
pade rehte hain aur GPU server boot hote hi wahi backlog padh leta hai.
Dono poller aapas me nahi takraate.

### Naye Telegram commands
| Command | Kaam |
|---|---|
| `/sleep` | GPU abhi band karo (quota bachao) |
| `/stay 20` | idle shutdown 20 min karo |
| `/stay 0` | auto-shutdown band (⚠️ quota jalega) |
| `/status` | ab `Idle : 3.2 min baad band` bhi dikhata hai |

Dashboard ke header me bhi live pill hai: **`GPU band in 4.3m`**
(1 min bachne pe Telegram pe warning aa jaata hai — prompt bhejo to timer reset.)

### GitHub Secrets (ek baar — waker ke liye zaroori)
Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | tumhara bot token |
| `TELEGRAM_CHAT_ID` | `6486771356` |
| `KAGGLE_USERNAME` | `ukboy7u787` |
| `KAGGLE_KEY` | tumhara `KGAT_...` token |

Phir Actions tab → **Diya Waker** → enable. Test ke liye *Run workflow* daba do.

> **Latency:** waker har 5 min chalta hai + GPU boot ~2 min = worst case ~7 min
> pehli photo me. Uske baad server 5 min jaga rehta hai, to aage ki photos
> turant (~20 s). Jaldi chahiye to Kaggle pe khud **Run** daba do.

---

## ⚡ Fast response kaise kiya

| Technique | Fayda |
|---|---|
| **Background job queue + worker thread** | API `<50 ms` me `job_id` lauta deta hai. GPU alag thread me. Dashboard/Telegram kabhi freeze nahi |
| **Startup warm-up pass** | CUDA kernels pehle hi compile → pehli asli image slow nahi |
| **Model ek hi baar load** | har image ~15-20 s (T4, 28 steps), dobara load nahi |
| **Lazy face models** | insightface/GFPGAN tabhi load jab `/swap on` karo — warna 2 min bachte hain |
| **Sirf missing pip packages** | purana code har run pe `numpy<2 insightface onnxruntime-gpu` install karta tha = **6-9 min bekaar**. Ab ~30 sec |
| **Optimistic UI** | card turant render, 100 ms stopwatch, 1.6 s state poll |

---

## 📊 Pehle vs Ab

| | Purana | Naya |
|---|---|---|
| Startup | 6-9 min pip install | ~30 sec |
| Pehli image | **aati hi nahi** (crash) | ~1.5 min (load + warm-up + gen) |
| Agli image | — | **15-20 sec** |
| Face accuracy | inswapper 128px, "milta-julta" | **trained LoRA — exact** |
| Base model | sdxl-turbo + galat scheduler = dhundhla | RealVisXL V4.0 + DPM++ 2M Karras |
| Control | prompt script me hardcode | **Telegram + Website, ek shared queue** |
| Output dekhna | kahin nahi | live gallery + background processing cards |

---

## 🔑 Secrets (token kabhi code me mat daalna)

Purana leaked token revoke ho chuka hai aur code se nikal diya gaya hai.
Ab har jagah secrets **sirf env se** aate hain.

**Local machine** — `.env` (ye file gitignored hai):
```bash
cp .env.example .env     # phir values bharo
```
```ini
TELEGRAM_BOT_TOKEN=<tumhara token>
TELEGRAM_CHAT_ID=6486771356
```

**Kaggle** — Add-ons → Secrets:
| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | tumhara token |
| `TELEGRAM_CHAT_ID` | `6486771356` |

Bot: **@Bbyjihotbot**. Agar token missing hoga to script saaf error ke saath ruk jaayegi,
chup-chaap galat token use nahi karegi.

---

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| Dashboard pe `no LoRA — train karo` | `diyarai-sdxl-lora` dataset attach nahi hua |
| Chehra 80% match karta hai | `/scale 1.0`, ya `--steps 2000` se retrain |
| Chehra zyada stiff / har photo same | `/scale 0.7` |
| Tunnel URL nahi bana | `--no-tunnel` hata do; ya Kaggle output me `trycloudflare` dhoondo |
| CUDA OOM | `/steps 25` aur `/n 1` |
| Telegram chup hai | Secrets me `TELEGRAM_CHAT_ID` galat hai — bot ko pehle `/start` bhejo |
