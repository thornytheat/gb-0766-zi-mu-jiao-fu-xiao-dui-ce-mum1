"""帧级交付台账：逐整数目标帧判定可交（READY）或待定（PENDING）。

交付帧沿用既有口径：KEEP 段的整数网格点，区间左闭右开，两端点向上取整。
一帧只有当某个待定候选字幕本身占据该帧时才记 PENDING；
仅由已采信字幕占据的帧始终 READY，即使落在候选的覆盖区间附近也不连坐。
"""
from collections import defaultdict

READY = 'READY'
PENDING = 'PENDING'


def _keep(rows):
    return [row for row in rows if row['kind'] == 'KEEP' and row['frame_in'] < row['frame_out']]


def frame_ledger(confirmed_mapped, candidate_mapped):
    tracks = defaultdict(lambda: ({}, set(), set()))
    for row in _keep(confirmed_mapped):
        owners, _, confirmed_points = tracks[row['track']]
        for point in range(row['frame_in'], row['frame_out']):
            confirmed_points.add(point)
            owners.setdefault(point, []).append((row['line'], row['cue_id']))
    for row in _keep(candidate_mapped):
        owners, pending_points, _ = tracks[row['track']]
        for point in range(row['frame_in'], row['frame_out']):
            pending_points.add(point)
            owners.setdefault(point, []).append((row['line'], row['cue_id']))
    summary_tracks, frames = [], []
    for track in sorted(tracks):
        owners, pending_points, confirmed_points = tracks[track]
        track_frames = []
        for point in sorted(owners):
            tokens = sorted(owners[point])
            entry = dict(track=track, frame=point,
                         state=PENDING if point in pending_points else READY,
                         lines=[token[0] for token in tokens],
                         cues=[token[1] for token in tokens])
            if point not in confirmed_points:
                entry['candidate_only'] = True
            track_frames.append(entry)
        frames.extend(track_frames)
        ready = sum(item['state'] == READY for item in track_frames)
        pending = sum(item['state'] == PENDING for item in track_frames)
        summary_tracks.append(dict(track=track, ready_frames=ready,
                                   pending_frames=pending, total=ready + pending))
    summary = dict(ready_frames=sum(item['ready_frames'] for item in summary_tracks),
                   pending_frames=sum(item['pending_frames'] for item in summary_tracks),
                   tracks=summary_tracks)
    return dict(summary=summary, frames=frames)
