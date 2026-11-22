from fractions import Fraction
from app.rational import show
from .coverage import union_length


def balance(cues, mapped, overlaps, rejected, pending_cues=None, pending_mapped=None, unresolved=None):
    pending_cues = pending_cues or []
    pending_mapped = pending_mapped or []
    unresolved = unresolved or []
    total = dict(original=Fraction(0), delivered=Fraction(0), removed=Fraction(0), pending=Fraction(0))
    rows = []
    tracks = sorted({row['track'] for row in cues} | {row['track'] for row in pending_cues})
    pending_lines = {row['line'] for row in pending_cues}
    for track in tracks:
        pieces = [row for row in mapped if row['track'] == track]
        exact = dict(original=union_length([row for row in cues if row['track'] == track]))
        for name, kind in [('delivered', 'KEEP'), ('removed', 'REMOVE'), ('pending', 'GAP')]:
            exact[name] = union_length([row for row in pieces if row['kind'] == kind])
        # 待定候选的源帧整体留在待证侧：定稿前不计入交付，避免先挑一版虚增覆盖。
        candidate_source = union_length([row for row in pending_cues if row['track'] == track])
        exact['original'] += candidate_source
        exact['pending'] += candidate_source
        for name, number in exact.items():
            total[name] += number
        rows.append(dict(track=track, **{name: show(value) for name, value in exact.items()}))
    gap = total['original'] - total['delivered'] - total['removed'] - total['pending']
    return dict(rows=rows,
                counts=dict(**{name: show(value) for name, value in total.items()},
                           rejected_unmeasurable=rejected, overlap_target_frames=overlaps,
                           pending_candidate_frames=show(union_length(pending_mapped)),
                           pending_cue_groups=len(unresolved),
                           pending_lines=sorted(pending_lines)),
                balanced=gap == 0, difference=show(gap))
