from __future__ import annotations

import array
import importlib.util
import json
import os
import queue
import shutil
import sqlite3
import subprocess
import threading
import uuid
import wave
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .contracts import canonical_json, sqlite_connection
from .recovery import RecoveryVault
from .universal_text import UniversalAssetStore

DDL = """
CREATE TABLE IF NOT EXISTS audio_clips (
    clip_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    consent_basis TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id TEXT PRIMARY KEY,
    clip_id TEXT NOT NULL REFERENCES audio_clips(clip_id),
    backend TEXT NOT NULL,
    culture TEXT NOT NULL,
    text TEXT NOT NULL,
    segments_json TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS voice_messages (
    message_id TEXT PRIMARY KEY,
    direction TEXT NOT NULL,
    text TEXT NOT NULL,
    culture TEXT NOT NULL,
    spoken INTEGER NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS monitor_sessions (
    session_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    consent_basis TEXT NOT NULL,
    participant_notice TEXT,
    started_at TEXT NOT NULL,
    stopped_at TEXT,
    state TEXT NOT NULL,
    indicator_required INTEGER NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class AudioHub:
    """Exact audio custody, batch transcription, proactive TTS, and optional VAD monitor."""

    def __init__(
        self, root: str | Path, *, on_transcript: Callable[[dict[str, Any]], None] | None = None
    ):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "audio.sqlite3"
        self.assets = UniversalAssetStore(self.root / "universal")
        self.vault = RecoveryVault(self.root / "recovery")
        self.on_transcript = on_transcript
        self._monitor_thread: threading.Thread | None = None
        self._monitor_stop = threading.Event()
        self._monitor_session: str | None = None
        with self.connect() as connection:
            connection.executescript(DDL)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @property
    def audio_data_root(self) -> Path:
        return Path(__file__).resolve().parent / "data" / "audio"

    def backends(self) -> dict[str, Any]:
        windows_speech = (
            os.name == "nt" and (self.audio_data_root / "transcribe_windows.ps1").is_file()
        )
        return {
            "windows_system_speech": {
                "available": windows_speech,
                "mode": "LOCAL_BATCH_WAV",
                "cultures_probed": ["es-ES", "en-US"],
            },
            "openai_whisper": {
                "available": bool(importlib.util.find_spec("whisper")),
                "mode": "LOCAL_BATCH",
                "ffmpeg": bool(shutil.which("ffmpeg")),
            },
            "sounddevice_monitor": {
                "available": bool(importlib.util.find_spec("sounddevice")),
                "mode": "LOCAL_VAD_SEGMENTED_CAPTURE",
            },
            "streaming_claim": "NOT_NATIVE_WHISPER_STREAMING",
        }

    def ingest_and_transcribe(
        self, source: str | Path, *, culture: str = "es-ES", consent_basis: str = "USER_OWN_AUDIO"
    ) -> dict[str, Any]:
        path = Path(source).resolve()
        manifest = self.assets.ingest(path)
        clip_id = f"ACLIP-{uuid.uuid4()}"
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audio_clips VALUES(?,?,?,?,?,?,?,?)",
                (
                    clip_id,
                    manifest["asset_id"],
                    path.name,
                    manifest["original"]["content_sha256"],
                    "IMPORTED_CLIP",
                    consent_basis,
                    "CUSTODIED",
                    timestamp,
                ),
            )
            connection.commit()
        backend = self.backends()
        if path.suffix.lower() == ".wav" and backend["windows_system_speech"]["available"]:
            transcript = self._transcribe_windows(clip_id, path, culture)
        elif backend["openai_whisper"]["available"] and backend["openai_whisper"]["ffmpeg"]:
            transcript = self._transcribe_whisper(clip_id, path, culture)
        else:
            transcript = {
                "clip_id": clip_id,
                "state": "TRANSCRIPTION_PENDING_BACKEND",
                "audio_custodied": True,
                "available_backends": backend,
            }
        return {
            "clip": {
                "clip_id": clip_id,
                "asset_manifest": manifest,
                "consent_basis": consent_basis,
            },
            "transcription": transcript,
        }

    def _save_transcript(
        self,
        clip_id: str,
        *,
        backend: str,
        culture: str,
        text: str,
        segments: list[dict[str, Any]],
        state: str,
    ) -> dict[str, Any]:
        transcript_id = f"TRANSCRIPT-{uuid.uuid4()}"
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO transcripts VALUES(?,?,?,?,?,?,?,?)",
                (
                    transcript_id,
                    clip_id,
                    backend,
                    culture,
                    text,
                    canonical_json(segments),
                    state,
                    timestamp,
                ),
            )
            connection.execute("UPDATE audio_clips SET state=? WHERE clip_id=?", (state, clip_id))
            connection.commit()
        value = {
            "transcript_id": transcript_id,
            "clip_id": clip_id,
            "backend": backend,
            "culture": culture,
            "text": text,
            "segments": segments,
            "state": state,
        }
        custody = self.vault.save_json(
            f"transcripts/{transcript_id}.json",
            value,
            kind="AUDIO_TRANSCRIPT",
            actor="KCH_SYSTEM",
            operation="TRANSCRIBE",
        )
        result = {**value, "custody": custody}
        if self.on_transcript:
            self.on_transcript(result)
        return result

    def _transcribe_windows(self, clip_id: str, path: Path, culture: str) -> dict[str, Any]:
        output = self.root / "transcription_work" / f"{clip_id}.json"
        output.parent.mkdir(exist_ok=True)
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.audio_data_root / "transcribe_windows.ps1"),
            "-InputWav",
            str(path),
            "-OutputJson",
            str(output),
            "-Culture",
            culture,
        ]
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=600, shell=False
        )
        if completed.returncode != 0 or not output.is_file():
            return self._save_transcript(
                clip_id,
                backend="WINDOWS_SYSTEM_SPEECH",
                culture=culture,
                text="",
                segments=[],
                state="TRANSCRIPTION_FAILED_PRESERVED",
            ) | {"error_type": "BACKEND_PROCESS_FAILURE", "stderr": completed.stderr[-2000:]}
        value = json.loads(output.read_text(encoding="utf-8-sig"))
        return self._save_transcript(
            clip_id,
            backend="WINDOWS_SYSTEM_SPEECH",
            culture=culture,
            text=str(value.get("text", "")),
            segments=list(value.get("segments", [])),
            state="TRANSCRIBED_LOCAL",
        )

    def _transcribe_whisper(self, clip_id: str, path: Path, culture: str) -> dict[str, Any]:
        import whisper

        model_name = os.environ.get("KCH_WHISPER_MODEL", "small")
        model = whisper.load_model(model_name)
        value = model.transcribe(
            str(path), language=culture.split("-")[0], word_timestamps=True, verbose=False
        )
        segments = [
            {
                key: item.get(key)
                for key in ("id", "start", "end", "text", "avg_logprob", "no_speech_prob")
            }
            for item in value.get("segments", [])
        ]
        return self._save_transcript(
            clip_id,
            backend=f"OPENAI_WHISPER_{model_name}",
            culture=culture,
            text=str(value.get("text", "")),
            segments=segments,
            state="TRANSCRIBED_LOCAL",
        )

    def speak(self, text: str, *, culture: str = "es-ES", wait: bool = False) -> dict[str, Any]:
        message_id = f"VOICE-{uuid.uuid4()}"
        timestamp = utc_now()
        text_path = self.root / "voice_messages" / f"{message_id}.txt"
        text_path.parent.mkdir(exist_ok=True)
        text_path.write_text(text, encoding="utf-8")
        script = self.audio_data_root / "speak_windows.ps1"
        if os.name == "nt" and script.is_file():
            command = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-InputText",
                str(text_path),
                "-Culture",
                culture,
            ]
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            if wait:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    creationflags=flags,
                    shell=False,
                )
                spoken = completed.returncode == 0
                state = "SPOKEN" if spoken else "TTS_FAILED_PRESERVED"
            else:
                subprocess.Popen(command, creationflags=flags, shell=False)
                spoken = True
                state = "TTS_LAUNCHED"
        else:
            spoken = False
            state = "TTS_BACKEND_UNAVAILABLE"
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO voice_messages VALUES(?,?,?,?,?,?,?)",
                (message_id, "KCH_TO_USER", text, culture, int(spoken), state, timestamp),
            )
            connection.commit()
        custody = self.vault.save(
            f"voice/messages/{message_id}.txt",
            text,
            kind="KCH_VOICE_MESSAGE_TRANSCRIPT",
            actor="KCH_SYSTEM",
            operation="SPEAK",
        )
        return {
            "message_id": message_id,
            "text": text,
            "culture": culture,
            "state": state,
            "spoken": spoken,
            "transcript_custody": custody,
        }

    @staticmethod
    def _rms(chunk: bytes) -> float:
        values = array.array("h")
        values.frombytes(chunk)
        if not values:
            return 0.0
        return (sum(value * value for value in values) / len(values)) ** 0.5

    def start_monitor(
        self,
        *,
        mode: str = "BRAINSTORM_USER_ONLY",
        consent_basis: str,
        participant_notice: str | None = None,
        culture: str = "es-ES",
        threshold: float = 550.0,
        silence_seconds: float = 1.2,
    ) -> dict[str, Any]:
        if mode == "THIRD_PARTY_CONVERSATION" and not participant_notice:
            raise ValueError(
                "third-party conversation mode requires a recorded participant notice/consent basis"
            )
        if self._monitor_thread and self._monitor_thread.is_alive():
            return self.status()
        if not self.backends()["sounddevice_monitor"]["available"]:
            return {
                "state": "MONITOR_BACKEND_UNAVAILABLE",
                "audio_recorded": False,
                "backends": self.backends(),
            }
        session_id = f"AMON-{uuid.uuid4()}"
        timestamp = utc_now()
        self._monitor_session = session_id
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO monitor_sessions VALUES(?,?,?,?,?,?,?,?)",
                (
                    session_id,
                    mode,
                    consent_basis,
                    participant_notice,
                    timestamp,
                    None,
                    "RUNNING_VISIBLE_INDICATOR_REQUIRED",
                    1,
                ),
            )
            connection.commit()
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(session_id, culture, threshold, silence_seconds, consent_basis),
            name="kch-audio-monitor",
            daemon=True,
        )
        self._monitor_thread.start()
        return self.status()

    def _monitor_loop(
        self,
        session_id: str,
        culture: str,
        threshold: float,
        silence_seconds: float,
        consent_basis: str,
    ) -> None:
        import sounddevice as sd

        sample_rate = 16000
        blocksize = 1600
        blocks_silence = max(1, int(silence_seconds * sample_rate / blocksize))
        incoming: queue.SimpleQueue[bytes] = queue.SimpleQueue()

        def callback(indata: Any, frames: int, timing: Any, status: Any) -> None:
            incoming.put(bytes(indata))

        active: list[bytes] = []
        silent = 0
        with sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=blocksize,
            channels=1,
            dtype="int16",
            callback=callback,
        ):
            while not self._monitor_stop.is_set():
                try:
                    chunk = incoming.get(timeout=0.2)
                except queue.Empty:
                    continue
                if self._rms(chunk) >= threshold:
                    active.append(chunk)
                    silent = 0
                elif active:
                    active.append(chunk)
                    silent += 1
                if active and (silent >= blocks_silence or len(active) >= 600):
                    raw = b"".join(active)
                    active = []
                    silent = 0
                    path = self.root / "monitor_audio" / session_id / f"{uuid.uuid4()}.wav"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with wave.open(str(path), "wb") as stream:
                        stream.setnchannels(1)
                        stream.setsampwidth(2)
                        stream.setframerate(sample_rate)
                        stream.writeframes(raw)
                    self.ingest_and_transcribe(path, culture=culture, consent_basis=consent_basis)

    def stop_monitor(self) -> dict[str, Any]:
        self._monitor_stop.set()
        if self._monitor_thread:
            self._monitor_thread.join(5)
        if self._monitor_session:
            with self.connect() as connection:
                connection.execute(
                    "UPDATE monitor_sessions SET stopped_at=?,state='STOPPED' WHERE session_id=?",
                    (utc_now(), self._monitor_session),
                )
                connection.commit()
        return self.status()

    def status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            clips = connection.execute("SELECT COUNT(*) FROM audio_clips").fetchone()[0]
            transcripts = connection.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
        return {
            "schema": "kch.audio-hub-status.v0.1.0",
            "monitor_running": bool(self._monitor_thread and self._monitor_thread.is_alive()),
            "monitor_session": self._monitor_session,
            "visible_indicator_required": True,
            "clips_custodied": clips,
            "transcripts": transcripts,
            "backends": self.backends(),
            "microphone_activated_during_build": False,
        }
