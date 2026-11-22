from flask import Blueprint, jsonify, request
from app.modules.runs.routes import archive
from app.modules.runs.service import record
from app.pipeline import inspect
from app.problems import Rejection
from .decisions import normalize

finalize = Blueprint('finalize', __name__)


def _parse_decisions(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('decisions'), list) or not payload['decisions']:
        raise Rejection('PAYLOAD', '提交非空 decisions 定稿列表')
    parsed, seen = [], set()
    for item in payload['decisions']:
        if not isinstance(item, dict) or set(item) != {'track', 'cue_id', 'line'}:
            raise Rejection('PAYLOAD', '每条定稿需含 track、cue_id、line')
        if not isinstance(item['line'], int):
            raise Rejection('PAYLOAD', 'line 必须为原行整数')
        marker = (item['track'], item['cue_id'])
        if marker in seen:
            raise Rejection('PAYLOAD', f"{item['track']}/{item['cue_id']} 重复定稿")
        seen.add(marker)
        parsed.append(dict(item))
    return parsed


@finalize.post('/api/delivery/<key>/finalize')
def settle(key):
    entry = archive().read(key)
    decisions = _parse_decisions(request.get_json(silent=True))
    source = inspect(entry['original'], until='source')
    groups = {(group['track'], group['cue_id']): group for group in source['pending']}
    settled = {(d['track'], d['cue_id']) for d in entry.get('decisions', [])}
    # 定稿必须命中仍待定的候选组；已结清的组不能再次定稿，不存在的组或原行拒绝且不留档。
    for item in decisions:
        marker = (item['track'], item['cue_id'])
        if marker in settled:
            raise Rejection('FINALIZE_TARGET', f"{item['track']}/{item['cue_id']} 已定稿")
        group = groups.get(marker)
        if group is None:
            raise Rejection('FINALIZE_TARGET', f"{item['track']}/{item['cue_id']} 没有待选原稿")
        if not any(candidate['line'] == item['line'] for candidate in group['candidates']):
            raise Rejection('FINALIZE_TARGET',
                            f"原行 {item['line']} 不属于 {item['track']}/{item['cue_id']} 候选组")
    merged = {(d['track'], d['cue_id']): d for d in entry.get('decisions', [])}
    for item in decisions:
        merged[(item['track'], item['cue_id'])] = item
    final_decisions = normalize(merged.values())
    result = record(archive(), entry['original'], final_decisions)
    result['settled'] = [dict(track=item['track'], cue_id=item['cue_id'], line=item['line'])
                         for item in final_decisions]
    return jsonify(result)
