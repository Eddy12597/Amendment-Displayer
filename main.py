from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from enum import Enum
import html2text
import json
import os
from pathlib import Path
from typing import Any, List, Optional
import re
import roman
from uuid import uuid4

import dotenv
from openai import OpenAI

from controller import *
from emailingestor import *
from reso.core.operationals import clause, subclause, subsubclause
from reso.core.preambs import preamb
from reso.core.resolution import Resolution
from reso import document
from util import *

dotenv.load_dotenv(dotenv.find_dotenv())

class AmendmentType(Enum):
    ADD = "ADD"
    AMEND = "AMEND"
    STRIKE = "STRIKE"

@dataclass
class Amendment:
    submitter_delegate: str
    
    # these string-based fields will be replaced in the future
    clause: str
    sub_clause: Optional[str] = None
    sub_sub_clause: Optional[str] = None
    
    resolution_main_submitter: str | None = None
    resolution_topic: str | None = None
    
    address_resolution: Resolution | None = None
    address_node: clause | subclause | subsubclause | None = None

    context: str = ""

    amendment_type: AmendmentType = AmendmentType.ADD
    text: Optional[str] = None
    reason: Optional[str] = None

    friendly: bool = False

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


    def __post_init__(self):
        self._validate()

    def _validate(self):
        if self.amendment_type in {AmendmentType.ADD, AmendmentType.AMEND}:
            if not self.text or not self.text.strip():
                log << Lvl.warn << "ADD/AMEND-Empty Text" << endl
                raise ValueError("ADD/AMEND amendments require non-empty text.")

        if self.amendment_type == AmendmentType.STRIKE:
            if self.text:
                log << Lvl.warn << "STK-Text" << endl
                raise ValueError("STRIKE amendments must not include text.")

        if not self.submitter_delegate.strip():
            log << Lvl.warn << "EMPTY-Sub" << endl
            raise ValueError("Submitter delegate cannot be empty.")

        if not self.clause:
            log << Lvl.warn << "NO-CLAUSE" << endl
            raise ValueError("Clause must be specified.")
    
    @classmethod
    @Log
    def from_json(cls, js: dict[str, Any]) -> Amendment | None:
        """
        Create an Amendment instance from a JSON-like dictionary.
        Keys in js should correspond to Amendment fields.
        """
        if not isinstance(js, dict):
            log << Lvl.warn << f"from_json expected dict, got {type(js)}" << endl
            raise TypeError("Input must be a dictionary.")
        if js == {} or js is None:
            log << Lvl.warn << "Empty JSON for Amendment" << endl
            return None
        required_fields = ["submitter_delegate", "clause"]#, "resolution_main_submitter", "resolution_topic"]
        if any(field not in js or not js[field] for field in required_fields):
            log << Lvl.warn << f"Missing required fields: {', '.join(f for f in required_fields if f not in js or not js[f])}" << endl
            return None
        # Extract values safely, fallback to None if missing
        submitter_delegate = js.get("submitter_delegate", "").strip()
        resolution_main_submitter = js.get("resolution_main_submitter")
        resolution_topic = js.get("resolution_topic")

        clause = js.get("clause", "").strip()
        sub_clause = js.get("sub_clause")
        sub_sub_clause = js.get("sub_sub_clause")
        context = js.get("context", "")

        # Handle AmendmentType, allow string input
        amendment_type_val = js.get("amendment_type", "AMEND")
        if isinstance(amendment_type_val, str):
            try:
                amendment_type = AmendmentType[amendment_type_val.upper()]
            except KeyError:
                log << Lvl.warn << f"Unknown amendment_type '{amendment_type_val}', defaulting to AMEND" << endl
                amendment_type = AmendmentType.AMEND
        else:
            amendment_type = amendment_type_val  # assume already an AmendmentType

        text = js.get("text")
        reason = js.get("reason")
        friendly = js.get("friendly", False)

        # Optional: allow id and created_at to be set from JSON
        id_val = js.get("id")
        created_at_val = js.get("created_at")

        return cls(
            submitter_delegate=submitter_delegate,
            resolution_main_submitter=resolution_main_submitter,
            resolution_topic=resolution_topic,
            clause=clause,
            sub_clause=sub_clause,
            sub_sub_clause=sub_sub_clause,
            context=context,
            amendment_type=amendment_type,
            text=text,
            reason=reason,
            friendly=friendly,
            id=id_val or str(uuid4()),
            created_at=created_at_val or datetime.utcnow().isoformat(),
        )
    
    @classmethod
    def infer_resolution(cls, amendment_list: list[Amendment], cur_id: int, reso_list: list[Resolution], basic_similarity_cutoff: int = 25) -> Resolution | None:
        nearby_amendments: list[Amendment] = []
        if len(amendment_list) > cur_id >= 0:
            if cur_id == 0:
                nearby_amendments.append(amendment_list[1])
            else:
                nearby_amendments.extend([amendment_list[cur_id-1], amendment_list[cur_id+1]])
        ans = None
        # both the same
        if nearby_amendments[0].resolution_topic == nearby_amendments[1].resolution_topic:
            r = None
            maxsim = 0
            sim_reso = None
            for res in reso_list:
                if res.topic == nearby_amendments[0].resolution_topic or (maxsim := max(similarity(res.topic, nearby_amendments[0].resolution_topic), maxsim)) >= basic_similarity_cutoff:
                    log << Lvl.info << "Resolution topic " << res.topic << " and that from nearby amendment, " << nearby_amendments[0].resolution_topic << " currently has highest similarity score of " << maxsim << endl
                    r = res.topic
                    sim_reso = res
            if r is None or sim_reso is None:
                ans = None
            else:
                return sim_reso
        else:
            # decide based on which one has most similar match in
            sims: list[float] = [0, 0]
            resos: list[Resolution | None] = [None, None]
            for i in range(2):
                cur_amd_topic = nearby_amendments[i].resolution_topic
                r = None
                maxsim = 0
                sim_reso = None
                for res in reso_list:
                    if res.topic == cur_amd_topic or (maxsim := max(similarity(res.topic, cur_amd_topic), maxsim)) >= basic_similarity_cutoff:
                        log << Lvl.info << "Resolution topic " << res.topic << " and that from nearby amendment, " << cur_amd_topic << " currently has highest similarity score of " << maxsim << endl
                        r = res.topic
                        sim_reso = res
                if r is None or sim_reso is None:
                    ans = None
                else:
                    sims[i] = maxsim
                    resos[i] = sim_reso
            if sims[0] > sims[1]:
                ans = resos[0] or None
            else:
                ans = resos[1] or None
        return ans                    

                
    
    @classmethod
    def attempt_basic_parsing(cls, em: Email) -> Amendment | None:
        """
        Basic parsing to extract a single Amendment from an email without AI.
        Handles common patterns like Submitter, Delegate, Clause, Action/Amendment Type, Text, Reason.
        Returns None if required fields cannot be found.
        """
        body = getattr(em, "body", "") or ""
        subject = getattr(em, "subject", "") or ""
        lines = body.splitlines()

        # Map common label synonyms to standardized keys
        field_patterns = {
            "submitter_delegate": [
                r"Submitter\s*:\s*(.+)",
                r"Delegate\s*:\s*(.+)"
            ],
            "amendment_type": [
                r"Amendment Type\s*:\s*(ADD|AMEND|STRIKE)",
                r"Action\s*:\s*(ADD|AMEND|STRIKE)",
                r"Amendment\s*:\s*(ADD|AMEND|STRIKE)"
            ],
            "resolution_main_submitter": [
                r"Resolution\s*:\s*(?:On .+), by (.+)",
                r"Resolution Topic\s*:\s*(?:On .+)",
                r"Main Submitter\s*:\s*(.+)"
            ],
            "resolution_topic": [
                r"Resolution\s*:\s*(On .+?), by .+",
                r"Resolution Topic\s*:\s*(On .+)",
            ],
            "clause": [
                r"Clause\s*[: ]\s*([\d\.\w]+)",
                r"Location\s*:\s*Clause\s*([\d\.\w]+)",
                r"Target\s*:\s*Clause\s*([\d\.\w]+)"
            ],
            "sub_clause": [
                r"Sub[- ]?clause\s*[: ]\s*([\da-z\(\)]+)"
            ],
            "sub_sub_clause": [
                r"Sub[- ]?sub[- ]?clause\s*[: ]\s*([\da-z\(\)]+)"
            ],
            "text": [
                r"New Text\s*:\s*(.+)",
                r"Revised Wording\s*:\s*(.+)",
                r"We propose\s*:\s*(.+)",
            ],
            "reason": [
                r"Reason\s*:\s*(.+)",
                r"Justification\s*:\s*(.+)"
            ]
        }

        def extract_first_match(patterns: list[str]):
            for pat in patterns:
                match = re.search(pat, body, re.IGNORECASE)# | re.DOTALL)
                if match:
                    if match.lastindex:  # at least one capture group
                        return match.group(1).strip()
                    else:
                        return match.group(0).strip()
            return None


        # Extract fields
        submitter_delegate = extract_first_match(field_patterns["submitter_delegate"])
        amendment_type_str = extract_first_match(field_patterns["amendment_type"])
        amendment_type = AmendmentType[amendment_type_str.upper()] if amendment_type_str else AmendmentType.ADD
        resolution_main_submitter = extract_first_match(field_patterns["resolution_main_submitter"]) or submitter_delegate
        resolution_topic = extract_first_match(field_patterns["resolution_topic"]) or ""
        clause = extract_first_match(field_patterns["clause"])
        sub_clause = extract_first_match(field_patterns["sub_clause"])
        sub_sub_clause = extract_first_match(field_patterns["sub_sub_clause"])
        if clause:
            # Split clause like "4.a.ii" → clause="4", sub_clause="a", sub_sub_clause="ii"
            parts = clause.split(".")
            if len(parts) >= 1:
                clause = parts[0]
            if len(parts) >= 2:
                sub_clause = sub_clause or parts[1]
            if len(parts) >= 3:
                sub_sub_clause = sub_sub_clause or parts[2]
        text = extract_first_match(field_patterns["text"]) if amendment_type in {AmendmentType.ADD, AmendmentType.AMEND} else None
        reason = extract_first_match(field_patterns["reason"])
        context = body

        # Validate required fields
        if not submitter_delegate or not clause: # or not resolution_main_submitter:
            log << Lvl.warn << "Basic parsing failed: missing required fields" << endl
            return None
        
        return cls(
            submitter_delegate=submitter_delegate,
            resolution_main_submitter=resolution_main_submitter,
            resolution_topic=resolution_topic,
            clause=clause,
            sub_clause=sub_clause,
            sub_sub_clause=sub_sub_clause,
            text=text,
            reason=reason,
            amendment_type=amendment_type,
            context=context
        )
    
    @classmethod
    @Log
    def from_email(cls, em: Email, use_ai_if_possible: bool = True) -> Amendment | None:
        if os.getenv("DEEPSEEK_API_KEY") and use_ai_if_possible:
            client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )
            with open("./system_prompt.txt") as f:
                system_prompt = f.read()
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""
                     Please Extract an Amendment from the following:
                     {em}
                     """}
                ],
                response_format={
                    "type": "json_object"
                },
                stream=False
            )
            ans = json.loads(response.choices[0].message.content or "{}")
            return Amendment.from_json(ans)
        else:
            return Amendment.attempt_basic_parsing(em)
    
    def apply_to_resolution(self, reso: Resolution) -> bool:
        """
        Applies Amendment to Resolution, then returns if it can be applied
        """
        c = int(self.clause)
        sc = self.sub_clause
        ssc = self.sub_sub_clause
        if sc: sc = ord(sc) - ord("a") + 1
        if ssc: ssc = roman.fromRoman(ssc)
        
        if (self.amendment_type == AmendmentType.ADD):
            if ssc and self.text:
                reso.clauses[c].subclauses[sc].append(subsubclause(ssc, self.text))
            elif sc and self.text:
                reso.clauses[c].append(subclause(sc, self.text))
            elif self.text:
                tokens = self.text.split(" ")
                scidx = None
                try:
                    scidx = tokens.index(":")
                except ValueError:
                    try:
                        scidx = tokens.index(";")
                    except ValueError:
                        try:
                            scidx = tokens.index("limited to:")
                        except ValueError as ve:
                            log << Lvl.FATAL << "Cannot split where subclause starts: " << ve << "\nin " << self.text << endl
                if not scidx:
                    log << Lvl.FATAL << "Cannot split where subclause starts: " << "\nin " << self.text << endl
                reso.clauses.append(clause(c, tokens[0], " ".join(tokens[1:scidx])))
                # TODO: add sub-clause level parsing logic
                raise NotImplementedError()
            
        
        return True
    def __str__(self) -> str:
        """Return a human-readable string representation of the amendment."""
        parts = []
        
        # Basic identification
        parts.append(f"Amendment {self.id[:8]}...")
        parts.append(f"Submitted by: {self.submitter_delegate}")
        
        # Resolution info if available
        if self.resolution_main_submitter or self.resolution_topic:
            reso_info = []
            if self.resolution_topic:
                reso_info.append(f"Topic: {self.resolution_topic}")
            if self.resolution_main_submitter:
                reso_info.append(f"Main submitter: {self.resolution_main_submitter}")
            parts.append(f"Resolution ({', '.join(reso_info)})")
        
        # Location
        location = f"Clause {self.clause}"
        if self.sub_clause:
            location += f".{self.sub_clause}"
        if self.sub_sub_clause:
            location += f".{self.sub_sub_clause}"
        parts.append(f"Location: {location}")
        
        # Type and content
        parts.append(f"Type: {self.amendment_type.name}")
        if self.text and self.amendment_type in {AmendmentType.ADD, AmendmentType.AMEND}:
            # Truncate text if too long
            text_preview = self.text[:100] + "..." if len(self.text) > 100 else self.text
            parts.append(f"Text: {text_preview}")
        elif self.amendment_type == AmendmentType.STRIKE:
            parts.append("Action: Strike")
        
        # Additional info
        if self.reason:
            reason_preview = self.reason[:80] + "..." if len(self.reason) > 80 else self.reason
            parts.append(f"Reason: {reason_preview}")
        
        if self.friendly:
            parts.append("(Friendly amendment)")
        
        parts.append(f"Created: {self.created_at}")
        
        return "\n".join(parts)

    def to_json(self) -> dict[str, Any]:
        """Convert the Amendment instance to a JSON-serializable dictionary."""
        json_dict = {
            "id": self.id,
            "created_at": self.created_at,
            "submitter_delegate": self.submitter_delegate,
            "clause": self.clause,
            "amendment_type": self.amendment_type.name,
            "friendly": self.friendly,
        }
        
        # Add optional fields if they exist
        if self.sub_clause is not None:
            json_dict["sub_clause"] = self.sub_clause
        if self.sub_sub_clause is not None:
            json_dict["sub_sub_clause"] = self.sub_sub_clause
        if self.resolution_main_submitter is not None:
            json_dict["resolution_main_submitter"] = self.resolution_main_submitter
        if self.resolution_topic is not None:
            json_dict["resolution_topic"] = self.resolution_topic
        if self.address_resolution is not None:
            json_dict["address_resolution"] = self.address_resolution.mainSubmitter
        if self.address_node is not None:
            # Handle the different possible types for address_node
            json_dict["address_node"] = str(self.address_node)
        if self.context:
            json_dict["context"] = self.context
        if self.text is not None:
            json_dict["text"] = self.text
        if self.reason is not None:
            json_dict["reason"] = self.reason
        
        return json_dict

@dataclass
class AmendmentSession:
    
    session_name: str
    committee: str
    ingestor: EmailIngestor | None = None

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
    
    def pull_from_email(self):
        if self.ingestor:
            emails = self.ingestor.pull()
            for em in emails:
                am = Amendment.from_email(em)
                if am:
                    self.add_amendment(am)
        else:
            log << Lvl.warn << "AmendmentSession.pull_from_email(self): ingestor not bound to session" << endl
    
    def add_amendment(self, amendment: Amendment) -> None:
        self.amendments.append(amendment)
    
    def delete_amendment(self, amendment: Amendment | None = None) -> None:
        """
        Deletes amendment, or the current amendment if not specified
        
        :param amendment: the amendment to delete
        :type amendment: Amendment | None
        """
        if amendment is None: 
            amendment = self.current()
        log << Lvl.Info << "Removing amendment: " << str(amendment) << endl
        self.amendments.remove(amendment)
        if self.current_index == len(self.amendments):
            self.current_index = max(len(self.amendments) - 1, 0)
    
    # ---------- Chair controls ----------

    def toggle_friendly(self):
        amendment = self.current()
        amendment.friendly = not amendment.friendly

    def toggle_reason_visibility(self):
        amendment = self.current()
        amendment.reason = None if amendment.reason else amendment.reason # ?
        # UI will decide how to interpret visibility
        pass
    
    @Log
    def save(self, path: str | Path | None = None):
        if path is None:
            path = self.source_path
        path = Path(path)
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
        return json.dumps(payload, indent=2)
    
    @classmethod
    @Log
    def load(cls, path: str | Path) -> AmendmentSession:
        path = Path(path)
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

def main():
    ingestor: EmailIngestor = EmailIngestor(imap_server="imap.163.com")
    session = AmendmentSession.load("session.json")
    session.ingestor = ingestor
    app = AmendmentApp(session)
    app.mainloop()

if __name__ == "__main__":
    main()