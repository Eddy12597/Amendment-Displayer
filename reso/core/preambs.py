from docx.api import Document
# import document as doc
import importlib.util
import os
spec = importlib.util.spec_from_file_location("document", os.path.join(os.path.dirname(__file__), "..", "document.py"))
if spec is None:
    raise
document = importlib.util.module_from_spec(spec)
if spec.loader is None:
    raise
spec.loader.exec_module(document)
doc = document

class preamb:
    def __init__(self, adverb: str = "Adverb",
                    content: str = "content") -> None:
        self.adverb = adverb
        self.content = content
    def toDocParagraph(self):
        _p = doc.paragraph(self.adverb, italic=True)
        _p.add_run(" " + self.content + ",")
        return _p
        