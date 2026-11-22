from app.digests import digest, encode
from app.problems import Rejection

PENDING = 'PENDING'
FINAL = 'FINAL'


def decided_cues(source, decisions):
    """把待选原稿按定稿记录折成采信行；无定稿时候选整体保留为待定。

    decisions: {f"{track}\u001f{cue_id}": {"line": 原行, "text": 选定文本, ...}}
    返回 (采信字幕行, 定稿后仍待定的候选组)。
    """
    chosen, unresolved = [], []
    index = {(row['track'], row['cue_id']): row for row in decisions}
    for group in source['pending']:
        key = (group['track'], group['cue_id'])
        decision = index.get(key)
        if decision is None:
            unresolved.append(group)
            continue
        matches = [candidate for candidate in group['candidates'] if candidate['line'] == decision['line']]
        if not matches:
            raise Rejection('FINALIZE_TARGET',
                            f"定稿原行 {decision['line']} 不属于 {group['track']}/{group['cue_id']} 候选组")
        winner = dict(matches[0])
        winner.pop('pending', None)
        chosen.append(winner)
    return source['rows'] + chosen, unresolved


def candidate_rows(groups):
    """把候选组拍平成行，供时码/切版试跑；每行带 pending 标记。"""
    return [dict(candidate) for group in groups for candidate in group['candidates']]


def decision_fingerprint(decisions):
    """定稿决策的稳定散列：同一份定稿重试得到同一指纹，从而命中幂等。"""
    payload = [dict(track=item['track'], cue_id=item['cue_id'], line=item['line']) for item in decisions]
    return digest(encode(sorted(payload, key=lambda item: (item['track'], item['cue_id'], item['line']))))


def normalize(decisions):
    """规范决策顺序：同一决策集合无论提交顺序如何，流水线行序与散列都一致。"""
    return sorted((dict(item) for item in decisions),
                  key=lambda item: (item['track'], item['cue_id'], item['line']))
