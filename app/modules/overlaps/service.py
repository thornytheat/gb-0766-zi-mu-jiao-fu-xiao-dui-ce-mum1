from collections import defaultdict
from .sweep import spans


def _intervals(fragments, pending):
    groups = defaultdict(list)
    pending_lines = {row['line'] for row in pending}
    for row in fragments:
        if row['kind'] == 'KEEP':
            token = (row['line'], row['cue_id'], row['line'] in pending_lines)
            groups[row['track']].append((row['frame_in'], row['frame_out'], token))
    return groups


def locate(fragments, pending=None):
    pending = pending or []
    # 候选片段并入同一条扫描线，才能定位“候选 vs 已采信字幕”的撞帧风险。
    rows, risk_rows = [], []
    for track, intervals in sorted(_intervals(list(fragments) + list(pending), pending).items()):
        for left, right, active in spans(intervals):
            if len(active) <= 1:
                continue
            # 同轨同号的候选稿彼此重叠是版本内重复，不是撞帧；只报不同字幕号之间的相交。
            distinct = {token[1] for token in active}
            if len(distinct) <= 1:
                continue
            lines = [token[0] for token in active]
            cues = [token[1] for token in active]
            entry = dict(track=track, frame_in=left, frame_out=right, frames=right-left,
                         lines=lines, cues=cues, code='OVERLAP')
            if any(token[2] for token in active):
                entry['code'] = 'CANDIDATE_RISK'
                entry['pending_lines'] = [token[0] for token in active if token[2]]
                risk_rows.append(entry)
            else:
                rows.append(entry)
    return dict(rows=rows, candidate_risks=risk_rows,
                counts=dict(regions=len(rows),
                            overlap_frames=sum(row['frames'] for row in rows),
                            candidate_risk_regions=len(risk_rows),
                            candidate_risk_frames=sum(row['frames'] for row in risk_rows)))
