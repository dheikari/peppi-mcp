"""Strict tool arguments and the observed, explicitly limited public source schema."""

import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from peppi_mcp.models import Credits, NoArguments

CourseId = Annotated[str, Field(pattern=r"^[0-9]{1,12}$")]
SourceText = Annotated[str, Field(max_length=40000)]


class PageArguments(NoArguments):
    limit: int = Field(default=20, ge=1, le=50)
    cursor: str | None = Field(default=None, min_length=1, max_length=512)


class SearchArguments(PageArguments):
    query: str = Field(min_length=3, max_length=80)

    @field_validator("query")
    @classmethod
    def safe_query(cls, value):
        # A term or course code, never a URL or an arbitrary API path.
        if value != value.strip() or not re.fullmatch(r"[\w -]+", value, re.UNICODE):
            raise ValueError("Use letters, numbers, spaces, underscores or hyphens")
        return value


class CourseArguments(NoArguments):
    course_id: CourseId


class OfferingArguments(PageArguments):
    course_id: CourseId
    collection: Literal["current", "past"] = "current"
    date_from: str | None = None
    date_to: str | None = None

    @field_validator("date_from", "date_to")
    @classmethod
    def iso_day(cls, value):
        if value is not None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Use YYYY-MM-DD")
            date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not follow date_to")
        return self


class SourceRecord(BaseModel):
    # Unknown source fields are ignored; critical known fields are validated.
    model_config = ConfigDict(extra="ignore")


class Localized(SourceRecord):
    valueFi: SourceText
    valueEn: SourceText
    valueSv: SourceText

    def texts(self):
        return {"fi": self.valueFi, "en": self.valueEn, "sv": self.valueSv}


class Section(SourceRecord):
    title: Localized
    content: Localized


class SearchRow(SourceRecord):
    learningUnitId: CourseId
    code: Annotated[str, Field(min_length=1, max_length=150)]
    name: Localized
    type: Literal["COURSE_UNIT"]


class SearchResponse(SourceRecord):
    learningUnits: list[SearchRow] = Field(max_length=1000)
    numberOfAllMatchedRows: int = Field(ge=0, strict=True)


class CourseResponse(SourceRecord):
    id: CourseId | None
    code: Annotated[str, Field(min_length=1, max_length=150)]
    name: Localized
    credits: Credits | None
    minCredits: Credits | None
    maxCredits: Credits | None
    contentList: list[Section] = Field(max_length=100)

    @model_validator(mode="after")
    def credit_range(self):
        if self.minCredits is not None and self.maxCredits is not None and self.minCredits > self.maxCredits:
            raise ValueError("Inverted credit range")
        return self


EpochMilliseconds = Annotated[int, Field(strict=True, ge=-2208988800000, le=4102444800000)]


class OfferingResponse(SourceRecord):
    realisationId: CourseId
    code: Annotated[str, Field(min_length=1, max_length=150)]
    name: Localized
    startDate: EpochMilliseconds | None
    endDate: EpochMilliseconds | None
    enrollmentStartDateTime: EpochMilliseconds | None
    enrollmentEndDateTime: EpochMilliseconds | None
    seats: Annotated[int, Field(strict=True, ge=0)] | None
    contentList: list[Section] = Field(max_length=100)

    @model_validator(mode="after")
    def ordered_times(self):
        for first, last in ((self.startDate, self.endDate), (self.enrollmentStartDateTime, self.enrollmentEndDateTime)):
            if first is not None and last is not None and first > last:
                raise ValueError("Inverted source time range")
        return self
