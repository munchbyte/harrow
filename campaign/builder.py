"""
campaign/builder.py — HARROW 7-Stage Campaign Builder Orchestrator.

The Campaign Builder takes a sector, location, and tone from Adrian and
produces a complete, ready-to-send campaign in a single guided session.

Seven Stages:
1. Define — validate sector, location, limit, tone. Create campaign record.
2. Harvest — run Workflow A (Outscraper). ICP filter.
3. Audit — run Workflow B (Firecrawl + Claude) on all PASS leads.
4. Segment — group leads by Leak Type. Order by score. Flag WARNs.
5. Generate Copy — M1/M2/M3 per Leak Type. Five-Gate + Voss.
6. Review — HITL gate fires. Copy displayed for Adrian.
7. GO — Adrian approves. Email channel armed. Scheduler triggered.

Class: CampaignBuilder with .run(params) async method.
"""

import json
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

from core.db import get_db
from core.logging import alog
from core.jobs import update_job
from core.hitl import fire_hitl
from core.go_state import arm_channel
from channels.lead_gen import task_lead_harvest, task_ghost_audit
from channels.email import generate_email_sequence
from campaign.copy_variants import get_template
from engine.five_gate import append_sovereignty_footer
from engine.voss import apply_accusation_audit, apply_label, apply_no_oriented_close
from engine.liability import get_liability_context
from engine.claude_client import call_sonnet

# Tone instructions (duplicated from email.py for template filling)
_TONE_INSTRUCTIONS = {
    "dj": "Late-Night FM DJ tone: slow, calm, deliberate. No urgency. No exclamation marks.",
    "formal": "Professional and measured. Clear, direct language. No jargon.",
    "concise": "Extremely concise. Short sentences. No filler. Every word counts.",
}

CAMPAIGN_STAGES = ["define", "harvest", "audit", "segment", "generate", "review", "go"]


