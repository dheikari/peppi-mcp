"""Fictional HOPS projections; never captured personal source bodies."""
from datetime import datetime, timezone
from urllib.parse import urlencode

from peppi_mcp.adapters.lapland_study_plan import PLAN_URL, PORTLET, PREFIX, parse_listing, normalize_plan


def version_url(key="501"):
    return PLAN_URL + "?" + urlencode({"p_p_id":PORTLET,"p_p_lifecycle":"0","p_p_state":"normal","p_p_mode":"view",
        PREFIX+"plannedPersonalCurriculumId":key,PREFIX+"struts.portlet.action":"/personalcurriculum/index",PREFIX+"struts.portlet.mode":"view"})


def metadata(right="right-a"):
    return {"study_right_key":right,"header":"FICTION2026 Hops-versio: 2 (DRAFT)","current_url":version_url(),
        "versions":[{"url":version_url(),"label":"2 DRAFT (voi muokata)"},{"url":version_url("502"),"label":"1 Hyväksytty"}]}


def listing(right="right-a"):
    return parse_listing(metadata(right), expected_right=right, retrieved_at=datetime(2026,10,3,tzinfo=timezone.utc))


def projection():
    group={"id":"1","parent_id":None,"plan_key":"501","source_kind":"STUDY_MODULE","course_code":"TEST-MODULE",
        "title":"Fictional required module","group":True,"summary":"1,5 op suorituksia<br/>3 op suunniteltu laajuus<br/>3 op tavoitelaajuus",
        "requirement":"","status":"","source_status":"","credits":None,"grade":None}
    rows=[{**group,"id":str(i+2),"parent_id":"1","source_kind":"COURSE_UNIT","course_code":"TEST"+str(i),"title":"Fictional course",
        "group":False,"summary":None,"requirement":"indicator compulsory","source_status":"Suoritettu","credits":"0,5 op","grade":"5"} for i in range(3)]
    return {"nodes":[group,*rows],"node_count":4,"summary":"1,5 op suorituksia<br/>0 op hopsin ulkopuoliset opinnot<br/>3 op suunniteltu laajuus<br/>3 op tavoitelaajuus",
        "scope":"HOPSin laajuus 3 / 3 op","total":"1,5"}


def plan(right="right-a"):
    return normalize_plan(projection(), listing(right))
