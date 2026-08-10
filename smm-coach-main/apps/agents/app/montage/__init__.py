"""Professional video montage subsystem.

A roster of one-agent-per-aspect emits small, validated JSON specs into a single
shared Edit-Decision-List (EDL); a deterministic Python compiler turns the merged
EDL into ONE ffmpeg filter_complex and renders once. LLMs never touch pixels and
never emit raw ffmpeg — they only produce the JSON the compiler consumes, mirroring
the codebase's "agents emit data, deterministic code acts" discipline.

See `edl.py` for the contract every montage node depends on.
"""
