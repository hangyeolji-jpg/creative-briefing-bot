from dataclasses import dataclass


@dataclass
class Ad:
    """수집된 광고 한 건. 성과 지표는 공개되지 않을 수 있어 None 허용."""

    advertiser: str
    industry: str
    likes: int | None
    ctr: float | None
    format: str
    caption: str
    link: str
    thumbnail: str | None = None
