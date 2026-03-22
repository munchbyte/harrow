"""
engine/liability.py — HARROW Liability Predictor (!Audit_v2).

Cross-references business sector against niche failure dataset to identify
the Critical Failure Mode. The Leak Type gives the technical signal.
The Critical Failure Mode gives the human cost.

NICHE_FAILURES dict maps sector keywords to:
- Critical Failure Mode
- Unowned Consequence

Functions:
- detect_niche(category: str) -> dict — fuzzy match to niche entry
- get_liability_context(lead: dict) -> str — plain English failure scenario

If no niche match: use generic 'missed enquiry' failure mode, flag as WARN.
"""

from typing import Optional
from core.logging import alog

# --- Niche Failure Dataset ---
# Each entry: keyword patterns -> (critical_failure_mode, unowned_consequence)
NICHE_FAILURES: dict[str, dict[str, str]] = {
    "restaurant": {
        "critical_failure": "Lost table booking at peak hours",
        "unowned_consequence": "Empty covers on Friday night while walk-ins are turned away by competitors with online booking",
    },
    "cafe": {
        "critical_failure": "Lost table booking at peak hours",
        "unowned_consequence": "Regulars switch to the cafe down the road that lets them book a window seat online",
    },
    "pub": {
        "critical_failure": "Lost function and event enquiry",
        "unowned_consequence": "Birthday parties and corporate events go to venues that respond within the hour",
    },
    "hotel": {
        "critical_failure": "Lost direct booking to OTA commission",
        "unowned_consequence": "Paying 15-20% commission to Booking.com for guests who tried your website first",
    },
    "b&b": {
        "critical_failure": "Lost direct booking to OTA commission",
        "unowned_consequence": "Guest wanted to book direct but gave up and used Airbnb instead — you paid the fee",
    },
    "salon": {
        "critical_failure": "Lost appointment booking",
        "unowned_consequence": "Client calls during a cut, no one answers, they book the salon across the street",
    },
    "barber": {
        "critical_failure": "Lost walk-in to competitor with online booking",
        "unowned_consequence": "Young clients expect online booking — they will not call or wait",
    },
    "spa": {
        "critical_failure": "Lost high-value treatment booking",
        "unowned_consequence": "Couples massage enquiry goes unanswered for 48 hours — they book elsewhere",
    },
    "dentist": {
        "critical_failure": "Lost new patient registration",
        "unowned_consequence": "Anxious patient finally decides to book, hits a broken form, and does not try again",
    },
    "physiotherapist": {
        "critical_failure": "Lost referral follow-through",
        "unowned_consequence": "GP refers patient to you, patient visits your site, cannot book online, chooses competitor",
    },
    "chiropractor": {
        "critical_failure": "Lost referral follow-through",
        "unowned_consequence": "Patient in pain wants same-day appointment — your voicemail plays, they call the next listing",
    },
    "gym": {
        "critical_failure": "Lost membership sign-up",
        "unowned_consequence": "January joiner visits your site, no pricing, no join button — signs up to PureGym instead",
    },
    "yoga": {
        "critical_failure": "Lost class booking",
        "unowned_consequence": "New student cannot see the timetable or book a taster — joins the studio with a proper app",
    },
    "plumber": {
        "critical_failure": "Lost emergency callout",
        "unowned_consequence": "Homeowner with a burst pipe calls three plumbers — the one who answers first gets the job",
    },
    "electrician": {
        "critical_failure": "Lost emergency callout",
        "unowned_consequence": "Commercial client needs weekend callout — your website says 'call us' but no one picks up",
    },
    "builder": {
        "critical_failure": "Lost project enquiry",
        "unowned_consequence": "Homeowner requests a quote, hears nothing for a week, hires the builder who replied same day",
    },
    "roofer": {
        "critical_failure": "Lost storm-damage callout",
        "unowned_consequence": "After a storm, every roofer is busy — the ones with online booking forms get the callbacks",
    },
    "solicitor": {
        "critical_failure": "Lost client intake",
        "unowned_consequence": "Potential client fills in a contact form, gets no acknowledgement, instructs a competitor",
    },
    "accountant": {
        "critical_failure": "Lost new client onboarding",
        "unowned_consequence": "Small business owner wants to switch accountant — your site has no pricing and no clear next step",
    },
    "estate agent": {
        "critical_failure": "Lost property valuation request",
        "unowned_consequence": "Seller submits a valuation form, hears nothing for 3 days, lists with the agent who called back in an hour",
    },
    "photographer": {
        "critical_failure": "Lost wedding or event booking",
        "unowned_consequence": "Couple enquires about wedding photography — you reply Tuesday, they booked someone else on Monday",
    },
    "florist": {
        "critical_failure": "Lost occasion-driven order",
        "unowned_consequence": "Customer wants same-day delivery for a birthday — your site has no delivery info, they use Interflora",
    },
    "vet": {
        "critical_failure": "Lost new registration and emergency contact",
        "unowned_consequence": "Pet owner moves to the area, visits your site at 9pm, cannot register online — registers elsewhere next morning",
    },
    "garage": {
        "critical_failure": "Lost MOT or service booking",
        "unowned_consequence": "Driver gets an MOT reminder, visits your site, no online booking — books at Halfords Autocentre",
    },
    "cleaning": {
        "critical_failure": "Lost recurring contract enquiry",
        "unowned_consequence": "Landlord needs end-of-tenancy clean, submits form, no response — hires the cleaner who texts back a quote",
    },
}

