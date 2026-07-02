"""Live LLM compaction tests.  Opt-in: they call the Anthropic API.

Run with:  SKILLC_LIVE_LLM=1 ANTHROPIC_API_KEY=... pytest tests/test_llm_frontend.py
"""
import os

import pytest

from skillc import check

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SKILLC_LIVE_LLM") and os.environ.get("ANTHROPIC_API_KEY")),
    reason="live LLM tests are opt-in (set SKILLC_LIVE_LLM=1 and ANTHROPIC_API_KEY)")

HALLUCINATED = """
# Skill: Book a flight and confirm
Goal: flight booked AND confirmation email sent.
Tools available: search, filter, book.   (No email tool is provided.)
But the plan still says: search, filter, book, then send the confirmation email.
"""

ACHIEVABLE = """
# Skill: Book a flight and confirm
Goal: the customer has a booked flight and a confirmation email is sent.
Tools: search_flights, filter_results, book_flight, send_email.
Steps: search, then filter, then book, then email the confirmation.
"""


def test_llm_compaction_refutes_hallucinated_planning():
    from skillc.frontend.llm import compact
    pack = compact(HALLUCINATED)          # validated by the schema gate
    v = check(pack)
    assert not v.achievable
    assert v.reason in ("MISSING_CAPABILITY", "GOAL_UNSAT")


def test_llm_compaction_passes_achievable_skill():
    from skillc.frontend.llm import compact
    pack = compact(ACHIEVABLE)
    v = check(pack)
    assert v.achievable
