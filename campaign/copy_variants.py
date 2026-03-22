"""
campaign/copy_variants.py — HARROW Per-Leak-Type Copy Templates.

COPY_TEMPLATES dict: BOOKING, CONTACT, SPEED, TRUST, CONTENT
Each has M1/M2/M3 structural prompts with embedded Voss techniques.
Templates are prompts — not final copy. Claude Sonnet fills them.

A DEFAULT template handles any leak_type not in the dict (with WARN log).

Message structure:
- M1: Accusation Audit + No-Oriented Question
- M2: Labelling + Calibrated Question
- M3: No-Oriented Close + Explicit Permission to Say No
"""

from typing import Optional
from core.logging import alog

# Each template is a dict with m1, m2, m3 prompt strings.
# Placeholders: {business_name}, {sector}, {leak_label}, {liability_context},
#               {accusation_audit}, {label}, {no_oriented_close}, {tone_instruction}

COPY_TEMPLATES: dict[str, dict[str, str]] = {
    "BOOKING": {
        "m1": (
            "Write a cold email (M1) for {business_name}, a {sector} business.\n"
            "Their primary leak is BOOKING: {leak_label}.\n"
            "Liability context: {liability_context}\n\n"
            "STRUCTURE:\n"
            "1. Open with this Accusation Audit: \"{accusation_audit}\"\n"
            "2. Name the booking problem specifically — reference their website or process\n"
            "3. Connect to lost revenue or wasted time (Translation Bridge)\n"
            "4. Close with a No-Oriented Question about seeing their missed booking data\n"
            "5. Offer a free booking audit with a specific deliverable\n\n"
            "TONE: {tone_instruction}\n"
            "Under 150 words. No subject line. Sign off with first name only."
        ),
        "m2": (
            "Write a follow-up email (M2) for {business_name}, a {sector} business.\n"
            "Sent 5 days after M1 (BOOKING leak) with no reply.\n"
            "Liability context: {liability_context}\n\n"
            "STRUCTURE:\n"
            "1. Open with this Label: \"{label}\"\n"
            "2. Reference your first email briefly — do not repeat it\n"
            "3. Add one specific data point about booking losses in their sector\n"
            "4. Close with a Calibrated Question: 'What would it look like if...'\n"
            "5. Include an exit ramp: make it genuinely easy to say no\n\n"
            "TONE: {tone_instruction}\n"
            "Under 120 words."
        ),
        "m3": (
            "Write a final email (M3) for {business_name}, a {sector} business.\n"
            "Sent 5 days after M2 (BOOKING leak) with no reply. This is the last message.\n"
            "Liability context: {liability_context}\n\n"
            "STRUCTURE:\n"
            "1. Acknowledge this is the last message — no guilt\n"
            "2. One sentence restating the booking problem\n"
            "3. Close with: \"{no_oriented_close}\"\n"
            "4. Give explicit permission to ignore\n\n"
            "TONE: {tone_instruction}\n"
            "Under 100 words."
        ),
    },
    "CONTACT": {
        "m1": (
            "Write a cold email (M1) for {business_name}, a {sector} business.\n"
            "Their primary leak is CONTACT: {leak_label}.\n"
            "Liability context: {liability_context}\n\n"
            "STRUCTURE:\n"
            "1. Open with this Accusation Audit: \"{accusation_audit}\"\n"
            "2. Name the contact/enquiry problem — broken form, missing email, phone only\n"
            "3. Connect to lost enquiries and the cost of silence (Translation Bridge)\n"
            "4. Close with a No-Oriented Question about seeing their enquiry gap\n"
            "5. Offer a free contact audit showing exactly where enquiries drop off\n\n"
            "TONE: {tone_instruction}\n"
            "Under 150 words. No subject line. Sign off with first name only."
        ),
        "m2": (
            "Write a follow-up email (M2) for {business_name}, a {sector} business.\n"
            "Sent 5 days after M1 (CONTACT leak) with no reply.\n"
            "Liability context: {liability_context}\n\n"
            "STRUCTURE:\n"
            "1. Open with this Label: \"{label}\"\n"
            "2. Reference your first email briefly\n"
            "3. Add a specific example of a lost enquiry scenario for their niche\n"
            "4. Close with: 'How would you know if an enquiry slipped through?'\n"
            "5. Exit ramp included\n\n"
            "TONE: {tone_instruction}\n"
            "Under 120 words."
        ),
        "m3": (
            "Write a final email (M3) for {business_name}, a {sector} business.\n"
            "Sent 5 days after M2 (CONTACT leak) with no reply. Last message.\n"
            "Liability context: {liability_context}\n\n"
            "STRUCTURE:\n"
            "1. Acknowledge this is the last message\n"
            "2. One sentence: the enquiry gap\n"
            "3. Close with: \"{no_oriented_close}\"\n"
            "4. Permission to ignore\n\n"
            "TONE: {tone_instruction}\n"
            "Under 100 words."
        ),
    },
    "SPEED": {
        "m1": (
            "Write a cold email (M1) for {business_name}, a {sector} business.\n"
            "Their primary leak is SPEED: {leak_label}.\n"
            "Liability context: {liability_context}\n\n"
            "STRUCTURE:\n"
            "1. Open with: \"{accusation_audit}\"\n"
            "2. Name the speed problem — load time, mobile, heavy images\n"
            "3. Connect to bounce rate and lost visitors (Translation Bridge)\n"
            "4. Close with No-Oriented Question about checking their page speed\n"
            "5. Offer a free speed report with specific metrics\n\n"
            "TONE: {tone_instruction}\n"
            "Under 150 words."
        ),
        "m2": (
            "Write M2 for {business_name} ({sector}), SPEED leak, 5 days after M1.\n"
            "Liability: {liability_context}\n\n"
            "1. Label: \"{label}\"\n"
            "2. Reference M1, add bounce rate data for their sector\n"
            "3. Calibrated Question: 'What would it take to...'\n"
            "4. Exit ramp\n\n"
            "TONE: {tone_instruction}. Under 120 words."
        ),
        "m3": (
            "Write M3 (final) for {business_name} ({sector}), SPEED leak.\n"
            "Liability: {liability_context}\n\n"
            "1. Last message acknowledgement\n"
            "2. One sentence: the speed cost\n"
            "3. Close: \"{no_oriented_close}\"\n"
            "4. Permission to ignore\n\n"
            "TONE: {tone_instruction}. Under 100 words."
        ),
    },
    "TRUST": {
        "m1": (
            "Write M1 for {business_name} ({sector}), TRUST leak: {leak_label}.\n"
            "Liability: {liability_context}\n\n"
            "1. Accusation Audit: \"{accusation_audit}\"\n"
            "2. Name the trust gap — reviews, testimonials, credentials\n"
            "3. Connect to prospect hesitation and competitor advantage\n"
            "4. No-Oriented Question about seeing their online reputation snapshot\n"
            "5. Offer a free reputation audit\n\n"
            "TONE: {tone_instruction}. Under 150 words."
        ),
        "m2": (
            "Write M2 for {business_name} ({sector}), TRUST leak, 5 days after M1.\n"
            "Liability: {liability_context}\n\n"
            "1. Label: \"{label}\"\n"
            "2. Add review comparison data for their sector\n"
            "3. Calibrated Question\n"
            "4. Exit ramp\n\n"
            "TONE: {tone_instruction}. Under 120 words."
        ),
        "m3": (
            "Write M3 (final) for {business_name} ({sector}), TRUST leak.\n"
            "Liability: {liability_context}\n\n"
            "1. Last message\n"
            "2. One sentence: the trust gap\n"
            "3. Close: \"{no_oriented_close}\"\n"
            "4. Permission to ignore\n\n"
            "TONE: {tone_instruction}. Under 100 words."
        ),
    },
    "CONTENT": {
        "m1": (
            "Write M1 for {business_name} ({sector}), CONTENT leak: {leak_label}.\n"
            "Liability: {liability_context}\n\n"
            "1. Accusation Audit: \"{accusation_audit}\"\n"
            "2. Name the content problem — outdated, thin, generic, broken links\n"
            "3. Connect to first impressions and lost credibility\n"
            "4. No-Oriented Question about seeing their site through fresh eyes\n"
            "5. Offer a free content audit with specific findings\n\n"
            "TONE: {tone_instruction}. Under 150 words."
        ),
        "m2": (
            "Write M2 for {business_name} ({sector}), CONTENT leak, 5 days after M1.\n"
            "Liability: {liability_context}\n\n"
            "1. Label: \"{label}\"\n"
            "2. Add competitor content comparison\n"
            "3. Calibrated Question\n"
            "4. Exit ramp\n\n"
            "TONE: {tone_instruction}. Under 120 words."
        ),
        "m3": (
            "Write M3 (final) for {business_name} ({sector}), CONTENT leak.\n"
            "Liability: {liability_context}\n\n"
            "1. Last message\n"
            "2. One sentence: the content gap\n"
            "3. Close: \"{no_oriented_close}\"\n"
            "4. Permission to ignore\n\n"
            "TONE: {tone_instruction}. Under 100 words."
        ),
    },
}

