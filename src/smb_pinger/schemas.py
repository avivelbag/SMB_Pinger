from pydantic import BaseModel, field_validator

from smb_pinger.url_utils import normalize_url


class BusinessCreate(BaseModel):
    name: str
    url: str
    category: str | None = None
    address: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("url")
    @classmethod
    def url_has_valid_format(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("url must not be empty")
        normalized = normalize_url(v)
        if not normalized:
            raise ValueError("invalid url")
        return v

    @property
    def normalized_url(self) -> str:
        return normalize_url(self.url)