class CampaignBuilder:
    """Orchestrates a full 7-stage campaign from sector+location to ready-to-send."""

    def __init__(self, job_id: str, caller: str):
        self.job_id = job_id
        self.caller = caller
        self.campaign_id: Optional[int] = None

    async def run(self, params: dict) -> dict:
        """Execute all 7 stages. Returns campaign summary."""
        # Stage 1: Define
        campaign = await self._stage_define(params)

        # Stage 2: Harvest
        harvest = await self._stage_harvest(params)

        # Stage 3: Audit
        audit = await self._stage_audit(harvest)

        # Stage 4: Segment
        segments = await self._stage_segment(audit)

        # Stage 5: Generate Copy
        copy_outputs = await self._stage_generate(segments, params.get("tone", "dj"))

        # Stage 6: Review (HITL gate)
        await self._stage_review(copy_outputs)

        # Stage 7: GO
        result = await self._stage_go(copy_outputs)

        return result

    # ── Stage 1: Define ────────────────────────────────────────────────

    async def _stage_define(self, params: dict) -> dict:
        """Validate inputs and create campaign record."""
        self._update_step(1, "define", "running")
        update_job(self.job_id, progress="Stage 1/7: Defining campaign...")

        sector = params.get("sector")
        location = params.get("location")
        if not sector or not location:
            raise ValueError("Missing required params: sector and location")

        tone = params.get("tone", "dj")
        if tone not in _TONE_INSTRUCTIONS:
            tone = "dj"

        name = f"{sector} — {location}"
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            cursor = db.execute(
                "INSERT INTO campaigns (name, sector, location, tone, status, created_at) VALUES (?, ?, ?, ?, 'running', ?)",
                (name, sector, location, tone, now),
            )
            self.campaign_id = cursor.lastrowid

            # Create 7 step records
            for i, stage_name in enumerate(CAMPAIGN_STAGES, 1):
                db.execute(
                    "INSERT INTO campaign_steps (campaign_id, step_num, step_name, status) VALUES (?, ?, ?, 'pending')",
                    (self.campaign_id, i, stage_name),
                )

        alog("INFO", f"Campaign created: {name} (id={self.campaign_id})",
             job_id=self.job_id, channel="lead_gen", step="campaign_define")

        self._update_step(1, "define", "complete")
        return {"campaign_id": self.campaign_id, "name": name, "sector": sector, "location": location, "tone": tone}

    # ── Stage 2: Harvest ───────────────────────────────────────────────

    async def _stage_harvest(self, params: dict) -> dict:
        """Run Outscraper lead harvest."""
        self._update_step(2, "harvest", "running")
        update_job(self.job_id, progress="Stage 2/7: Harvesting leads...")

        sector = params.get("sector", "")
        location = params.get("location", "")
        limit = params.get("limit", 20)
        dry_run = params.get("dry_run", True)

        query = f"{sector} in {location}"
        harvest_params = {"query": query, "limit": limit, "dry_run": dry_run}

        result = await task_lead_harvest(self.job_id, harvest_params, self.caller)

        self._update_step(2, "harvest", "complete", result=json.dumps({
            "total_raw": result["total_raw"],
            "passed": result["passed"],
            "warned": result["warned"],
            "rejected": result["rejected"],
        }))

        alog("INFO", f"Harvest complete: {result['passed']} PASS, {result['warned']} WARN",
             job_id=self.job_id, channel="lead_gen", step="campaign_harvest")

        return result

    # ── Stage 3: Audit ─────────────────────────────────────────────────

    async def _stage_audit(self, harvest: dict) -> dict:
        """Run Ghost Audit on harvested leads."""
        self._update_step(3, "audit", "running")
        update_job(self.job_id, progress="Stage 3/7: Running Ghost Audit...")

        leads = harvest.get("leads", [])
        # Only audit PASS and WARN leads that have a website
        audit_leads = [l for l in leads if l.get("site")]

        if not audit_leads:
            alog("WARN", "No leads with websites to audit",
                 job_id=self.job_id, channel="lead_gen", step="campaign_audit")
            self._update_step(3, "audit", "complete", result=json.dumps({"audited": 0}))
            return {"audited": 0, "errors": 0, "results": []}

        audit_params = {"leads": audit_leads, "limit": len(audit_leads), "dry_run": True}
        result = await task_ghost_audit(self.job_id, audit_params, self.caller)

        self._update_step(3, "audit", "complete", result=json.dumps({
            "audited": result["audited"], "errors": result["errors"],
        }))

        return result

    # ── Stage 4: Segment ───────────────────────────────────────────────

    async def _stage_segment(self, audit: dict) -> dict:
        """Group leads by leak type. Order by score. Flag WARNs."""
        self._update_step(4, "segment", "running")
        update_job(self.job_id, progress="Stage 4/7: Segmenting leads...")

        results = audit.get("results", [])
        segments: dict[str, list] = defaultdict(list)

        for lead in results:
            if "error" in lead:
                continue
            leak_type = lead.get("leak_type", "NONE")
            segments[leak_type].append(lead)

        # Sort each segment by leak_score descending
        for leak_type in segments:
            segments[leak_type].sort(key=lambda x: x.get("leak_score", 0), reverse=True)

        # Remove NONE — no actionable leak
        none_leads = segments.pop("NONE", [])

        summary = {
            leak_type: len(leads)
            for leak_type, leads in segments.items()
        }
        summary["NONE"] = len(none_leads)

        alog("INFO", f"Segmented: {dict(summary)}",
             job_id=self.job_id, channel="lead_gen", step="campaign_segment")

        self._update_step(4, "segment", "complete", result=json.dumps(summary))

        return {"segments": dict(segments), "none_count": len(none_leads), "summary": summary}

    # ── Stage 5: Generate Copy ─────────────────────────────────────────

    async def _stage_generate(self, segment_data: dict, tone: str = "dj") -> list[dict]:
        """Generate M1/M2/M3 per leak type using copy templates."""
        self._update_step(5, "generate", "running")
        update_job(self.job_id, progress="Stage 5/7: Generating copy...")

        segments = segment_data.get("segments", {})
        tone_instruction = _TONE_INSTRUCTIONS.get(tone, _TONE_INSTRUCTIONS["dj"])
        all_outputs: list[dict] = []

        for leak_type, leads in segments.items():
            if not leads:
                continue

            # Use the top lead as representative for the template
            rep_lead = leads[0]
            template = get_template(leak_type)

            business_name = rep_lead.get("name", rep_lead.get("business_name", "the business"))
            sector = rep_lead.get("category", rep_lead.get("sector", "service business"))
            leak_label = rep_lead.get("leak_label", "")
            liability_context = get_liability_context(rep_lead)

            # Fill template placeholders
            fill = {
                "business_name": business_name,
                "sector": sector,
                "leak_label": leak_label,
                "liability_context": liability_context,
                "accusation_audit": apply_accusation_audit(leak_type, sector),
                "label": apply_label(leak_type),
                "no_oriented_close": apply_no_oriented_close(leak_type),
                "tone_instruction": tone_instruction,
            }

            update_job(self.job_id, progress=f"Stage 5/7: Generating {leak_type} copy...")

            try:
                # Generate using templates
                m1_prompt = template["m1"].format(**fill)
                m2_prompt = template["m2"].format(**fill)
                m3_prompt = template["m3"].format(**fill)

                m1 = await call_sonnet(m1_prompt, job_id=self.job_id, step=f"gen_{leak_type}_m1")
                m1 = append_sovereignty_footer(m1)

                m2 = await call_sonnet(m2_prompt, job_id=self.job_id, step=f"gen_{leak_type}_m2")
                m2 = append_sovereignty_footer(m2)

                m3 = await call_sonnet(m3_prompt, job_id=self.job_id, step=f"gen_{leak_type}_m3")
                m3 = append_sovereignty_footer(m3)

                # Store in DB
                now = datetime.now(timezone.utc).isoformat()
                with get_db() as db:
                    db.execute(
                        """INSERT INTO copy_outputs
                           (campaign_id, leak_type, m1, m2, m3, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (self.campaign_id, leak_type, m1, m2, m3, now),
                    )

                output = {
                    "leak_type": leak_type,
                    "lead_count": len(leads),
                    "m1": m1,
                    "m2": m2,
                    "m3": m3,
                }
                all_outputs.append(output)

                alog("INFO", f"Copy generated for {leak_type} ({len(leads)} leads)",
                     job_id=self.job_id, channel="email", step=f"gen_{leak_type}")

            except Exception as e:
                alog("ERROR",
                     f"Copy generation failed for {leak_type}: {e}. "
                     f"To resolve this: check Claude API key and retry",
                     job_id=self.job_id, channel="email", step=f"gen_{leak_type}")
                all_outputs.append({"leak_type": leak_type, "error": str(e)})

        self._update_step(5, "generate", "complete", result=json.dumps({
            "generated": len([o for o in all_outputs if "error" not in o]),
            "errors": len([o for o in all_outputs if "error" in o]),
        }))

        return all_outputs

    # ── Stage 6: Review ────────────────────────────────────────────────

    async def _stage_review(self, copy_outputs: list[dict]) -> None:
        """Fire HITL gate for copy review."""
        self._update_step(6, "review", "running")
        update_job(self.job_id, progress="Stage 6/7: Awaiting review...")

        successful = [o for o in copy_outputs if "error" not in o]
        if not successful:
            alog("WARN", "No copy to review — all generation failed",
                 job_id=self.job_id, step="campaign_review")
            self._update_step(6, "review", "complete")
            return

        # Build review summary
        summary_lines = []
        for output in successful:
            summary_lines.append(
                f"[{output['leak_type']}] {output['lead_count']} leads — M1/M2/M3 generated"
            )

        context = {
            "campaign_id": self.campaign_id,
            "copy_count": len(successful),
            "leak_types": [o["leak_type"] for o in successful],
            "summary": "\n".join(summary_lines),
        }

        gate_id = fire_hitl(
            trigger="Campaign copy review — Stage 6",
            job_id=self.job_id,
            channel="email",
            context=context,
            recommended="Review generated copy in the dashboard. Approve to proceed to GO.",
        )

        alog("GATE",
             f"Campaign review gate fired (gate {gate_id}). "
             f"To approve: POST /gates/{gate_id}/resolve",
             job_id=self.job_id, channel="email", step="campaign_review")

        self._update_step(6, "review", "complete")

    # ── Stage 7: GO ────────────────────────────────────────────────────

    async def _stage_go(self, copy_outputs: list[dict]) -> dict:
        """Mark campaign complete. Return full summary."""
        self._update_step(7, "go", "running")
        update_job(self.job_id, progress="Stage 7/7: Campaign ready for GO...")

        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE campaigns SET status = 'awaiting_review', completed_at = ? WHERE id = ?",
                (now, self.campaign_id),
            )

        successful = [o for o in copy_outputs if "error" not in o]
        total_leads = sum(o.get("lead_count", 0) for o in successful)

        result = {
            "campaign_id": self.campaign_id,
            "status": "awaiting_review",
            "leak_types": len(successful),
            "total_leads": total_leads,
            "copy_sets": len(successful),
            "message": (
                f"Campaign complete. {len(successful)} leak types, {total_leads} leads. "
                f"HITL gate fired — awaiting review. "
                f"Once approved, arm email channel with POST /go/email."
            ),
        }

        self._update_step(7, "go", "complete")

        alog("INFO", f"Campaign {self.campaign_id} ready for review: {len(successful)} copy sets, {total_leads} leads",
             job_id=self.job_id, channel="email", step="campaign_go")

        return result

    # ── Helpers ─────────────────────────────────────────────────────────

    def _update_step(
        self,
        step_num: int,
        step_name: str,
        status: str,
        *,
        result: Optional[str] = None,
    ) -> None:
        """Update a campaign_steps row."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            if status == "running":
                db.execute(
                    "UPDATE campaign_steps SET status = ?, started_at = ? WHERE campaign_id = ? AND step_num = ?",
                    (status, now, self.campaign_id, step_num),
                )
            else:
                sets = "status = ?, completed_at = ?"
                params: list = [status, now]
                if result:
                    sets += ", result = ?"
                    params.append(result)
                params.extend([self.campaign_id, step_num])
                db.execute(
                    f"UPDATE campaign_steps SET {sets} WHERE campaign_id = ? AND step_num = ?",
                    params,
                )


# ── Task handler ───────────────────────────────────────────────────────

async def task_run_campaign(job_id: str, params: dict, caller: str) -> dict:
    """
    Run the full 7-stage Campaign Builder.
    Params: sector (str), location (str), limit (int), tone (str), dry_run (bool)
    """
    builder = CampaignBuilder(job_id=job_id, caller=caller)
    return await builder.run(params)
