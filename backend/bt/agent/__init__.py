"""Background AI curator worker (`python -m bt.agent`).

Pipeline per iteration: learn (feedback→lessons) → judge (enriched) → enrich (one found video) →
discover (planner queries / seed channels / subscription RSS) when the backlog is small.
"""
