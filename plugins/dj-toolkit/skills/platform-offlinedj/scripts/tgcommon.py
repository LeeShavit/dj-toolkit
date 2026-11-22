import json, os, stat

HOME = os.path.expanduser(os.environ.get("DJ_TOOLKIT_HOME", "~/.claude/dj-toolkit"))
DIR = os.path.join(HOME, "secrets", "telegram")
CFG = os.path.join(DIR, "config.json")
SESSION = os.path.join(DIR, "me")


def ensure_dir():
    os.makedirs(DIR, exist_ok=True)
    os.chmod(os.path.join(HOME, "secrets"), stat.S_IRWXU)
    os.chmod(DIR, stat.S_IRWXU)


def load():
    if not os.path.exists(CFG):
        raise SystemExit("Telegram not set up - run tg_keys.py first.")
    return json.load(open(CFG))


def save(cfg):
    ensure_dir()
    old = os.umask(0o077)
    json.dump(cfg, open(CFG, "w"), indent=1)
    os.umask(old)
    os.chmod(CFG, stat.S_IRUSR | stat.S_IWUSR)


def lock_session():
    for f in os.listdir(DIR):
        if f.startswith("me.session"):
            os.chmod(os.path.join(DIR, f), stat.S_IRUSR | stat.S_IWUSR)
