from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
import json
import pathlib
from controller import *

class AmendmentType(Enum):
    ADD = "ADD"
    AMEND = "AMEND"
    STRIKE = "STRIKE"

@dataclass
class Amendment:
    submitter_delegate: str
    resolution_main_submitter: str
    resolution_topic: str

    clause: str
    sub_clause: Optional[str] = None
    sub_sub_clause: Optional[str] = None

    context: str = ""

    amendment_type: AmendmentType = AmendmentType.ADD
    text: Optional[str] = None
    reason: Optional[str] = None

    friendly: bool = False

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self):
        self._validate()

    def _validate(self):
        if self.amendment_type in {AmendmentType.ADD, AmendmentType.AMEND}:
            if not self.text or not self.text.strip():
                raise ValueError("ADD / AMEND amendments require non-empty text.")

        if self.amendment_type == AmendmentType.STRIKE:
            if self.text:
                raise ValueError("STRIKE amendments must not include text.")

        if not self.submitter_delegate.strip():
            raise ValueError("Submitter delegate cannot be empty.")

        if not self.clause:
            raise ValueError("Clause must be specified.")

@dataclass
class AmendmentSession:
    session_name: str
    committee: str

    amendments: List[Amendment] = field(default_factory=list)
    current_index: int = 0
    schema_version: int = 1
    source_path: str = "./session.json"

    # ---------- Navigation ----------

    def current(self) -> Amendment:
        if not self.amendments:
            raise IndexError("No amendments in session.")
        return self.amendments[self.current_index]

    def next(self):
        if self.current_index < len(self.amendments) - 1:
            self.current_index += 1

    def previous(self):
        if self.current_index > 0:
            self.current_index -= 1

    def first(self):
        self.current_index = 0

    def last(self):
        if self.amendments:
            self.current_index = len(self.amendments) - 1
    
    # ---------- Chair controls ----------

    def toggle_friendly(self):
        amendment = self.current()
        amendment.friendly = not amendment.friendly

    def toggle_reason_visibility(self):
        amendment = self.current()
        amendment.reason = None if amendment.reason else amendment.reason
        # UI will decide how to interpret visibility

    def save(self, path: str | pathlib.Path | None = None):
        if path is None:
            path = self.source_path
        path = pathlib.Path(path)
        payload = {
            "schema_version": self.schema_version,
            "session": {
                "session_name": self.session_name,
                "committee": self.committee,
                "current_index": self.current_index,
            },
            "amendments": [
                {
                    **asdict(a),
                    "amendment_type": a.amendment_type.value
                }
                for a in self.amendments
            ]
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    
    
    @classmethod
    def load(cls, path: str | pathlib.Path) -> AmendmentSession:
        path = pathlib.Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))

        session_info = data["session"]
        amendments = []

        for raw in data["amendments"]:
            raw["amendment_type"] = AmendmentType(raw["amendment_type"])
            amendments.append(Amendment(**raw))

        session = cls(
            session_name=session_info["session_name"],
            committee=session_info["committee"],
            amendments=amendments,
            current_index=session_info.get("current_index", 0)
        )
        return session


if __name__ == "__main__":
    session = AmendmentSession.load("session.json")
    app = AmendmentApp(session)
    app.mainloop()