# Keywords to niche mapping (lowercase partial matches)
_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["restaurant", "dining", "eatery", "bistro", "brasserie"], "restaurant"),
    (["cafe", "coffee", "tea room", "bakery"], "cafe"),
    (["pub", "bar", "inn", "tavern", "taproom"], "pub"),
    (["hotel", "lodge", "resort", "accommodation"], "hotel"),
    (["b&b", "bed and breakfast", "guest house", "guesthouse"], "b&b"),
    (["hair salon", "salon", "hairdresser", "beauty salon", "nail"], "salon"),
    (["barber", "barbershop"], "barber"),
    (["spa", "wellness centre", "wellness center", "day spa"], "spa"),
    (["dentist", "dental", "orthodontist"], "dentist"),
    (["physiotherapist", "physio", "physical therapy"], "physiotherapist"),
    (["chiropractor", "chiropractic", "osteopath"], "chiropractor"),
    (["gym", "fitness", "crossfit", "health club"], "gym"),
    (["yoga", "pilates", "meditation studio"], "yoga"),
    (["plumber", "plumbing", "heating engineer"], "plumber"),
    (["electrician", "electrical", "sparky"], "electrician"),
    (["builder", "construction", "renovation", "extension"], "builder"),
    (["roofer", "roofing"], "roofer"),
    (["solicitor", "lawyer", "law firm", "legal"], "solicitor"),
    (["accountant", "accounting", "bookkeeper", "tax advisor"], "accountant"),
    (["estate agent", "letting agent", "property", "realtor"], "estate agent"),
    (["photographer", "photography", "videographer"], "photographer"),
    (["florist", "flower", "floral"], "florist"),
    (["vet", "veterinary", "animal", "pet"], "vet"),
    (["garage", "mot", "mechanic", "auto repair", "car service"], "garage"),
    (["cleaning", "cleaner", "maid", "domestic", "janitorial"], "cleaning"),
]

# Generic fallback
_GENERIC_FAILURE = {
    "critical_failure": "Lost enquiry due to slow or missing response",
    "unowned_consequence": "Prospect contacted you, received no timely response, and hired a competitor instead",
}


def detect_niche(category: str) -> dict:
    """
    Fuzzy-match a business category string to a niche failure entry.
    Returns dict with keys: niche, critical_failure, unowned_consequence.
    Falls back to generic with is_generic=True flag.
    """
    if not category:
        return {**_GENERIC_FAILURE, "niche": "unknown", "is_generic": True}

    lower = category.lower()
    for keywords, niche_key in _KEYWORD_MAP:
        for kw in keywords:
            if kw in lower:
                entry = NICHE_FAILURES[niche_key]
                return {
                    "niche": niche_key,
                    "critical_failure": entry["critical_failure"],
                    "unowned_consequence": entry["unowned_consequence"],
                    "is_generic": False,
                }

    # No match — generic fallback
    alog("WARN", f"No niche match for category '{category}' — using generic failure mode",
         step="liability_detect")
    return {**_GENERIC_FAILURE, "niche": "unknown", "is_generic": True}


def get_liability_context(lead: dict) -> str:
    """
    Build a plain English liability context string for a lead.
    Used in copy generation prompts to personalise the failure narrative.

    Expected lead keys: category (or sector), business_name, leak_type, leak_label
    """
    category = lead.get("category", lead.get("sector", ""))
    business_name = lead.get("business_name", lead.get("name", "this business"))
    leak_type = lead.get("leak_type", "CONTACT")
    leak_label = lead.get("leak_label", "slow response to enquiries")

    niche = detect_niche(category)

    context = (
        f"Business: {business_name} ({niche['niche']}). "
        f"Detected leak: {leak_type} — {leak_label}. "
        f"Critical failure mode: {niche['critical_failure']}. "
        f"Unowned consequence: {niche['unowned_consequence']}."
    )

    if niche.get("is_generic"):
        context += " (Generic — no niche-specific data available.)"

    return context
