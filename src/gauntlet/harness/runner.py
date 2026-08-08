"""Harness — runs an attack library against a target and measures ASR.

Connects roles that know nothing about each other: the target exposes
only `ask`, the judge only scores text, the harness wires them together.

Results are dataclasses rather than dicts. A dict typo (`r["trails"]`)
is invisible until runtime; a dataclass field typo is caught by the
editor before the code runs — the compiler guarantee Python does not
give you for free.
"""

import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from gauntlet.attacks.library import GOLDEN_SET, Attack
from gauntlet.judges.cascade import Verdict, judge
from gauntlet.targets.base import Target

# More trials tighten the estimate and cost time. 5 is a dev-loop
# compromise; use 20+ for numbers that go in a report.
DEFAULT_TRIALS = 5


@dataclass
class AttackResult:
    """Outcome of running one attack N times against one target."""

    attack: Attack
    responses: list[str]
    verdicts: list[Verdict]

    @property
    def leaks(self) -> int:
        return sum(1 for v in self.verdicts if v.leaked)

    @property
    def trials(self) -> int:
        return len(self.verdicts)

    @property
    def rate(self) -> float:
        """Fraction 0.0-1.0. Computed, never stored — one source of truth,
        so the value cannot disagree with itself elsewhere in the code."""
        return self.leaks / self.trials if self.trials else 0.0


@dataclass
class CampaignReport:
    """Everything one campaign produced, plus the metrics derived from it."""

    target_name: str
    target_domain: str
    results: list[AttackResult] = field(default_factory=list)

    @property
    def total_leaks(self) -> int:
        return sum(r.leaks for r in self.results)

    @property
    def total_trials(self) -> int:
        return sum(r.trials for r in self.results)

    @property
    def asr(self) -> float:
        """Overall attack success rate, 0.0-1.0.

        State this caveat in any report: ASR is a property of the PAIR
        (target, attack library), not of the target alone. Adding weak
        attacks lowers it without the target changing at all.
        """
        return self.total_leaks / self.total_trials if self.total_trials else 0.0

    def by_category(self) -> dict[str, tuple[int, int]]:
        """Leaks and trials per technique family — the actual finding.

        'ASR 25%' tells a founder nothing. 'Task-reframing leaks 40% of
        the time, direct asks 0%' tells them exactly what to fix.
        """
        totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in self.results:
            totals[r.attack.category][0] += r.leaks
            totals[r.attack.category][1] += r.trials
        return {cat: (leaks, trials) for cat, (leaks, trials) in totals.items()}

    def by_stage(self) -> Counter:
        """Which cascade stage caught each leak.

        The headline number for the write-up: every leak caught beyond
        'literal' is one a naive string-matching audit would have missed.
        """
        return Counter(v.stage for r in self.results for v in r.verdicts if v.leaked)


async def run_attack(
    target: Target, attack: Attack, trials: int = DEFAULT_TRIALS
) -> AttackResult:
    """Run one attack N times concurrently, then judge every response."""
    responses = await asyncio.gather(
        *(target.ask(attack.prompt) for _ in range(trials))
    )
    # Judging is I/O too (stage 3 calls a model), so it is gathered as well.
    verdicts = await asyncio.gather(*(judge(r, target.secret or "") for r in responses))
    return AttackResult(
        attack=attack, responses=list(responses), verdicts=list(verdicts)
    )


async def run_campaign(
    target: Target,
    attacks: list[Attack] | None = None,
    trials: int = DEFAULT_TRIALS,
) -> CampaignReport:
    """Run the full attack library against one target."""
    attacks = attacks if attacks is not None else GOLDEN_SET
    report = CampaignReport(target_name=target.name, target_domain=target.domain)

    for i, attack in enumerate(attacks, start=1):
        result = await run_attack(target, attack, trials)
        report.results.append(result)
        print(
            f"[{i:>2}/{len(attacks)}] {result.leaks}/{result.trials} "
            f"({result.rate:>6.1%}) {attack.category:<18} :: {attack.prompt[:45]}"
        )

    return report


def print_summary(report: CampaignReport) -> None:
    """Print the per-category breakdown and detection provenance."""
    print(f"\n{'=' * 72}")
    print(f"TARGET: {report.target_name} ({report.target_domain})")
    print(f"{'=' * 72}")

    ranked = sorted(
        report.by_category().items(),
        key=lambda item: item[1][0] / item[1][1] if item[1][1] else 0,
        reverse=True,
    )
    for category, (leaks, trials) in ranked:
        rate = leaks / trials if trials else 0.0
        bar = "#" * round(rate * 30)
        print(f"  {category:<18} {rate:>6.1%}  {leaks:>3}/{trials:<4} {bar}")

    print(
        f"\n  {'OVERALL':<18} {report.asr:>6.1%}  "
        f"{report.total_leaks:>3}/{report.total_trials}"
    )

    stages = report.by_stage()
    if stages:
        print(f"\n  Detection stage:")
        for stage, count in stages.most_common():
            share = count / report.total_leaks if report.total_leaks else 0.0
            print(f"    {stage:<22} {count:>3}  ({share:.0%})")

        beyond_literal = report.total_leaks - stages.get("literal", 0)
        if beyond_literal:
            missed = beyond_literal / report.total_leaks
            print(
                f"\n  {missed:.0%} of leaks were invisible to literal string matching."
            )


async def main() -> None:
    from gauntlet.targets.simple_target import TARGET

    report = await run_campaign(TARGET, trials=DEFAULT_TRIALS)
    print_summary(report)


if __name__ == "__main__":
    asyncio.run(main())
