import json
import os
import httpx
from .models import Activity, ActivityDay, AvailableSlot, InefficiencyModeConfig, Recommendation, RecoveryAnalysis


async def request_solar_recommendations(
    date: str, day: ActivityDay, classes: list[dict], slots: list[AvailableSlot],
    activities: list[Activity],
) -> list[Recommendation] | None:
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        return None


async def request_recovery_explanation(
    config: InefficiencyModeConfig, analysis: RecoveryAnalysis,
) -> str | None:
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        return None
    payload = {
        "requestType": "RECOVERY_SCORE_EXPLANATION",
        "weeklyCondition": config.weekly_condition if config.weekly_condition is not None else 50,
        "targetScheduleDensity": config.target_schedule_density,
        "recoveryScore": analysis.score,
        "recoveryGrade": analysis.grade,
        "scoreDetails": analysis.details.model_dump(),
        "analysisData": {
            "totalRestMinutes": analysis.total_rest_minutes,
            "scheduleDensityPercent": analysis.schedule_density_percent,
            "longestContinuousFocusMinutes": analysis.longest_continuous_focus_minutes,
            "recoveryActivityMinutes": analysis.recovery_activity_minutes,
        },
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://api.upstage.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "solar-pro3",
                "messages": [
                    {"role": "system", "content": "주어진 점수와 등급은 변경하지 말고, 낮아진 원인·잘 확보된 회복 요소·개선 방법을 의료적 판단 없이 한국어 3문장 이내로 설명하세요."},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            },
        )
        response.raise_for_status()
    try:
        return response.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, TypeError, AttributeError):
        return None
    payload = {
        "requestType": "ACTIVITY_RECOMMENDATION", "date": date, "day": day,
        "timezone": "Asia/Seoul", "classes": classes,
        "availableSlots": [item.model_dump(by_alias=True) for item in slots],
        "activities": [item.model_dump(by_alias=True) for item in activities],
    }
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(
            "https://api.upstage.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "solar-pro3",
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "제공된 빈 시간을 다시 계산하지 말고 활동 추천만 수행하세요. Recommendation 필드는 activity_id, activity_name, category, slot_type, start_time, end_time, duration_minutes, reason, status의 snake_case로 작성하고 recommendations 배열을 가진 JSON으로만 답하세요."},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            },
        )
        response.raise_for_status()
    try:
        content = response.json()["choices"][0]["message"]["content"]
        return [Recommendation.model_validate(item) for item in json.loads(content).get("recommendations", [])]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
