import redis
import json
from app.schemas.canonical import CanonicalEvent
from app.core.config import settings

class CorrelationEngine:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        # Sequence rules: state machine transitions
        self.rules = {
            "attack_sequence_1": ["port_scan", "login_failure", "login_success", "data_access"]
        }
        
    def track_and_correlate(self, event: CanonicalEvent) -> dict:
        action = event.event.action.lower()
        src_ip = event.source.ip
        
        if not src_ip:
            return {"correlation_score": 0, "frequency_score": 0}
            
        # 1. Frequency Tracking
        freq_key = f"freq:{src_ip}:{action}"
        self.redis.incr(freq_key)
        self.redis.expire(freq_key, 60) # 1 minute window
        freq_count = int(self.redis.get(freq_key) or 1)
        
        freq_score = 0
        if freq_count > 100:
            freq_score = 100
        elif freq_count > 20:
            freq_score = 50
        elif freq_count > 5:
            freq_score = 20
            
        # 2. Sequence Correlation
        corr_score = 0
        seq_key = f"seq:{src_ip}"
        current_state = self.redis.get(seq_key)
        
        if current_state:
            state = json.loads(current_state)
            seq = state["sequence"]
            
            # Simple check if this action advances any rule
            for rule_name, rule_seq in self.rules.items():
                # Where are we in this rule?
                expected_next = None
                for i, r_act in enumerate(rule_seq):
                    if r_act not in seq:
                        expected_next = r_act
                        break
                
                if action == expected_next:
                    seq.append(action)
                    state["sequence"] = seq
                    state["events"].append(event.event_id)
                    self.redis.setex(seq_key, 300, json.dumps(state)) # 5 mins
                    
                    if len(seq) == len(rule_seq):
                        # Sequence complete
                        corr_score = 100
                    else:
                        corr_score = int((len(seq) / len(rule_seq)) * 80)
        else:
            # Start new tracking if it's a first step
            for rule_name, rule_seq in self.rules.items():
                if action == rule_seq[0]:
                    state = {
                        "sequence": [action],
                        "events": [event.event_id],
                        "rule": rule_name
                    }
                    self.redis.setex(seq_key, 300, json.dumps(state))
                    corr_score = 20
                    break
                    
        return {
            "correlation_score": corr_score,
            "frequency_score": freq_score
        }

correlation_engine = CorrelationEngine()