# Default template for any unrecognised leak type
_DEFAULT_TEMPLATE: dict[str, str] = {
    "m1": (
        "Write M1 for {business_name} ({sector}), detected issue: {leak_label}.\n"
        "Liability: {liability_context}\n\n"
        "1. Accusation Audit: \"{accusation_audit}\"\n"
        "2. Name the specific problem from the audit\n"
        "3. Connect to time or money cost\n"
        "4. No-Oriented Question\n"
        "5. Offer a free audit\n\n"
        "TONE: {tone_instruction}. Under 150 words."
    ),
    "m2": (
        "Write M2 for {business_name} ({sector}), 5 days after M1.\n"
        "Issue: {leak_label}. Liability: {liability_context}\n\n"
        "1. Label: \"{label}\"\n"
        "2. Add one new evidence point\n"
        "3. Calibrated Question\n"
        "4. Exit ramp\n\n"
        "TONE: {tone_instruction}. Under 120 words."
    ),
    "m3": (
        "Write M3 (final) for {business_name} ({sector}).\n"
        "Issue: {leak_label}. Liability: {liability_context}\n\n"
        "1. Last message\n"
        "2. One sentence summary\n"
        "3. Close: \"{no_oriented_close}\"\n"
        "4. Permission to ignore\n\n"
        "TONE: {tone_instruction}. Under 100 words."
    ),
}


def get_template(leak_type: str) -> dict[str, str]:
    """
    Return the M1/M2/M3 prompt templates for a given leak type.
    Falls back to DEFAULT with a WARN log if leak_type is unrecognised.
    """
    if leak_type in COPY_TEMPLATES:
        return COPY_TEMPLATES[leak_type]

    alog(
        "WARN",
        f"No copy template for leak_type '{leak_type}' — using DEFAULT template",
        step="copy_variants",
    )
    return _DEFAULT_TEMPLATE
