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
        raw_items = json.loads(content).get("recommendations", [])
        activity_map = {item.activity_id: item for item in activities}
        normalized: list[Recommendation] = []
        for item in raw_items:
            activity = activity_map.get(item.get("activity_id"))
            start_time, end_time = item.get("start_time"), item.get("end_time")
            if not activity or not isinstance(start_time, str) or not isinstance(end_time, str):
                continue
            start_minutes = int(start_time[:2]) * 60 + int(start_time[3:])
            end_minutes = int(end_time[:2]) * 60 + int(end_time[3:])
            if end_minutes - start_minutes != activity.duration_minutes:
                corrected_end = start_minutes + activity.duration_minutes
                end_time = f"{corrected_end // 60:02d}:{corrected_end % 60:02d}"
            matching_slot = next((
                slot for slot in slots
                if slot.start_time <= start_time < end_time <= slot.end_time
            ), None)
            if not matching_slot:
                continue
            normalized.append(Recommendation.model_validate({
                "activity_id": activity.activity_id,
                "activity_name": item.get("activity_name") or activity.activity_name,
                "category": item.get("category") or activity.category,
                "slot_type": item.get("slot_type") or matching_slot.slot_type,
                "start_time": start_time,
                "end_time": end_time,
                "duration_minutes": item.get("duration_minutes") or activity.duration_minutes,
                "reason": item.get("reason") or item.get("notes") or "현재 일정의 빈 시간과 활동 조건을 고려해 추천했습니다.",
                "status": item.get("status") if item.get("status") in {
                    "AVAILABLE", "CONFLICT", "INSUFFICIENT_TIME",
                    "OUTSIDE_PREFERRED_TIME", "ALREADY_COMPLETED",
                } else "AVAILABLE",
            }))
        return normalized or None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
