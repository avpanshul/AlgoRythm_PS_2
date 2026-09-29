r"""Entity graph + attack-path reconstruction (ULPF-phase2-prompt.md E2/E8).

Built directly from real NormalizedEvent rows (source_ip/dest_ip pairs) --
no synthetic graph data. Reuses E1's `correlation_id` (attached to edges
whose underlying event matched a correlation rule) and E7a's Sentinel
`risk_score` (attached to nodes) rather than inventing a third scoring
system.

E8's "likely next targets" is explicitly proximity-based (same /24 as the
current front, not yet visited), never a predictive claim -- per
ULPF-phase2-prompt.md's own Ground Rule 5 ("shows attack path so far" /
"flags likely next targets by proximity", never "predicts breaches"). No
string in this module or its API layer should ever say "predict".
"""
import ipaddress
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.all import NormalizedEvent, EntityProfile, CorrelatedIncident

MAX_NODES = 2000  # E2's own stated cap for a single graph render
TIMELINE_MAX_EVENTS = 1000


def build_graph(db: Session, entity: str = None, limit: int = MAX_NODES) -> dict:
    """Builds a node/edge graph from real source_ip->dest_ip pairs. If
    `entity` is given, returns only that entity's immediate neighborhood
    (its own edges) -- the "pivot" operation E3's threat-hunting workspace
    needs: one click from any IP shows everything connected to it."""
    q = db.query(NormalizedEvent).filter(
        NormalizedEvent.source_ip.isnot(None), NormalizedEvent.dest_ip.isnot(None)
    )
    if entity:
        q = q.filter((NormalizedEvent.source_ip == entity) | (NormalizedEvent.dest_ip == entity))
    events = q.order_by(NormalizedEvent.timestamp.desc()).limit(limit * 5).all()  # oversample pairs, dedupe below

    edge_key = lambda e: (e.source_ip, e.dest_ip)
    edges = defaultdict(lambda: {"count": 0, "last_seen": None, "correlation_ids": set()})
    node_ids = set()

    for e in events:
        node_ids.add(e.source_ip)
        node_ids.add(e.dest_ip)
        if len(node_ids) > limit:
            break
        key = edge_key(e)
        edge = edges[key]
        edge["count"] += 1
        if not edge["last_seen"] or (e.timestamp and e.timestamp > edge["last_seen"]):
            edge["last_seen"] = e.timestamp
        if e.correlation_id:
            edge["correlation_ids"].add(e.correlation_id)

    profiles = {p.entity_id: p for p in db.query(EntityProfile).filter(EntityProfile.entity_id.in_(node_ids)).all()}

    nodes = [
        {
            "id": node_id,
            "risk_score": profiles[node_id].risk_score if node_id in profiles else None,
            "event_count": profiles[node_id].event_count if node_id in profiles else None,
        }
        for node_id in node_ids
    ]
    edge_list = [
        {
            "source": src, "target": dst, "weight": data["count"],
            "last_seen": data["last_seen"].isoformat() if data["last_seen"] else None,
            "correlation_ids": sorted(data["correlation_ids"]),
        }
        for (src, dst), data in edges.items()
        if src in node_ids and dst in node_ids
    ]
    return {"nodes": nodes, "edges": edge_list, "truncated": len(node_ids) >= limit}


def _event_summary(e: NormalizedEvent) -> dict:
    data = e.event_data or {}
    return {
        "event_id": e.event_id,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "source_ip": e.source_ip,
        "dest_ip": e.dest_ip,
        "user_name": e.user_name,
        "device_vendor": e.device_vendor,
        "device_product": e.device_product,
        "category": data.get("category"),
        "action": data.get("action"),
        "outcome": data.get("outcome"),
        "severity": data.get("severity") or e.risk_level,
        "message": e.message,
        "correlation_id": e.correlation_id,
        "source_id": e.source_id,
    }


