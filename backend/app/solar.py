import json
import os
import httpx
from .models import Activity, ActivityDay, AvailableSlot, Recommendation


async def request_solar_recommendations(
    date: str, day: ActivityDay, classes: list[dict], slots: list[AvailableSlot],
    activities: list[Activity],
) -> list[Recommendation] | None:
    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
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
