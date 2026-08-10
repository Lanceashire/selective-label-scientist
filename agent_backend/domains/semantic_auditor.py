"""Semantic audit with decision-dependent availability and temporal validation."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from ..schemas import DomainSpec

def _missing(value: Any) -> bool: return value in (None,"","NA","N/A","nan")
def _time(value: Any):
 try: return datetime.fromisoformat(str(value).replace("Z","+00:00"))
 except (TypeError,ValueError): return None
def label_availability_mask(rows: list[dict[str,Any]], target_column: str)->dict[str,Any]:
 missing=sum(_missing(row.get(target_column)) for row in rows); return {"target_column":target_column,"observed_count":len(rows)-missing,"missing_count":missing,"missing_rate":missing/max(1,len(rows)),"availability_by_row":"private"}
def audit_semantics(spec:DomainSpec|dict[str,Any],rows:list[dict[str,Any]],description:str="")->dict[str,Any]:
 content=spec.to_dict() if isinstance(spec,DomainSpec) else spec; d=content.get("historical_decision",{}); target=content.get("outcome",{}).get("column"); action=content.get("observation_action",{}); observed=set(map(str,d.get("observed_action_values",[]))); hidden=set(map(str,d.get("non_observed_action_values",[]))); confirmed=bool(d.get("confirmed")); checks=[{"name":"decision_mapping_confirmed","status":"PASS" if confirmed and observed and hidden and not observed&hidden else "NEEDS_USER_INPUT","detail":"需要人工确认 observed/non-observed action mapping"}]
 if not target: checks.append({"name":"label_availability","status":"NEEDS_USER_INPUT","detail":"未确认 outcome 字段"})
 else:
  mask=label_availability_mask(rows,str(target)); grouped:dict[str,list[int]]={}
  for row in rows:
   key=str(row.get(d.get("column"),"")); grouped.setdefault(key,[0,0]); grouped[key][0]+=1; grouped[key][1]+=int(not _missing(row.get(target)))
  rates=[{"decision_value":key,"sample_count":n,"visible_label_count":v,"visible_label_rate":v/max(1,n)} for key,(n,v) in grouped.items()]; diff=max((x["visible_label_rate"] for x in rates),default=0)-min((x["visible_label_rate"] for x in rates),default=0)
  status,detail=("PASS_WITH_WARNINGS","REPLAY MODE：人工确认映射；原始标签仅供私有 evaluator 重建") if mask["missing_count"]==0 and confirmed else ("NOT_SELECTIVE_LABEL","全量可见标签本身不能证明选择性标签机制") if mask["missing_count"]==0 else ("PASS","发现标签可见率差异；仍不替代业务语义确认")
  checks.append({"name":"label_availability","status":status,"detail":detail,"mask":mask,"by_decision_value":rates,"max_visible_rate_difference":diff})
 dt,ot=content.get("time",{}).get("decision_time"),content.get("time",{}).get("outcome_time")
 if not dt or not ot: checks.append({"name":"time_order","status":"NEEDS_USER_INPUT","detail":"需要确认决策和结果时间字段"})
 else:
  valid=invalid=missing=0
  for row in rows:
   a,b=_time(row.get(dt)),_time(row.get(ot))
   if not a or not b: missing+=1
   elif b>=a: valid+=1
   else: invalid+=1
  comparable=valid+invalid; rate=valid/max(1,comparable); status="BLOCKED" if invalid and invalid/max(1,len(rows))>.05 else "PASS_WITH_WARNINGS" if missing else "PASS"
  checks.append({"name":"time_order","status":status,"decision_time":dt,"outcome_time":ot,"valid_order_rate":rate,"invalid_order_count":invalid,"missing_time_count":missing})
 checks.append({"name":"observation_action","status":"PASS" if action.get("confirmed") and action.get("reversible") is True and action.get("simulatable") is True else "NEEDS_USER_INPUT","detail":"action 必须人工确认，禁止默认 true"})
 statuses={x["status"] for x in checks}; status="BLOCKED" if "BLOCKED" in statuses else "NOT_SELECTIVE_LABEL" if "NOT_SELECTIVE_LABEL" in statuses else "NEEDS_USER_INPUT" if "NEEDS_USER_INPUT" in statuses else "PASS_WITH_WARNINGS" if "PASS_WITH_WARNINGS" in statuses else "PASS"; return {"status":status,"checks":checks,"description":description,"semantic_confirmation_required":status!="PASS"}
