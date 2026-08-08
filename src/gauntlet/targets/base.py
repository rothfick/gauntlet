"""Target protocol — the shape every attackable system implements.

The harness must never know whether it is attacking a local model, a
hosted API, or a browser UI driven by Playwright. That knowledge lives
in the target implementation, so new targets plug in without the harness
changing at all.

Same principle as a Page Object in Selenium: the test does not know how
the page is built, and the page does not know which test drives it.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Target:
    """One attackable system under test.

    Attributes:
        name:     stable identifier used in reports, e.g. "bank_assistant"
        domain:   business domain, e.g. "banking" — drives which judges apply
        ask:      async callable: prompt -> reply. The only way in.
        secret:   the string an extraction attack tries to obtain, if any
        metadata: provenance for the report (model, version, surface, notes)
    """

    name: str
    domain: str
    ask: Callable[[str], Awaitable[str]]
    secret: str | None = None
    metadata: dict = field(default_factory=dict)
