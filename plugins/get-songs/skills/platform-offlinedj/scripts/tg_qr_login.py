"""Log in to Telegram by QR code. Opens qr.png (refreshed ~every 25 s) and waits up to 10 min.
Scan with phone: Telegram -> Settings -> Devices -> Link Desktop Device.
If the account has 2FA, rerun with TG_2FA env var set (prints 2FA_REQUIRED otherwise).
"""
import asyncio, os, platform, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tgcommon import load, ensure_dir, lock_session, SESSION, DIR
import qrcode
from telethon.sync import TelegramClient
from telethon import errors

cfg = load(); ensure_dir()
PNG = os.path.join(DIR, "qr.png")


def show(path):
    opener = {"Darwin": ["open"], "Windows": ["cmd", "/c", "start", ""]}.get(platform.system(), ["xdg-open"])
    subprocess.run(opener + [path])


client = TelegramClient(SESSION, cfg["api_id"], cfg["api_hash"])
client.connect()
run = client.loop.run_until_complete
try:
    if not client.is_user_authorized():
        qr = client.qr_login()
        deadline = time.time() + 600
        while True:
            if time.time() > deadline:
                print("timed out"); sys.exit(1)
            qrcode.make(qr.url).save(PNG); show(PNG)
            print("QR ready - scan it now", flush=True)
            try:
                run(qr.wait(timeout=25)); break
            except (TimeoutError, asyncio.TimeoutError):
                run(qr.recreate())
            except errors.SessionPasswordNeededError:
                pw = os.environ.get("TG_2FA")
                if not pw:
                    print("2FA_REQUIRED", flush=True); sys.exit(2)
                client.sign_in(password=pw); break
    me = client.get_me()
    bot = client.get_entity(cfg["bot"])
    print(f"Logged in OK as {me.first_name}. Bot found: @{bot.username}")
except errors.SessionPasswordNeededError:
    pw = os.environ.get("TG_2FA")
    if not pw:
        print("2FA_REQUIRED"); sys.exit(2)
    client.sign_in(password=pw); print("Logged in OK (2FA)")
finally:
    client.disconnect()
    if os.path.exists(PNG): os.remove(PNG)
    lock_session()
