from collections import defaultdict
from .account import account
from .reader import tabulate

FIELDS = ('cue_id', 'track', 'format', 'in', 'out', 'text')
MISSING = {'', '-', 'N/A', 'NULL', '未知'}
ALIASES = {'legacy_id': 'cue_id', 'time_in': 'in', 'time_out': 'out'}


def receive(text):
    rows, isolated, headings, blanks, data_lines = tabulate(text, ALIASES, FIELDS)
    groups = defaultdict(list)
    for row in rows:
        if any(row[key] in MISSING for key in FIELDS):
            isolated.append(dict(row, code='MISSING'))
        else:
            groups[row['track'], row['cue_id']].append(row)
    cues, copies, pending = [], [], []
    # 保留首次出现顺序，避免分组排序打乱行序。
    for (track, cue_id), group in groups.items():
        if len({tuple(row[key] for key in FIELDS) for row in group}) > 1:
            # 同轨同号内容冲突：整组保留为待选原稿，不再先挑一版，也不丢任何一版。
            isolated.extend(dict(row, code='CUE_CONFLICT') for row in group)
            pending.append(dict(track=track, cue_id=cue_id, status='PENDING',
                                candidates=[dict(row, pending=True) for row in group]))
        else:
            cues.append(group[0])
            copies.extend(dict(row, code='CUE_COPY') for row in group[1:])
    return dict(rows=cues, isolated=sorted(isolated, key=lambda row: row['line']), copies=copies,
                pending=pending,
                counts=account(cues, isolated, copies, headings, blanks, data_lines,
                               sum(len(group['candidates']) for group in pending)))