def build_timeline(db: Session, entity: str = None, incident_id: str = None, limit: int = TIMELINE_MAX_EVENTS) -> dict:
    """Real chronological event strip for one entity or one correlated
    incident (ULPF-phase2-prompt.md E2's "timeline" visualization). Two
    modes, mutually exclusive:

    - `incident_id`: pulls the exact event set E1's correlation engine
      already recorded for that `CorrelatedIncident` (`event_ids`), in
      timestamp order -- this is literally "what happened, in what order,
      that made this incident fire".
    - `entity`: every real event where this IP/user appears as source or
      dest or actor, in timestamp order -- "everything this entity did or
      had done to it".

    No synthetic events, no fabricated ordering -- an entity/incident with
    no events returns an honest empty list, not a placeholder.
    """
    if incident_id:
        incident = db.query(CorrelatedIncident).filter(CorrelatedIncident.id == incident_id).first()
        if not incident:
            return {"mode": "incident", "incident_id": incident_id, "events": [], "found": False}
        events = (
            db.query(NormalizedEvent)
            .filter(NormalizedEvent.event_id.in_(incident.event_ids))
            .order_by(NormalizedEvent.timestamp.asc())
            .limit(limit)
            .all()
        )
        return {
            "mode": "incident",
            "incident_id": incident_id,
            "found": True,
            "rule_name": incident.rule_name,
            "status": incident.status,
            "events": [_event_summary(e) for e in events],
        }

    if entity:
        events = (
            db.query(NormalizedEvent)
            .filter(
                (NormalizedEvent.source_ip == entity)
                | (NormalizedEvent.dest_ip == entity)
                | (NormalizedEvent.user_name == entity)
            )
            .order_by(NormalizedEvent.timestamp.asc())
            .limit(limit)
            .all()
        )
        return {
            "mode": "entity",
            "entity": entity,
            "events": [_event_summary(e) for e in events],
            "truncated": len(events) >= limit,
        }

    return {"mode": None, "events": [], "error": "provide either ?entity= or ?incident_id="}


def _same_proximity_zone(a: str, b: str) -> bool:
    """Same /24 -- a simple, explainable proximity rule (not a learned
    model), consistent with E8's requirement that "worth watching" be
    explainable proximity, not a black-box prediction."""
    try:
        return ipaddress.ip_network(f"{a}/24", strict=False) == ipaddress.ip_network(f"{b}/24", strict=False)
    except ValueError:
        return False


def reconstruct_attack_path(db: Session, entity: str, max_hops: int = 10) -> dict:
    """Forward-time BFS from `entity`: each hop is a real edge (an actual
    event connecting two IPs) that occurs chronologically after the previous
    hop's arrival, reconstructing the chain this entity has actually
    touched -- not a simulation, not a prediction. The graph is directed and
    time-ordered by construction (a hop can only follow an earlier one).
    """
    events = (
        db.query(NormalizedEvent)
        .filter(NormalizedEvent.source_ip.isnot(None), NormalizedEvent.dest_ip.isnot(None))
        .order_by(NormalizedEvent.timestamp.asc())
        .all()
    )
    if not events:
        return {"path": [], "front": entity, "proximity_watchlist": []}

    by_source = defaultdict(list)
    for e in events:
        by_source[e.source_ip].append(e)

    visited = {entity}
    path = []
    front = entity
    front_time = events[0].timestamp  # earliest possible starting point

    for _ in range(max_hops):
        # Earliest edge from the current front that happens at/after the
        # front's own arrival time and leads somewhere not yet visited.
        candidates = [e for e in by_source.get(front, []) if e.timestamp >= front_time and e.dest_ip not in visited]
        if not candidates:
            break
        hop = min(candidates, key=lambda e: e.timestamp)
        path.append({
            "from": hop.source_ip, "to": hop.dest_ip, "at": hop.timestamp.isoformat() if hop.timestamp else None,
            "event_id": hop.event_id, "correlation_id": hop.correlation_id,
        })
        visited.add(hop.dest_ip)
        front = hop.dest_ip
        front_time = hop.timestamp

    all_ips = {e.source_ip for e in events} | {e.dest_ip for e in events}
    proximity_watchlist = sorted(
        ip for ip in all_ips if ip not in visited and _same_proximity_zone(ip, front)
    )[:20]

    return {
        "path": path,
        "front": front,
        "proximity_watchlist": proximity_watchlist,
        "proximity_note": "Same /24 as the current front, not yet touched by this path -- "
                           "flagged as worth watching by network proximity alone, never a forecast "
                           "of where this actor will go next.",
    }
