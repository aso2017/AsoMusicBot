import asyncio
import json
import os
import shutil
import tempfile
import time
from functools import partial
from pathlib import Path

import ffmpeg
import yt_dlp
from shazamio import Shazam
from ytmusicapi import YTMusic

from app.config import config


class DownloadError(Exception):
    """Raised when all configured audio download strategies fail."""


class YtDownload:
    """Reliable audio downloader with multiple YouTube strategies.

    Cookies are optional. The downloader first tries guest-compatible clients,
    then retries with an explicitly configured cookie file when available.
    aria2c is intentionally not required: yt-dlp handles the download itself.
    """

    def __init__(self, data):
        self.data = data
        title = str(data.get("title", "song"))
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in title)
        safe = safe.strip("_")[:80] or "song"
        self.name = safe
        self.path = str(Path("songs") / f"{safe}_{int(time.time() * 1000)}.mp3")
        Path("songs").mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _cookie_path():
        path = config.COOKIES_PATH
        if path and os.path.isfile(path):
            return path
        return None

    @staticmethod
    def _common_options():
        options = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "retries": 2,
            "fragment_retries": 2,
            "file_access_retries": 2,
            "socket_timeout": 25,
            "concurrent_fragment_downloads": 2,
            "http_chunk_size": 10 * 1024 * 1024,
            "geo_bypass": True,
            "restrictfilenames": True,
            "overwrites": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "http_headers": {
                "User-Agent": config.YOUTUBE_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
        if config.YOUTUBE_PROXY:
            options["proxy"] = config.YOUTUBE_PROXY
        return options

    @classmethod
    def _attempts(cls):
        """Return ordered strategies. No cookie is required for the first pass."""
        attempts = []
        cookie = cls._cookie_path()

        # Current yt-dlp guidance favors clients that can work without an
        # authenticated browser session. We keep each strategy separate so a
        # failed client cannot poison the next attempt.
        clients = ["web_safari", "android_vr", "tv"]
        for client in clients:
            opts = cls._common_options()
            opts["extractor_args"] = {"youtube": {"player_client": [client]}}
            attempts.append((f"youtube:{client}", opts))

        if cookie:
            # A cookie-authenticated web_safari attempt is kept as a fallback.
            # We deliberately do not combine cookies with the TV client.
            opts = cls._common_options()
            opts["cookies"] = cookie
            opts["extractor_args"] = {"youtube": {"player_client": ["web_safari"]}}
            attempts.append(("youtube:web_safari+cookies", opts))

        return attempts

    async def download_audio_from_id(self, video_id):
        last_error = None
        loop = asyncio.get_running_loop()
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        for label, base_opts in self._attempts():
            stem = str(Path(self.path).with_suffix(""))
            opts = dict(base_opts)
            opts["outtmpl"] = stem + ".%(ext)s"
            try:
                # Remove leftovers from an earlier failed strategy.
                self._cleanup_outputs(stem)
                download_func = partial(yt_dlp.YoutubeDL(opts).download, [video_url])
                await asyncio.wait_for(loop.run_in_executor(None, download_func), timeout=180)

                candidates = [Path(stem + ".mp3"), *Path(stem).parent.glob(Path(stem).name + ".*")]
                mp3 = next((p for p in candidates if p.suffix.lower() == ".mp3" and p.exists()), None)
                if mp3 and mp3.stat().st_size > 0:
                    self.path = str(mp3)
                    return self.path
                raise DownloadError("yt-dlp completed without producing an MP3")
            except Exception as exc:
                last_error = exc
                print(f"⚠️ Download strategy {label} failed: {exc}")
                self._cleanup_outputs(stem)

        raise DownloadError(str(last_error) if last_error else "No download strategy succeeded")

    @staticmethod
    def _cleanup_outputs(stem):
        parent = Path(stem).parent
        prefix = Path(stem).name + "."
        for item in parent.glob(prefix + "*"):
            try:
                if item.is_file():
                    item.unlink()
            except OSError:
                pass
        for item in parent.glob(Path(stem).name + ".part*"):
            try:
                if item.is_file():
                    item.unlink()
            except OSError:
                pass

    @staticmethod
    def is_supported(url):
        if config.IS_GENERIC_URL_OK:
            return True
        extractors = yt_dlp.extractor.gen_extractors()
        return any(e.suitable(url) and e.IE_NAME != "generic" for e in extractors)

    @staticmethod
    async def download_audio_from_url(url, path):
        if not YtDownload.is_supported(url) or config.DOWNLOAD_URL_SIZE_IN_MB == 0:
            return None

        loop = asyncio.get_running_loop()
        output = str(Path(path).with_suffix("")) + ".%(ext)s"
        opts = YtDownload._common_options()
        opts.update({
            "outtmpl": output,
            "max_filesize": config.DOWNLOAD_URL_SIZE_IN_MB * 1024 * 1024,
        })

        cookie = YtDownload._cookie_path()
        if cookie:
            opts["cookies"] = cookie

        try:
            download_func = partial(yt_dlp.YoutubeDL(opts).download, [url])
            await asyncio.wait_for(loop.run_in_executor(None, download_func), timeout=180)
        except Exception as exc:
            print(f"⚠️ URL download failed: {exc}")
            return None

        mp3 = Path(path).with_suffix(".mp3")
        if mp3.exists():
            return str(mp3)
        # Some extractors produce a different extension before post-processing.
        matches = list(mp3.parent.glob(mp3.stem + ".*"))
        for item in matches:
            if item.suffix.lower() == ".mp3" and item.exists():
                return str(item)
        return None

    def get(self):
        return open(self.path, "rb")

    def remove(self):
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass


class Song:
    @staticmethod
    async def extract_audio_from_video(video_path, delete=True):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
            temp_audio_path = temp_audio.name

        await asyncio.to_thread(
            lambda: ffmpeg.input(video_path)
            .output(temp_audio_path, format="mp3", acodec="mp3", audio_bitrate="128k")
            .run(overwrite_output=True, quiet=True)
        )

        if delete:
            os.remove(video_path)
        return temp_audio_path

    @staticmethod
    async def recognize(file_path, delete=True):
        shazam = Shazam()
        try:
            return await shazam.recognize(file_path)
        finally:
            if delete:
                try:
                    os.remove(file_path)
                except FileNotFoundError:
                    pass

    @staticmethod
    async def search(query, limit=10, offset=0):
        ytmusic = YTMusic()
        loop = asyncio.get_running_loop()
        offset = min(max(offset, 0), 5)
        adjusted_limit = limit * (offset + 1)

        results = await loop.run_in_executor(
            None, ytmusic.search, query, "songs", None, adjusted_limit
        )
        if not results:
            return [], False

        filtered = results[offset * limit:(offset + 1) * limit]
        video_ids = [
            song for song in filtered
            if song.get("videoId") and song.get("duration_seconds", 0) < 700
        ]
        has_more = len(results) >= adjusted_limit and offset < 4
        return video_ids, has_more

    @staticmethod
    async def get(song):
        ytmusic = YTMusic()
        loop = asyncio.get_running_loop()
        search_results = await loop.run_in_executor(None, ytmusic.search, song, "songs")
        return search_results[0] if search_results else None

    @staticmethod
    async def get_lyrics(song_id):
        ytmusic = YTMusic()
        loop = asyncio.get_running_loop()
        search_info = await loop.run_in_executor(None, ytmusic.get_watch_playlist, song_id)
        lyrics_id = search_info.get("lyrics") if search_info else None
        if not lyrics_id:
            return None
        result = await loop.run_in_executor(None, ytmusic.get_lyrics, lyrics_id)
        return result.get("lyrics") if result else None
