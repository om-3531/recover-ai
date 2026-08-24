"""
AI agent layer (Gemini-backed).

This package will hold the AI logic that analyzes failed payments and
recommends interventions. Per the project's architecture rules, code in
this package must NEVER directly execute a financial action — it only
produces a recommendation that is passed to the policy engine
(`app.policies`) for authorization.

Not implemented on Day 1.
"""
