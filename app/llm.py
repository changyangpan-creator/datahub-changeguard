from __future__ import annotations

import os

from openai import AsyncOpenAI

from app.models import ChangeRequest, DataEntity, ImpactedEntity


class LLMPlanner:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    async def summarize(
        self,
        *,
        request: ChangeRequest,
        source: DataEntity,
        impacts: list[ImpactedEntity],
        risk_score: int,
        deterministic_summary: str,
    ) -> str:
        if not self.client:
            return deterministic_summary

        evidence = "\n".join(
            (
                f"- {item.name} ({item.entity_type}, {item.platform}), "
                f"depth={item.depth}, criticality={item.criticality.value}, "
                f"owner={item.owner or 'missing'}, fields={','.join(item.impacted_fields)}"
            )
            for item in impacts
        )
        prompt = f"""You are the planning layer of DataHub ChangeGuard.
Write one concise executive paragraph for a schema-change approval screen.
Use only the supplied DataHub evidence. Do not invent assets, owners, or metrics.
Lead with the decision and include the safest rollout pattern.

Source: {source.name}
Field: {request.field}
Change: {request.change_type.value}
Risk score: {risk_score}/100
Rationale: {request.rationale or 'not provided'}
Downstream evidence:
{evidence or '- No field-level downstream consumers found'}

Deterministic baseline:
{deterministic_summary}
"""
        try:
            response = await self.client.responses.create(
                model=self.model,
                input=prompt,
            )
            text = response.output_text.strip()
            return text or deterministic_summary
        except Exception:
            return deterministic_summary

