"""
Deterministic policy / authorization engine.

Every AI recommendation must pass through this layer before any recovery
action is executed. This is where business rules, limits, and safety
checks live. Kept separate from `app.agents` so authorization logic is
auditable and does not depend on LLM output.

Not implemented on Day 1.
"""
