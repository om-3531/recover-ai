"""
Razorpay integration layer.

All Razorpay API calls (payments, refunds, orders, etc.) must live in
this package and nowhere else, so the integration can be mocked, tested,
and swapped without touching route or business logic.

Not implemented on Day 1 — see `.env.example` for the credentials this
layer will eventually require (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET).
"""
