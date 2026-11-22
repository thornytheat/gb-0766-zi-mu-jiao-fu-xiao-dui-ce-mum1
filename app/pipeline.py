from .modules.source.service import receive
from .modules.clock.service import validate
from .modules.edits.contract import timeline
from .modules.edits.mapping import map_cues
from .modules.overlaps.service import locate
from .modules.balance.service import balance
from .modules.finalize.decisions import candidate_rows, decided_cues


def inspect(material, until=None, decisions=None):
    decisions = decisions or []
    source = receive(material['cues'])
    if until == 'source':
        return source
    accepted, unresolved = decided_cues(source, decisions)
    timing = validate(accepted)
    # 仍待定的候选照常试跑时码，坏时码的候选行隔离并从后续帧分析剔除；已定稿的组不再算候选。
    candidate_timing = validate(candidate_rows(unresolved))
    timing['pending_rows'] = candidate_timing['rows']
    timing['pending_isolated'] = candidate_timing['isolated']
    if until == 'clock':
        return timing
    cuts = map_cues(timing['rows'], timeline(material['cuts']))
    candidate_cuts = map_cues(timing['pending_rows'], timeline(material['cuts']))
    cuts['pending_rows'] = candidate_cuts['rows']
    if until == 'edits':
        return cuts
    clashes = locate(cuts['rows'], candidate_cuts['rows'])
    if until == 'overlaps':
        return clashes
    rejected = (len(source['isolated']) + len(timing['isolated'])
                + len(timing['pending_isolated']))
    check = balance(timing['rows'], cuts['rows'], clashes['counts']['overlap_frames'], rejected,
                    timing['pending_rows'], cuts['pending_rows'], unresolved)
    if until == 'balance':
        return check
    return dict(source=source, clock=timing, edits=cuts, overlaps=clashes, balance=check,
                pending=unresolved, decisions=decisions)
