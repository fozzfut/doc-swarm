"""Session management for DocSwarm."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .models import DocIssue, DocPage, now_iso

_STORAGE_DIR = Path("~/.doc-swarm").expanduser()


class Session:
    """A documentation generation/verification session."""

    def __init__(self, session_id: str, session_dir: Path) -> None:
        self.session_id = session_id
        self._dir = session_dir
        self._pages: list[DocPage] = []
        self._issues: list[DocIssue] = []
        self._lock = threading.Lock()

    def add_page(self, page: DocPage) -> None:
        with self._lock:
            self._pages.append(page)
            self._save_pages()

    def add_issue(self, issue: DocIssue) -> None:
        with self._lock:
            self._issues.append(issue)
            self._save_issues()

    @property
    def pages(self) -> list[DocPage]:
        with self._lock:
            return list(self._pages)

    @property
    def issues(self) -> list[DocIssue]:
        with self._lock:
            return list(self._issues)

    def write_docs(self, output_dir: Path) -> list[str]:
        """Write all generated doc pages to the output directory."""
        written = []
        output_dir.mkdir(parents=True, exist_ok=True)
        for page in self._pages:
            path = output_dir / page.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(page.to_markdown(), encoding="utf-8")
            written.append(str(page.path))
        return written

    def _save_pages(self) -> None:
        path = self._dir / "pages.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for page in self._pages:
                fh.write(json.dumps(page.to_dict()) + "\n")

    def _save_issues(self) -> None:
        path = self._dir / "issues.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for issue in self._issues:
                fh.write(json.dumps(issue.to_dict()) + "\n")

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "pages": len(self._pages),
            "issues": len(self._issues),
        }


class SessionManager:
    """Manages DocSwarm sessions."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._storage = storage_dir or _STORAGE_DIR
        self._sessions_dir = self._storage / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()

    def start_session(self, project_path: str, name: str | None = None) -> Session:
        with self._lock:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            seq = len(list(self._sessions_dir.glob(f"doc-{today}-*"))) + 1
            session_id = f"doc-{today}-{seq:03d}"

            sess_dir = self._sessions_dir / session_id
            sess_dir.mkdir(parents=True, exist_ok=True)

            meta = {
                "session_id": session_id,
                "project_path": project_path,
                "name": name or session_id,
                "created_at": now_iso(),
                "status": "active",
            }
            (sess_dir / "meta.json").write_text(
                json.dumps(meta, indent=2), encoding="utf-8"
            )

            session = Session(session_id, sess_dir)
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> Session:
        with self._lock:
            if session_id not in self._sessions:
                sess_dir = self._sessions_dir / session_id
                if not sess_dir.exists():
                    raise KeyError(f"Session {session_id} not found")
                self._sessions[session_id] = Session(session_id, sess_dir)
            return self._sessions[session_id]
