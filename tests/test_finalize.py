"""待选原稿、帧台账与晚到定稿的端到端测试。"""
import pytest

CUES = """cue_id,track,format,in,out,text
C1,简中,FRAME,100,200,已确认字幕
C2,简中,FRAME,300,400,候选甲
C2,简中,FRAME,300,400,候选乙
C3,简中,FRAME,350,420,邻居字幕
"""
CUTS = """cut,start,end,target,kind
A-01,0,1000,0,KEEP
"""
MATERIAL = {'cues': CUES, 'cuts': CUTS}


def _publish(client, material=None):
    return client.post('/api/runs', json=material or MATERIAL).get_json()


def test_source_retains_all_candidates(client):
    run = _publish(client)
    entry = client.application.extensions['cut_archive'].read(run['id'])
    group, = entry['stages']['source']['pending']
    assert (group['track'], group['cue_id'], group['status']) == ('简中', 'C2', 'PENDING')
    assert [c['line'] for c in group['candidates']] == [3, 4]
    # 两版原稿都保留在隔离账中，未被任一版静默覆盖。
    conflict = [r for r in entry['stages']['source']['isolated'] if r['code'] == 'CUE_CONFLICT']
    assert {r['line'] for r in conflict} == {3, 4}


def test_frame_ledger_marks_ready_and_pending(client):
    run = _publish(client)
    export = client.get(f"/api/delivery/{run['id']}/export").get_json()
    ledger = export['frame_ledger']
    assert ledger['summary']['pending_frames'] == 80
    assert ledger['summary']['ready_frames'] == 96
    pending = [f for f in ledger['frames'] if f['state'] == 'PENDING']
    assert {f['frame'] for f in pending} == set(range(241, 321))
    # 每一待定帧都由候选 C2 占据；C3 独有的帧不被连坐，保持 READY。
    assert all('C2' in f['cues'] for f in pending)
    assert all(f['state'] in ('READY', 'PENDING') for f in ledger['frames'])
    assert len(ledger['frames']) == ledger['summary']['ready_frames'] + ledger['summary']['pending_frames']


def test_candidate_risk_separate_from_confirmed_overlap(client):
    run = _publish(client)
    entry = client.application.extensions['cut_archive'].read(run['id'])
    overlaps = entry['stages']['overlaps']
    assert overlaps['rows'] == []
    risk, = overlaps['candidate_risks']
    assert (risk['frame_in'], risk['frame_out'], risk['code']) == (281, 321, 'CANDIDATE_RISK')
    assert risk['pending_lines'] == [3, 4]
    assert overlaps['counts'] == dict(regions=0, overlap_frames=0,
                                      candidate_risk_regions=1, candidate_risk_frames=40)


def test_candidate_frames_stay_on_pending_side(client):
    run = _publish(client)
    stages = client.application.extensions['cut_archive'].read(run['id'])['stages']
    counts = stages['balance']['counts']
    assert counts['pending_cue_groups'] == 1
    assert int(counts['pending_candidate_frames']) > 0
    assert stages['balance']['balanced'] is True and stages['balance']['difference'] == '0'


def test_finalize_recomputes_and_promotes_risk(client):
    run = _publish(client)
    outcome = client.post(f"/api/delivery/{run['id']}/finalize",
                          json={'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': 3}]}).get_json()
    assert outcome['reused'] is False and outcome['id'] != run['id']
    assert outcome['frame_ledger'] == dict(
        ready_frames=176, pending_frames=0,
        tracks=[dict(track='简中', ready_frames=176, pending_frames=0, total=176)])
    finalized = client.application.extensions['cut_archive'].read(outcome['id'])
    assert finalized['stages']['pending'] == []
    winner = next(r for r in finalized['stages']['clock']['rows'] if r['cue_id'] == 'C2')
    assert winner['text'] == '候选甲'
    overlap, = finalized['stages']['overlaps']['rows']
    assert (overlap['frame_in'], overlap['frame_out'], overlap['cues']) == (281, 321, ['C2', 'C3'])
    assert finalized['stages']['overlaps']['candidate_risks'] == []


def test_same_decision_retry_is_idempotent(client):
    run = _publish(client)
    payload = {'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': 3}]}
    first = client.post(f"/api/delivery/{run['id']}/finalize", json=payload).get_json()
    second = client.post(f"/api/delivery/{run['id']}/finalize", json=payload).get_json()
    assert first['id'] == second['id'] and second['reused'] is True
    assert client.get('/api/runs').get_json()['count'] == 2


