# 👱‍♀️ AI Influencer Face LoRA Training Guide (bmaltais/kohya_ss)

**100% Free on Google Colab or Kaggle T4 GPU (~35 minutes)**

---

## 📸 1. Dataset Collection (20–30 Photos)

1. **Photo Breakdown:**
   - 10 Close-up face selfies (neutral, smiling, side angle)
   - 10 Upper-body portraits (different lighting, backgrounds)
   - 5 Full-body shots
2. **Rules:**
   - No sunglasses or hats blocking eyebrows/eyes
   - Clean, high resolution (minimum 512x512)
   - Consistent face, varied clothing and hair

---

## ⚡ 2. 1-Click Training Setup (Colab Free T4)

Open Google Colab with T4 GPU and run:

```bash
# Cell 1: Clone kohya_ss
!git clone https://github.com/bmaltais/kohya_ss.git
%cd kohya_ss
!pip install -q -r requirements.txt
!pip install -q xformers

# Cell 2: Launch Web UI
!python kohya_gui.py --share
```

---

## 🎛️ 3. Exact Training Parameters

In the **LoRA** tab of Kohya GUI:

| Parameter | Recommended Value | Why? |
| :--- | :--- | :--- |
| **Base Model** | `runwayml/stable-diffusion-v1-5` | Best compatibility with StableAnimator |
| **Instance Prompt** | `my_influencer` | Unique trigger word |
| **Class Prompt** | `woman` | Base class |
| **Batch Size** | `1` | Fits easily in 15GB T4 VRAM |
| **Epochs** | `3` | Prevents over-fitting |
| **Learning Rate** | `1e-4` (`0.0001`) | Ideal convergence |
| **Text Encoder LR** | `5e-5` | Preserves likeness |
| **LR Scheduler** | `cosine` | Smooth decay |
| **Mixed Precision** | `fp16` | Fast rendering |
| **Network Rank (Dimension)** | `32` | Sharp face structure (~75MB file) |
| **Network Alpha** | `16` | Stability |

---

## 💾 4. Save & Deploy

1. After training finishes (~30-40 min), download:
   `my_face.safetensors`
2. Place it in:
   - Locally: `models/lora/my_face.safetensors`
   - Or upload to your Hugging Face Space / Kaggle Dataset.

Tumhara AI Influencer ka face ab har video mein **100% consistent** rahega!
