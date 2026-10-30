"""dpp-conformance: a conformance checker for the Document Parsing Protocol.

Grades a document parser's Markdown output against the expected outputs
published with LlamaIndex's Document Parsing Protocol (DPP, draft 0.1),
rule by rule, applying the protocol's own accepted-alternative equivalences.
"""

__version__ = "0.1.0"

from .corpus import Sample, extract_protocol  # noqa: F401
from .grade import GradeResult, grade  # noqa: F401
