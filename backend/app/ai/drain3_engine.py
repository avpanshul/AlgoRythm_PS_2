r"""Item 4: Drain3 template-store persistence.

Real bug found live (2026-09-28 audit): `TemplateMiner` was an in-memory-only
singleton -- every backend restart reset its cluster-ID counter to 1 and
forgot every cluster it had ever seen. Reproduced: after a restart, 5
brand-new, genuinely unrelated log lines were assigned cluster IDs 1-5,
which collided with old `UnknownTemplate` DB rows from a *previous* process
lifetime (real 9-month-old SSH clusters) -- `_cluster_unknown_format`'s
upsert-by-cluster_id then silently merged the new, unrelated samples into
those old rows instead of creating new ones. `GET /unknown-clusters/1/samples`
showed a real "EVT~AuthAttempt~..." line sitting next to a real 2005
Apache log line under one "cluster."

Two independent layers of fix, since either one alone leaves a real gap:

1. Real disk persistence (drain3's own `FilePersistence`, gated behind
   ENABLE_DRAIN_PERSIST): the miner's actual cluster tree survives a
   restart, so IDs stay genuinely stable -- not just non-colliding, but the
   *same* cluster the same log line matched before. If the persisted state
   fails to load (corrupted file), falls back to today's original
   empty-start behavior -- logged, not silent, and the corrupt file is
   moved aside rather than repeatedly failing every future start.
2. A counter-reseed safety net (always on, independent of the flag above):
   on first real use after any empty start (persistence off, or on but
   nothing was ever saved yet), the miner's next-cluster-id counter is
   seeded from `MAX(cluster_id)` already in the `UnknownTemplate` table --
   so even a from-scratch miner can never hand out an ID that collides with
   a pre-existing DB row, regardless of whether persistence itself is
   enabled.
"""
import logging
import os

from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence
from drain3.template_miner_config import TemplateMinerConfig

from app.core.config import settings

log = logging.getLogger("drain3_engine")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
PERSIST_PATH = os.path.join(DATA_DIR, "drain3_state.bin")


class Drain3Engine:
    def __init__(self):
        config = TemplateMinerConfig()
        ini_path = os.path.join(os.path.dirname(__file__), "drain3.ini")
        config.load(ini_path) if os.path.exists(ini_path) else None
        config.profiling_enabled = False

        self._persistence_handler = None
        if settings.ENABLE_DRAIN_PERSIST:
            os.makedirs(DATA_DIR, exist_ok=True)
            self._persistence_handler = FilePersistence(PERSIST_PATH)

        self.miner = self._build_miner(config)
        self._counter_seeded = False

    def _build_miner(self, config: TemplateMinerConfig) -> TemplateMiner:
        try:
            return TemplateMiner(persistence_handler=self._persistence_handler, config=config)
        except Exception as e:
            # Real requirement: "if loading fails, fall back to today's
            # empty-start" -- move the corrupt file aside (so we don't fail
            # this same way on every future start with the same bad file)
            # and build fresh, persistence still enabled for new writes.
            log.warning("Drain3 persisted state failed to load (%s) -- falling back to empty-start", e)
            if self._persistence_handler is not None and os.path.exists(PERSIST_PATH):
                try:
                    os.rename(PERSIST_PATH, PERSIST_PATH + ".corrupt")
                except OSError:
                    pass
            return TemplateMiner(persistence_handler=self._persistence_handler, config=config)

    def _seed_counter_from_db_if_needed(self):
        """Safety net against colliding with pre-existing UnknownTemplate
        rows -- runs once, lazily (not at import time, to avoid a DB
        dependency during module import), only when the miner's own counter
        looks like a fresh/empty start (0) rather than one restored from a
        real persisted snapshot."""
        if self._counter_seeded:
            return
        self._counter_seeded = True
        if self.miner.drain.clusters_counter != 0:
            return  # real state was loaded (persistence hit) -- already correct, don't touch it
        try:
            from app.core.database import SessionLocal
            from app.models.all import UnknownTemplate

            db = SessionLocal()
            try:
                rows = db.query(UnknownTemplate.cluster_id).all()
                numeric_ids = [int(row[0]) for row in rows if str(row[0]).isdigit()]
            finally:
                db.close()
            if numeric_ids:
                seeded_to = max(numeric_ids)
                self.miner.drain.clusters_counter = seeded_to
                log.info("Drain3 fresh start -- seeded cluster-ID counter to %d from existing UnknownTemplate rows (collision prevention)", seeded_to)
        except Exception as e:  # noqa: BLE001 -- seeding is a safety net, never fatal to real clustering
            log.warning("Drain3 counter reseed from DB failed (continuing with counter=0): %s", e)

    def extract_template(self, log_line: str):
        self._seed_counter_from_db_if_needed()
        result = self.miner.add_log_message(log_line)
        return result

    def get_variables(self, log_line: str, template: str) -> dict:
        # Simplistic variable extractor based on Drain3 template <*>
        # For a production system this needs more robust regex matching
        # derived from the template exact tokens.
        extracted = self.miner.extract_parameters(template, log_line)
        if not extracted:
            return {}
        # Returns list of dicts or list of strings depending on Drain3 version
        vars_dict = {}
        for i, val in enumerate(extracted):
            vars_dict[f"var_{i}"] = val if isinstance(val, str) else val.value
        return vars_dict

drain3_engine = Drain3Engine()
