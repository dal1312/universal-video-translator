from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from .transcription import ensure_ffmpeg


class DownloadError(RuntimeError):
    pass


def is_web_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def download_video(
    url: str, directory: str | Path, cookies_browser: str | None = None
) -> Path:
    if not is_web_url(url):
        raise DownloadError("URL non valido.")
    try:
        import yt_dlp
    except ImportError as exc:
        raise DownloadError(
            "yt-dlp non installato. Esegui: pip install -e .[youtube]"
        ) from exc

    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bv*+ba/b",
        "outtmpl": str(target / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-orig", "es", "fr", "de"],
        "subtitlesformat": "vtt",
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": str(Path(ensure_ffmpeg()).parent),
        "js_runtimes": {"deno": {}},
        "remote_components": {"ejs:github"},
    }
    if cookies_browser:
        options["cookiesfrombrowser"] = (cookies_browser,)
    def extract(download_options):
        with yt_dlp.YoutubeDL(download_options) as downloader:
            info = downloader.extract_info(url, download=True)
            prepared = Path(downloader.prepare_filename(info))
            return [
                path
                for path in (
                    prepared,
                    prepared.with_suffix(".mp4"),
                    prepared.with_suffix(".mkv"),
                    prepared.with_suffix(".webm"),
                )
                if path.exists()
            ]

    try:
        candidates = extract(options)
    except Exception as exc:
        detail = str(exc)
        subtitle_failure = (
            "video subtitles" in detail.casefold()
            or "too many requests" in detail.casefold()
            or "http error 429" in detail.casefold()
        )
        if not subtitle_failure:
            raise DownloadError(f"Download non riuscito: {exc}") from exc
        fallback = dict(options)
        for key in (
            "writesubtitles",
            "writeautomaticsub",
            "subtitleslangs",
            "subtitlesformat",
        ):
            fallback.pop(key, None)
        try:
            candidates = extract(fallback)
        except Exception as fallback_exc:
            raise DownloadError(
                f"Download non riuscito: {fallback_exc}"
            ) from fallback_exc
    if not candidates:
        raise DownloadError("yt-dlp non ha prodotto un file video.")
    return max(candidates, key=lambda path: path.stat().st_size)
