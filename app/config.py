import base64
import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    DATABASE_URL = os.getenv("DATABASE_URL")
    SECRET = os.getenv("SECRET")
    TOKEN = os.getenv("TOKEN")

    IS_GENERIC_URL_OK = os.getenv("IS_GENERIC_URL_OK", "false").lower() == "true"

    DOWNLOAD_VIDEO_SIZE_IN_MB = int(os.getenv("DOWNLOAD_VIDEO_SIZE_IN_MB", "20"))
    DOWNLOAD_VOICE_SIZE_IN_MB = int(os.getenv("DOWNLOAD_VOICE_SIZE_IN_MB", "5"))
    DOWNLOAD_URL_SIZE_IN_MB = int(os.getenv("DOWNLOAD_URL_SIZE_IN_MB", "40"))

    BASE = "api.telegram.org"
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/telegram")

    LOADING_SONG = os.getenv(
        "LOADING_SONG",
        "https://s3.filebin.net/filebin/c08376ec0ac682f9575943f68e78dcf61f5a9c9d6b3bc9f9ccb3420a72a53f63/0f0217efbd0328b4c312f8bc31ffe13449d5f3bd401ed2533c3b56e7199b8f6f?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=7pMj6hGeoKewqmMQILjm%2F20250328%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20250328T233625Z&X-Amz-Expires=60&X-Amz-SignedHeaders=host&response-cache-control=max-age%3D60&response-content-disposition=filename%3D%22clear-silent-track.mp3%22&response-content-type=audio%2Fmpeg&X-Amz-Signature=dbefa68d24d1295f89e235e9b79ac43ab0706f53540a7a88a3a800e2b7848446",
    )

    YOUTUBE_USER_AGENT = os.getenv(
        "YOUTUBE_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    )
    YOUTUBE_PROXY = os.getenv("YOUTUBE_PROXY") or None

    # Optional: either mount a Netscape cookies.txt file or provide its base64
    # content as a Render secret. Nothing is required for normal operation.
    COOKIES_PATH = os.getenv("YOUTUBE_COOKIES_PATH") or None
    _cookie_b64 = os.getenv("YOUTUBE_COOKIES_B64")
    if _cookie_b64 and not COOKIES_PATH:
        try:
            cookie_file = Path(tempfile.gettempdir()) / "asoland_youtube_cookies.txt"
            cookie_file.write_bytes(base64.b64decode(_cookie_b64))
            try:
                cookie_file.chmod(0o600)
            except OSError:
                pass
            COOKIES_PATH = str(cookie_file)
        except Exception as exc:
            print(f"⚠️ Could not decode YOUTUBE_COOKIES_B64: {exc}")
            COOKIES_PATH = None

    ADMIN = int(os.getenv("ADMIN", "1000000"))

    with open(Path("app") / "data" / "default_texts.json", encoding="utf-8") as f:
        DEFAULT_TEXTS = json.load(f)


config = Config()
