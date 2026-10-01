#!/usr/bin/env python3
"""
Diya Rai — Kaggle kernels push karo (yahin se, ek command me).

Kaggle CLI ko har kernel ke folder me `kernel-metadata.json` chahiye hota hai,
isliye yeh script ek saaf staging folder banata hai aur wahan se push karta hai.

CREDENTIALS (.env me, ya env vars):
    KAGGLE_USERNAME=ukboy7u787
    KAGGLE_KEY=<kaggle.json wali API key>
    -> https://www.kaggle.com/settings  ->  API  ->  "Create New Token"

CHALAO:
    python scripts/push_kaggle.py              # dono kernels push
    python scripts/push_kaggle.py server       # sirf server
    python scripts/push_kaggle.py train        # sirf trainer
    python scripts/push_kaggle.py --status     # last run ka status
    python scripts/push_kaggle.py --diff       # Kaggle vs local compare
    python scripts/push_kaggle.py --pull       # Kaggle ka code local me laao
    python scripts/push_kaggle.py server --force   # jaan-boojh ke overwrite
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

KERNELS = {
    "train": {
        "code": ROOT / "training" / "kaggle_lora_train.py",
        "meta": ROOT / "training" / "kernel-metadata.json",
        "desc": "SDXL LoRA trainer (~32 min, ek baar chalana hai)",
    },
    "server": {
        "code": ROOT / "kaggle" / "diya_server.py",
        "meta": ROOT / "kaggle" / "kernel-metadata-live.json",
        "desc": "Unified GPU server — Telegram + web dashboard",
    },
}


# ------------------------------------------------------------------ #
def load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def setup_creds():
    """Kaggle ke do token format support karo:
       - naya OAuth token  'KGAT_...'  -> ~/.kaggle/access_token + KAGGLE_API_TOKEN
       - purani API key                -> ~/.kaggle/kaggle.json
    """
    load_env()
    user = os.getenv("KAGGLE_USERNAME", "")
    key = os.getenv("KAGGLE_KEY", "") or os.getenv("KAGGLE_API_TOKEN", "")
    if not (user and key):
        sys.exit(
            "\n❌ Kaggle credentials missing.\n\n"
            "   https://www.kaggle.com/settings/api -> 'Generate New Token'\n"
            "   Phir .env me daalo:\n\n"
            "     KAGGLE_USERNAME=ukboy7u787\n"
            "     KAGGLE_KEY=<token>\n"
        )
    d = Path.home() / ".kaggle"
    d.mkdir(exist_ok=True)
    if key.startswith("KGAT_"):
        f = d / "access_token"
        f.write_text(key)
        f.chmod(0o600)
        os.environ["KAGGLE_API_TOKEN"] = key
        (d / "kaggle.json").unlink(missing_ok=True)
    else:
        f = d / "kaggle.json"
        f.write_text(json.dumps({"username": user, "key": key}))
        f.chmod(0o600)
        os.environ["KAGGLE_USERNAME"] = user
        os.environ["KAGGLE_KEY"] = key
    return user


def run(cmd, **kw):
    print(f"   $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    out = (r.stdout + r.stderr).strip()
    if out:
        print("   " + out.replace("\n", "\n   "))
    return r.returncode == 0, out


def remote_code(slug, user):
    """Kaggle pe abhi jo code hai wo laao (compare karne ke liye)."""
    stage = Path(tempfile.mkdtemp(prefix="kglpull_"))
    r = subprocess.run(["kaggle", "kernels", "pull", f"{user}/{slug}", "-p", str(stage)],
                       capture_output=True, text=True)
    try:
        if r.returncode == 0:
            for f in stage.glob("*.py"):
                return f.read_text()
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return None


INJECT_HEAD = "# --- push-time injected secrets (private kernel only) ---"


def strip_secrets(code):
    """Kaggle se aaye code me se injected secret block hatao aur MARKER wapas
    lagao — taaki token kabhi repo file me na likha jaaye."""
    if INJECT_HEAD not in code:
        return code
    out, skip = [], False
    for line in code.splitlines():
        if line.startswith(INJECT_HEAD):
            out.append(MARKER)
            skip = True
            continue
        if skip:
            if line.startswith("#") or line.startswith("os.environ.setdefault("):
                continue
            skip = False
        out.append(line)
    return "\n".join(out) + ("\n" if code.endswith("\n") else "")


def guard(name, user, force):
    """Agar Kaggle pe code local se ALAG hai to push rok do — warna
    tumhare Kaggle-side edits chup-chaap mit jaayenge.
    Comparison se pehle injected secrets hata dete hain, warna hamesha
    'alag' dikhega."""
    k = KERNELS[name]
    slug = json.loads(k["meta"].read_text())["id"].split("/")[-1]
    rem = remote_code(slug, user)
    if rem is None:
        return True  # kernel abhi exist nahi karta — pehli push
    rem = strip_secrets(rem)
    loc = k["code"].read_text()
    if rem.strip() == loc.strip():
        return True

    import difflib
    d = list(difflib.unified_diff(loc.splitlines(), rem.splitlines(),
                                  "LOCAL", "KAGGLE", lineterm="", n=0))
    add = sum(1 for x in d if x.startswith("+") and not x.startswith("+++"))
    rem_n = sum(1 for x in d if x.startswith("-") and not x.startswith("---"))
    print(f"\n   ⚠️  RUKO — Kaggle pe code local se ALAG hai")
    print(f"      Kaggle me {add} lines aisi hain jo local me nahi")
    print(f"      Local me {rem_n} lines aisi hain jo Kaggle me nahi")
    print(f"      Lagta hai tumne Kaggle pe edit kiya hai.")
    print(f"\n      Pehle Kaggle wala code local me le aao:")
    print(f"        python scripts/push_kaggle.py {name} --pull")
    print(f"      Ya jaan-boojh ke overwrite karna hai to:")
    print(f"        python scripts/push_kaggle.py {name} --force")
    return bool(force)


def pull(name, user):
    """Kaggle ka code local file me wapas laao."""
    k = KERNELS[name]
    slug = json.loads(k["meta"].read_text())["id"].split("/")[-1]
    rem = remote_code(slug, user)
    if rem is None:
        print(f"❌ {name}: Kaggle pe kernel nahi mila")
        return False
    rem = strip_secrets(rem)   # token kabhi repo file me na jaaye
    if rem.strip() == k["code"].read_text().strip():
        print(f"✅ {name}: pehle se same hai, kuch badla nahi")
        return True
    bak = k["code"].with_suffix(".py.bak")
    bak.write_text(k["code"].read_text())
    k["code"].write_text(rem)
    print(f"✅ {name}: Kaggle ka code -> {k['code'].relative_to(ROOT)}")
    print(f"   (purana local backup: {bak.relative_to(ROOT)})")
    return True


MARKER = "# === SECRETS_INJECT_MARKER ==="
INJECT_KEYS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "HF_TOKEN", "GEMINI_API_KEY",
               "IG_USERNAME", "IG_PASSWORD", "IG_SESSION_ID")


def inject_secrets(code, meta, name):
    """.env ki values ko staged copy me daalo — repo file me KABHI nahi.

    Kaggle ke API me secrets ka koi endpoint nahi hai, isliye private kernel me
    inject karna hi ek tareeka hai. Public kernel pe ye refuse karega.
    """
    if MARKER not in code:
        return code, []
    vals = {k: os.getenv(k, "").strip() for k in INJECT_KEYS}
    vals = {k: v for k, v in vals.items() if v}
    if not vals:
        return code, []

    if str(meta.get("is_private", "true")).lower() not in ("true", "1"):
        print("   ⚠️  kernel PUBLIC hai — secrets inject NAHI kiye (leak ho jaate).")
        return code, []

    block = [
        "# --- push-time injected secrets (private kernel only) ---",
        "# Source: local .env. Repo me ye values kabhi commit nahi hotin.",
    ]
    for k, v in vals.items():
        block.append(f'os.environ.setdefault({k!r}, {v!r})')
    return code.replace(MARKER, "\n".join(block)), list(vals)


def push(name, user, force=False):
    k = KERNELS[name]
    if not k["code"].exists():
        print(f"❌ {name}: {k['code']} nahi mila")
        return False

    print(f"\n📤 {name} — {k['desc']}")
    if not guard(name, user, force):
        print("   ⏭️  SKIP kiya (kuch overwrite nahi hua)")
        return False

    meta = json.loads(k["meta"].read_text())
    # metadata ka owner hamesha current user hona chahiye
    slug = meta["id"].split("/")[-1]
    meta["id"] = f"{user}/{slug}"
    meta["code_file"] = k["code"].name

    stage = Path(tempfile.mkdtemp(prefix=f"kgl_{name}_"))
    code, injected = inject_secrets(k["code"].read_text(), meta, name)
    (stage / k["code"].name).write_text(code)
    (stage / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))

    print(f"   id       : {meta['id']}")
    if injected:
        print(f"   secrets  : 🔐 injected -> {', '.join(injected)}")
    print(f"   code     : {k['code'].relative_to(ROOT)}")
    print(f"   gpu      : {meta.get('enable_gpu')}  internet: {meta.get('enable_internet')}")
    print(f"   datasets : {', '.join(meta.get('dataset_sources') or []) or '—'}")

    ok, out = run(["kaggle", "kernels", "push", "-p", str(stage)])
    shutil.rmtree(stage, ignore_errors=True)

    if ok and "error" not in out.lower():
        print(f"   ✅ https://www.kaggle.com/code/{meta['id']}")
        return True
    print(f"   ❌ push fail")
    return False


def status(user):
    for name, k in KERNELS.items():
        slug = json.loads(k["meta"].read_text())["id"].split("/")[-1]
        print(f"\n📊 {name} ({user}/{slug})")
        run(["kaggle", "kernels", "status", f"{user}/{slug}"])


def main():
    args = [a for a in sys.argv[1:]]
    user = setup_creds()
    print(f"🔑 Kaggle user: {user}")

    if "--status" in args:
        status(user)
        return

    targets = [a for a in args if a in KERNELS] or list(KERNELS)

    if "--pull" in args:
        for n in targets:
            pull(n, user)
        return
    if "--diff" in args:
        for n in targets:
            print(f"\n🔍 {n}")
            guard(n, user, force=False) and print("   ✅ Kaggle == local")
        return

    force = "--force" in args
    results = {n: push(n, user, force) for n in targets}

    print("\n" + "=" * 60)
    for n, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {n}")
    print("=" * 60)
    if all(results.values()):
        print("\nAgla step:")
        print("  1. Kaggle pe kernel kholo -> Settings -> Accelerator: GPU T4 x2, Internet: ON")
        print("  2. Add-ons -> Secrets -> TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID")
        print("  3. Pehle 'train' chalao (~32 min), phir 'server'")
        print("\n  Status dekhne ke liye:  python scripts/push_kaggle.py --status")


if __name__ == "__main__":
    main()
