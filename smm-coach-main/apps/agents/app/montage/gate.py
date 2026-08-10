"""Process-wide serialization for heavy ffmpeg ENCODES.

The montage render worker and the studio-source transcode both shell out to a
CPU-bound libx264 ffmpeg. On a GPU-less box two encodes at once pin every core and
thrash each other (and the rest of the agents process). This gate ensures at most
ONE heavy encode runs at a time across the whole process — they queue instead of
racing. It is a `threading.Semaphore` (not asyncio) because the encodes run inside
`asyncio.to_thread`/threads, not on the event loop.

NOTE: gate only the heavy ENCODE, never ffprobe (the input-guard probe must stay
fast and not queue behind a render).
"""
from __future__ import annotations

import threading

ENCODE_GATE = threading.Semaphore(1)
