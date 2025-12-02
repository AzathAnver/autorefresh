# refresh_token_updater.py
import requests, time, os, tempfile, shutil
from datetime import datetime, timedelta


# === FILE PATHS ===
OUTPUT_FILE_PATH = r"C:\Users\Azath.A\os\logs\log.txt"
# === File Logging Setup ===
output_file = open(OUTPUT_FILE_PATH, "w", encoding="utf-8")
_original_print = print
def print(*args, **kwargs):
    """Print to console AND to log file at once."""
    _original_print(*args, **kwargs)
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    output_file.write(sep.join(map(str, args)) + end)
    output_file.flush()

ENV_PATH = r"C:\Users\Azath.A\os\auth.env"
TOKEN_URL = "https://authenticate.os.wpp.com/auth/realms/os-prod/protocol/openid-connect/token"
CLIENT_ID = "os-web"
SLEEP_ON_SUCCESS = 60 * 50   # 50 minutes
SLEEP_ON_FAIL = 60           # 1 minute

def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def read_env(path):
    d = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k,v = line.rstrip("\n").split("=",1)
                    d[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return d

def write_env_atomic(path, new_kv):
    orig=[]
    try:
        with open(path, "r", encoding="utf-8") as f:
            orig = f.readlines()
    except FileNotFoundError:
        orig = []
    out=[]
    written=set()
    for line in orig:
        if "=" in line and not line.strip().startswith("#"):
            k,_ = line.split("=",1)
            k=k.strip()
            if k in new_kv:
                out.append(f"{k}={new_kv[k]}\n")
                written.add(k)
            else:
                out.append(line)
        else:
            out.append(line)
    for k,v in new_kv.items():
        if k not in written:
            out.append(f"{k}={v}\n")
    fd,tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", text=True)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as tf:
            tf.writelines(out)
        shutil.move(tmp, path)
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass

def do_refresh(refresh_token):
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    return requests.post(TOKEN_URL, data=data, headers=headers, timeout=15)

def main():
    print(f"{now()} | refresh_token_updater starting. ENV: {ENV_PATH}")
    while True:
        env = read_env(ENV_PATH)
        refresh_token = env.get("REFRESH_TOKEN")
        if not refresh_token:
            print(f"{now()} | No REFRESH_TOKEN found in {ENV_PATH}. Add it now. Retrying in {SLEEP_ON_FAIL}s.")
            time.sleep(SLEEP_ON_FAIL)
            continue

        try:
            resp = do_refresh(refresh_token)
        except Exception as e:
            print(f"{now()} | HTTP error during refresh: {e}. Retrying in {SLEEP_ON_FAIL}s.")
            time.sleep(SLEEP_ON_FAIL)
            continue

        if resp.status_code != 200:
            print(f"{now()} | token endpoint {resp.status_code}: {resp.text[:300]}. Retrying in {SLEEP_ON_FAIL}s.")
            time.sleep(SLEEP_ON_FAIL)
            continue

        j = resp.json()
        access = j.get("access_token")
        new_refresh = j.get("refresh_token")
        expires_in = int(j.get("expires_in") or 3600)

        if not access:
            print(f"{now()} | No access_token in response. Response: {j}. Retrying in {SLEEP_ON_FAIL}s.")
            time.sleep(SLEEP_ON_FAIL)
            continue

        kv = {"BEARER_TOKEN": access}
        if new_refresh:
            kv["REFRESH_TOKEN"] = new_refresh
        kv["ACCESS_EXPIRES_AT"] = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
        write_env_atomic(ENV_PATH, kv)
        print(f"{now()} | Refreshed tokens; expires_in={expires_in}. Next run in {SLEEP_ON_SUCCESS}s.")
        time.sleep(SLEEP_ON_SUCCESS)

if __name__ == "__main__":
    main()

# === Close Log File ===
output_file.close()