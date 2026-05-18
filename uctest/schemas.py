from typing import Literal

from pydantic import BaseModel, Field


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class UserProfile(BaseModel):
    betting_pref: str = ""
    purchase_cn: int | None = None
    cheer_engagement: str = ""
    fav_sport_1: str = ""
    fav_sport_2: str = ""
    fav_sport_3: str = ""


class Character(BaseModel):
    name: str = Field(..., min_length=1)
    gender: Literal["male", "female"]
    personality: Literal["외향", "내향"]


class Slots(BaseModel):
    data: str = ""
    style: str = ""
    policy: str = ""
    tone: str = ""
    history: list[HistoryTurn] = []
    tools: list[dict] = []
    user_profile: UserProfile | None = None
    user_disposition: str = ""
    recent_cheers: list[str] = []
    # events: 질문 시점 최근 발생 이벤트 리스트. 종목마다 스키마 편차가 있어
    # (축구 `match_minute` vs 야구 `inning`) list[dict]로 자유도 유지. data는
    # "지금까지의 누적 스냅샷"이고 events는 "방금 일어난 건"에 대한 포커스 신호.
    events: list[dict] = []
    # odds: 시장 배당 스냅샷 (홈/무승부/원정 + 시작값과 현재값 비교 신호).
    # 시스템 프롬프트의 [배당 활용] 가이드를 받아 승패 가능성 추측의 근거로 사용.
    # 자유 텍스트라 종목·시장별 포맷 차이를 흡수 (축구 1×2 vs 야구 머니라인 등).
    odds: str = ""
    # character: 봇 정체성(이름·성별) 슬롯. style/tone과 직교 — 자유 조합 가능.
    # 옛 persona가 어휘·문체·캐릭터를 묶어 tone과 충돌한 전철 회피용으로 정체성만 분리.
    character: Character | None = None


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    slots: Slots = Slots()
    provider: str | None = None
    model: str | None = None
    temperature: float | None = Field(None, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=1)


class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class ChatResponse(BaseModel):
    request_id: str
    answer: str
    rendered_system: str
    rendered_user: str
    provider: str
    model: str
    latency_ms: int
    usage: Usage | None = None
    emotion: str | None = None