def test_switching_revision_creates_new_run(client):
    run = _publish(client)
    first = client.post(f"/api/delivery/{run['id']}/finalize",
                        json={'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': 3}]}).get_json()
    second = client.post(f"/api/delivery/{run['id']}/finalize",
                         json={'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': 4}]}).get_json()
    assert second['id'] not in (run['id'], first['id']) and second['reused'] is False
    export = client.get(f"/api/delivery/{second['id']}/export").get_json()
    assert next(r for r in export['stages']['clock']['rows'] if r['cue_id'] == 'C2')['text'] == '候选乙'


def test_decision_order_does_not_change_run_id(client):
    """同一决策集合无论提交顺序、分批还是一次性，都必须命中同一档号，不触发 DRIFT。"""
    cues = """cue_id,track,format,in,out,text
C1,简中,FRAME,100,200,甲一
C1,简中,FRAME,100,200,甲二
C2,英语,FRAME,100,200,乙一
C2,英语,FRAME,100,200,乙二
"""
    run = _publish(client, {'cues': cues, 'cuts': CUTS})
    partial = client.post(f"/api/delivery/{run['id']}/finalize",
                          json={'decisions': [{'track': '简中', 'cue_id': 'C1', 'line': 2}]}).get_json()
    chained = client.post(f"/api/delivery/{partial['id']}/finalize",
                          json={'decisions': [{'track': '英语', 'cue_id': 'C2', 'line': 4}]}).get_json()
    batched = client.post(f"/api/delivery/{run['id']}/finalize",
                          json={'decisions': [{'track': '英语', 'cue_id': 'C2', 'line': 4},
                                              {'track': '简中', 'cue_id': 'C1', 'line': 2}]}).get_json()
    assert batched['id'] == chained['id'] and batched['reused'] is True
    assert client.get(f"/api/delivery/{chained['id']}").get_json()['verified'] is True


def test_finalize_unknown_group_rejected_without_archive(client):
    run = _publish(client)
    response = client.post(f"/api/delivery/{run['id']}/finalize",
                           json={'decisions': [{'track': '简中', 'cue_id': 'NOPE', 'line': 1}]})
    assert (response.status_code, response.get_json()['code']) == (422, 'FINALIZE_TARGET')
    assert client.get('/api/runs').get_json()['count'] == 1


def test_finalize_line_outside_group_rejected(client):
    run = _publish(client)
    response = client.post(f"/api/delivery/{run['id']}/finalize",
                           json={'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': 99}]})
    assert (response.status_code, response.get_json()['code']) == (422, 'FINALIZE_TARGET')


def test_refinalize_settled_group_rejected(client):
    run = _publish(client)
    outcome = client.post(f"/api/delivery/{run['id']}/finalize",
                          json={'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': 3}]}).get_json()
    response = client.post(f"/api/delivery/{outcome['id']}/finalize",
                           json={'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': 4}]})
    assert (response.status_code, response.get_json()['code']) == (422, 'FINALIZE_TARGET')
    # 要换版必须回到仍含该候选组的父档，由父档派生出新档，而不是覆盖已签发证据。
    switched = client.post(f"/api/delivery/{run['id']}/finalize",
                           json={'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': 4}]})
    assert switched.status_code == 200 and switched.get_json()['id'] != outcome['id']


def test_finalize_payload_validation(client):
    run = _publish(client)
    bad = [
        {'decisions': []},
        {'decisions': [{'track': '简中', 'cue_id': 'C2'}]},
        {'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': '3'}]},
        {'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': 3},
                       {'track': '简中', 'cue_id': 'C2', 'line': 4}]},
    ]
    for payload in bad:
        response = client.post(f"/api/delivery/{run['id']}/finalize", json=payload)
        assert response.status_code == 422 and response.get_json()['code'] == 'PAYLOAD'


def test_evidence_package_carries_ledger_and_decisions(client):
    run = _publish(client)
    export = client.get(f"/api/delivery/{run['id']}/export").get_json()
    assert export['verified'] is True
    assert 'frame_ledger' in export and export['decisions'] == []
    assert export['manifest']['decision_sha256']
    outcome = client.post(f"/api/delivery/{run['id']}/finalize",
                          json={'decisions': [{'track': '简中', 'cue_id': 'C2', 'line': 3}]}).get_json()
    finalized = client.get(f"/api/delivery/{outcome['id']}/export").get_json()
    assert finalized['decisions'] == [{'track': '简中', 'cue_id': 'C2', 'line': 3}]
    assert finalized['manifest']['decision_sha256'] != export['manifest']['decision_sha256']


def test_tampered_ledger_fails_verification(client):
    run = _publish(client)
    entry = client.application.extensions['cut_archive'].read(run['id'])
    entry['frame_ledger']['summary']['ready_frames'] += 1
    from app.modules.delivery.service import signing
    from app.problems import Rejection
    with pytest.raises(Rejection, match='证据散列'):
        signing(entry)
