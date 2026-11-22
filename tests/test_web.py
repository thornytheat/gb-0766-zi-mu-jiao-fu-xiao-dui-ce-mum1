def test_every_sheet(client, saved):
    for sheet, text in [('source','提交供应商原件'),('clock','该帧号已跳过'),('edits','B-01'),
                        ('overlaps','同轨目标帧相交'),('balance','740'),('pending','待选原稿'),
                        ('runs','复算该版'),('delivery','下载交付证据')]:
        response = client.get(f'/sheet/{sheet}?run={saved["id"]}')
        assert response.status_code == 200 and text in response.get_data(as_text=True)


def test_pending_tab_lists_candidate_groups(client, saved):
    html = client.get(f'/sheet/pending?run={saved["id"]}').get_data(as_text=True)
    assert 'C111' in html and 'PENDING' in html
    data = client.get(f'/api/check/pending?run={saved["id"]}').json
    assert data['frame_ledger']['pending_frames'] == 16
    assert data['groups'][0]['candidates'][0]['line'] == 14


def test_delivery_sheet_has_finalize_form(client, saved):
    html = client.get(f'/sheet/delivery?run={saved["id"]}').get_data(as_text=True)
    assert 'finalize-form' in html and 'value="14"' in html and 'value="15"' in html


def test_finalize_flow_through_delivery_page(client, saved):
    outcome = client.post(f"/api/delivery/{saved['id']}/finalize",
                          json={'decisions': [{'track': '简中', 'cue_id': 'C111', 'line': 14}]}).json
    html = client.get(f"/sheet/delivery?run={outcome['id']}").get_data(as_text=True)
    assert '候选均已定稿' in html


def test_sheet_cells_focusable(client):
    html = client.get('/').get_data(as_text=True)
    assert 'tabindex="0" data-cell="A1"' in html
    assert 'tabindex="-1" data-cell="B1"' in html


def test_unknown_sheet(client):
    response = client.get('/api/check/unknown')
    assert (response.status_code, response.json['code']) == (404, 'NO_SHEET')
