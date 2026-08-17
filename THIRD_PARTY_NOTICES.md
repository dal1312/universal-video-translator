# Third-Party Notices

Universal Video Translator includes or uses third-party software. The project
license does not replace the licenses of these components.

## SoundVolumeView 2.53

- Author: Nir Sofer / NirSoft
- Website: <https://www.nirsoft.net/utils/sound_volume_view.html>
- Files are redistributed unmodified as the complete vendor package:
  `SoundVolumeView.exe`, `SoundVolumeView.chm`, and `readme.txt`.
- The authoritative license and redistribution conditions are in
  `licenses/SoundVolumeView-readme.txt` inside the release.
- The vendor terms restrict charging for or commercially bundling the utility.
  Review those terms before commercial distribution.

## FFmpeg 8.1.2 Full Build

- Project: <https://ffmpeg.org/>
- Windows build source: <https://www.gyan.dev/ffmpeg/builds/>
- License: GPL v3 or later for the bundled full build.
- The release contains the distributor's `LICENSE` as
  `licenses/FFmpeg-LICENSE.txt`.
- FFmpeg source and build information are available from the links above.

## Python Runtime Components

The `_internal` directory contains Python and packages installed from PyPI,
including PyInstaller, Faster-Whisper, CTranslate2, PyTorch, Kokoro, SoundCard,
yt-dlp, Argos Translate, and their dependencies. Argos Translate 1.11.0 is
distributed under MIT and CC0-1.0 terms. Each component remains subject to its own
license. Exact versions used by the validated Windows environment are recorded
in `requirements/windows-py310-x64.constraints.txt` in the source repository
and in `PROVENANCE.json` for packaged releases.

## External Components

Ollama, the selected Ollama model, Deno, VB-Cable, Argos language packages, and
downloaded AI models are not included in the portable archive. Their own
licenses and privacy policies apply when users install or download them. Voice
and translation model licenses must be reviewed and accepted separately before
download.
