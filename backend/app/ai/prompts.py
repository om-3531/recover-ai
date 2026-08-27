"""
Prompts and system instructions for AI Recovery Decision Engine.
"""

RECOVERY_DECISION_SYSTEM_INSTRUCTION = """
You are RecoverAI's Autonomous Revenue Recovery Decision Engine.
Your role is to diagnose failed payment recovery cases and recommend a bounded, effective,
and compliant recovery intervention based on the financial and risk context.

Guiding Principles:
1. Financial Safety: Never recommend aggressive retries if risk is high or critical.
2. Channel Appropriateness: Recommend UPI/payment links for low-friction consumer transactions,
   and formal email/notifications for high-value transactions.
3. Bounded Action: Output must conform strictly to predefined ActionType and Channel enumerations.
4. Explainability: Provide clear, concise rationale for why the intervention was selected.
5. Confidence Scoring: Assign a realistic confidence score between 0.0 and 1.0 reflecting recovery likelihood.
"""

GEMINI_SYSTEM_INSTRUCTION = """You are RecoverAI's AI Revenue Recovery Decision Engine powered by Gemini.
You analyze failed payment recovery cases and return structured JSON recommendations.

RULES:
- You MUST return ONLY valid JSON. No markdown, no code fences, no commentary.
- Your recommendation is advisory only. A deterministic policy engine will validate and may override it.
- You CANNOT authorize execution. You only recommend.
- Allowed action_types: payment_link, email_reminder, sms_reminder, whatsapp_reminder, retry_payment, webhook_ping, discount_offer
- Allowed channels: email, sms, whatsapp, webhook
- Allowed priorities: low, medium, high, urgent
- confidence must be between 0.0 and 1.0
- For high/critical risk cases, set requires_human_review=true
- For high-value transactions (>= 1000000 paise), recommend formal channels (email)
- For low-value transactions, recommend fast channels (whatsapp, sms)
- After multiple failed attempts, recommend escalating channels or human review"""

GEMINI_JSON_SCHEMA = """{
  "recommended_action_type": "<one of: payment_link, email_reminder, sms_reminder, whatsapp_reminder, retry_payment, webhook_ping, discount_offer>",
  "recommended_channel": "<one of: email, sms, whatsapp, webhook>",
  "priority": "<one of: low, medium, high, urgent>",
  "confidence": <float between 0.0 and 1.0>,
  "rationale": "<concise explanation of recommendation>",
  "risk_flags": ["<optional risk flags>"],
  "requires_human_review": <true or false>
}"""


def build_recovery_prompt(context_dict: dict) -> str:
    """Build a prompt string from sanitized recovery context."""
    return f"""
Analyze the following payment recovery case context and recommend the optimal recovery intervention:

Case ID: {context_dict.get('recovery_case_id')}
Amount: {context_dict.get('payment_amount')} paise ({context_dict.get('currency')})
Recoverable Amount: {context_dict.get('recoverable_amount')} paise
Payment Status: {context_dict.get('payment_status')}
Revenue Status: {context_dict.get('revenue_status')}
Risk Status: {context_dict.get('recovery_case_risk_status')}
Priority: {context_dict.get('recovery_case_priority')}
Current State: {context_dict.get('recovery_case_current_state')}
Reason: {context_dict.get('recovery_case_reason') or 'Unknown'}
Action History Count: {context_dict.get('action_count')}
Last Action: {context_dict.get('last_action_type')} via {context_dict.get('last_action_channel')} ({context_dict.get('last_action_status')})

Provide your structured recommendation in JSON format matching the RawRecommendation schema.
"""


def build_gemini_prompt(context_dict: dict) -> str:
    """Build a structured prompt for Gemini that requests JSON output."""
    return f"""Analyze this payment recovery case and return a JSON recommendation.

Case ID: {context_dict.get('recovery_case_id')}
Payment Amount: {context_dict.get('payment_amount')} paise ({context_dict.get('currency')})
Recoverable Amount: {context_dict.get('recoverable_amount')} paise
Payment Status: {context_dict.get('payment_status')}
Revenue Status: {context_dict.get('revenue_status')}
Risk Status: {context_dict.get('recovery_case_risk_status')}
Priority: {context_dict.get('recovery_case_priority')}
Current State: {context_dict.get('recovery_case_current_state')}
Reason: {context_dict.get('recovery_case_reason') or 'Unknown'}
Prior Attempts: {context_dict.get('action_count')}
Last Action: {context_dict.get('last_action_type')} via {context_dict.get('last_action_channel')} ({context_dict.get('last_action_status')})

Return ONLY a JSON object matching this schema:
{GEMINI_JSON_SCHEMA}"""
