from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from .transcription import ensure_ffmpeg


class DownloadError(RuntimeError):
    pass


SOURCE_LANGUAGE_CODES = {
    "inglese": "en",
    "spagnolo": "es",
    "francese": "fr",
    "tedesco": "de",
}


def is_web_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def subtitle_language_candidates(
    source_language: str,
    metadata_language: str | None,
    available_languages: list[str] | tuple[str, ...],
) -> list[str]:
    available = list(dict.fromkeys(
        language for language in available_languages if language != "live_chat"
    ))
    selected = SOURCE_LANGUAGE_CODES.get(
        source_language.casefold(), source_language.casefold()
    )
    if selected in {"", "auto"}:
        selected = (metadata_language or "").casefold().replace("_", "-")

    if selected:
        base = selected.split("-", 1)[0]
        preferred = [selected, base, f"{selected}-orig", f"{base}-orig"]
        for language in dict.fromkeys(preferred):
            if language in available:
                return [language]

        for language in available:
            if language == base or language.startswith(f"{base}-"):
                return [language]
        return []

    original_tracks = [
        language for language in available if language.endswith("-orig")
    ]
    if len(original_tracks) == 1:
        return original_tracks
    if len(available) == 1:
        return available
    return []


def download_video(
    url: str,
    directory: str | Path,
    cookies_browser: str | None = None,
    source_language: str = "auto",
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
        "subtitlesformat": "vtt",
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": str(Path(ensure_ffmpeg()).parent),
        "js_runtimes": {"deno": {}},
        "remote_components": {"ejs:github"},
    }
    if cookies_browser:
        options["cookiesfrombrowser"] = (cookies_browser,)

    def extract(download_options, include_subtitles: bool = True):
        with yt_dlp.YoutubeDL(download_options) as downloader:
            info = downloader.extract_info(url, download=False)
            if include_subtitles:
                subtitles = info.get("subtitles") or {}
                automatic = info.get("automatic_captions") or {}
                languages = subtitle_language_candidates(
                    source_language,
                    info.get("language"),
                    [*subtitles, *automatic],
                )
                downloader.params.update(
                    {
                        "writesubtitles": bool(languages),
                        "writeautomaticsub": bool(languages),
                        "subtitleslangs": languages,
                    }
                )
            else:
                downloader.params.update(
                    {
                        "writesubtitles": False,
                        "writeautomaticsub": False,
                        "subtitleslangs": [],
                    }
                )
            info = downloader.process_ie_result(info, download=True)
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
        try:
            candidates = extract(fallback, include_subtitles=False)
        except Exception as fallback_exc:
            raise DownloadError(
                f"Download non riuscito: {fallback_exc}"
            ) from fallback_exc
    if not candidates:
        raise DownloadError("yt-dlp non ha prodotto un file video.")
    return max(candidates, key=lambda path: path.stat().st_size)
