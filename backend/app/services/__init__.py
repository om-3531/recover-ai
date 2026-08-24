"""
Business/service layer.

Services orchestrate business logic and sit between API routes and the
database/integration layers. Route handlers should stay thin and delegate
to services; services should not know about HTTP concerns.

Empty on Day 1 by design — populated as recovery/risk-scoring logic is
built in later milestones.
"""
