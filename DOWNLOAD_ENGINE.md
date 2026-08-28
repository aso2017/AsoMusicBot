# Download Engine Notes

AsoMusicBot no longer treats YouTube cookies as the primary download mechanism.

The order is:

1. YouTube `web_safari` client without cookies.
2. YouTube `android_vr` client without cookies.
3. YouTube `tv` client without cookies.
4. If configured, `web_safari` with a Netscape/Mozilla cookies file.

No `aria2c` binary is required.

When a song is successfully sent to Telegram, its `file_id` is stored in the existing `musics.file_id` field. Future requests reuse that Telegram file instead of downloading the same source again.

The public `Info` button points to:

`https://song.link/y/<youtube-video-id>`

This is intentionally based on the same YouTube video ID used by the music search result.
