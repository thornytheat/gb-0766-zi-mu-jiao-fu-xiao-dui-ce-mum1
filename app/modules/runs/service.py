from datetime import datetime, timezone
from time import perf_counter_ns
from app.digests import digest, encode, fingerprints
from app.frame_ledger import frame_ledger
from app.pipeline import inspect
from app.problems import Rejection
from app.settings import VERSION
from app.modules.finalize.decisions import decision_fingerprint, normalize


def record(store, material, decisions=None):
    decisions = normalize(decisions or [])
    start = perf_counter_ns()
    hashes = fingerprints(material)
    decision_hash = decision_fingerprint(decisions)
    # 档号同时绑定原件指纹与定稿决策：同一份定稿重试得到同一档号（幂等不重复签发），
    # 新定稿或换版决策自然产生新档号。
    key = digest(encode([VERSION, hashes, decision_hash]))
    stages = inspect(material, decisions=decisions)
    ledger = frame_ledger(stages['edits']['rows'], stages['edits']['pending_rows'])
    result_hash = digest(encode(dict(stages=stages, frame_ledger=ledger)))
    manifest = dict(id=key, version=VERSION, input_sha256=hashes, result_sha256=result_hash,
                    decision_sha256=decision_hash,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    elapsed_us=(perf_counter_ns() - start) // 1000)
    envelope = dict(manifest=manifest, original=material, stages=stages,
                    frame_ledger=ledger, decisions=decisions)
    actual, reused = store.publish(key, envelope)
    if actual['manifest']['result_sha256'] != result_hash or digest(
            encode(dict(stages=actual['stages'], frame_ledger=actual['frame_ledger']))) != result_hash:
        raise Rejection('DRIFT', '复算与已归档结果不一致', 409)
    return dict(summary(actual), reused=reused)


def summary(record):
    return dict(id=record['manifest']['id'], manifest=record['manifest'],
                counts=record['stages']['balance']['counts'],
                frame_ledger=record['frame_ledger']['summary'])
