"""Unknown-format cluster review + AI-assisted pack drafting (closes the
agentic-onboarding loop's real gap: nothing previously let an analyst see a
Drain3 cluster and get a draft pack for it -- they had to already know a
cluster existed and hand-write YAML from scratch)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.all import UnknownTemplate, DLQEvent, User, AgentReasoningTraceEntry
from app.services.pack_drafting import draft_pack_for_cluster

router = APIRouter()


@router.get("/unknown-clusters")
def list_unknown_clusters(db: Session = Depends(get_db)):
    # Real bug found live: UnknownTemplate.event_count is a monotonically
    # incrementing counter (bumped once per unparseable event ever seen for
    # this cluster, in app/core/processing.py::_cluster_unknown_format) --
    # it never decreases when a later parser fix resolves that cluster's
    # real DLQ events. The list ended up showing hundreds of "unknown
    # clusters" that were actually already fixed (their DLQEvent rows are
    # now status="resolved"), with nothing real left to trace or draft
    # against. Recomputed live from DLQEvent so the count -- and which
    # clusters even appear -- reflects the real, current backlog.
    live_counts = dict(
        db.query(DLQEvent.drain_cluster_id, func.count(DLQEvent.id))
        .filter(DLQEvent.status == "failed", DLQEvent.drain_cluster_id.isnot(None))
        .group_by(DLQEvent.drain_cluster_id)
        .all()
    )
    clusters = db.query(UnknownTemplate).filter(UnknownTemplate.cluster_id.in_(live_counts.keys())).all()
    rows = [
        {
            "cluster_id": c.cluster_id,
            "template_str": c.template_str,
            "vendor": c.vendor,
            "event_count": live_counts.get(c.cluster_id, 0),
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in clusters
    ]
    rows.sort(key=lambda r: r["event_count"], reverse=True)
    return rows


@router.get("/unknown-clusters/{cluster_id}/samples")
def get_cluster_samples(cluster_id: str, db: Session = Depends(get_db)):
    # status == "failed": same live-backlog fix as list_unknown_clusters --
    # otherwise a resolved cluster's old, already-fixed samples still show
    # up here as if they were current unparsed work.
    rows = (
        db.query(DLQEvent.raw_log, DLQEvent.created_at)
        .filter(DLQEvent.drain_cluster_id == cluster_id, DLQEvent.status == "failed")
        .order_by(DLQEvent.created_at.desc())
        .limit(10)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No DLQ events found for this cluster")
    return [{"raw_log": r[0], "created_at": r[1]} for r in rows]


@router.post("/unknown-clusters/{cluster_id}/draft-pack")
def draft_pack(cluster_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cluster = db.query(UnknownTemplate).filter(UnknownTemplate.cluster_id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Unknown cluster not found")
    result = draft_pack_for_cluster(db, cluster_id, vendor=cluster.vendor)
    if result["status"] != "drafted":
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/unknown-clusters/{cluster_id}/reasoning-trace")
def get_reasoning_trace(cluster_id: str, db: Session = Depends(get_db)):
    """Item 5: every real attempt the agent refine loop made for this
    cluster's most recent draft-pack call, in order -- honest even when
    empty (ENABLE_AGENT_REFINE was off, or draft-pack was never called)."""
    rows = (
        db.query(AgentReasoningTraceEntry)
        .filter(AgentReasoningTraceEntry.cluster_id == cluster_id)
        .order_by(AgentReasoningTraceEntry.created_at.asc(), AgentReasoningTraceEntry.attempt_number.asc())
        .all()
    )
    return [
        {
            "attempt_number": r.attempt_number,
            "feedback_used": r.feedback_used,
            "mapped_field_count": r.mapped_field_count,
            "unmapped_field_count": r.unmapped_field_count,
            "field_classifications": r.field_classifications,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
