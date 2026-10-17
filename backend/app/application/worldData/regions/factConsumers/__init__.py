"""Typed domain plugin registry and facts collector; flora remains unregistered."""

from collections.abc import Callable
from dataclasses import dataclass, replace

from app.application.worldData.regions.factConsumers import climate, hydrology, relief
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import DeclarationFacts, RegionFacts


@dataclass(frozen=True)
class FactConsumer:
    name: str
    contribute: Callable[[FactConsumerContext, RegionFacts], RegionFacts]


FACT_CONSUMERS = (
    FactConsumer("climate", lambda context, facts: replace(facts, climate=climate.contribute(context))),
    FactConsumer("hydrology", lambda context, facts: replace(facts, hydrology=hydrology.contribute(context))),
    FactConsumer("relief", lambda context, facts: replace(facts, relief=relief.contribute(context))),
)


def collect_facts(
    context: FactConsumerContext,
    *,
    declaration: DeclarationFacts | None = None,
    elapsed_ticks: int = 0,
    consumers: tuple[FactConsumer, ...] = FACT_CONSUMERS,
) -> RegionFacts:
    facts = RegionFacts(declaration=declaration, elapsed_ticks=elapsed_ticks)
    for consumer in consumers:
        facts = consumer.contribute(context, facts)
    return facts
