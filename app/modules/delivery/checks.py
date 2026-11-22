from app.digests import digest, encode, fingerprints
from app.problems import Rejection


def verify(record):
    stamp = record['manifest']
    stages_blob = dict(stages=record['stages'], frame_ledger=record['frame_ledger'])
    if (fingerprints(record['original']) != stamp['input_sha256'] or
            digest(encode(stages_blob)) != stamp['result_sha256'] or
            not record['stages']['source']['counts']['balanced'] or
            not record['stages']['balance']['balanced']):
        raise Rejection('INVALID_EVIDENCE', '证据散列或覆盖勾稽不符', 409)
    return stamp
