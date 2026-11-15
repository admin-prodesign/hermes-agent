"""``session.create`` ``source`` must accept every ``session_policy.SURFACES`` key."""
from gateway.session_policy import SURFACES
from tui_gateway.contracts.canonical_sessions import SessionCreateSource
from tui_gateway.contracts.registry import CANONICAL_METHODS, canonical_param_problems


def test_session_create_source_enum_matches_surfaces():
    assert set(SessionCreateSource) == set(SURFACES)


def test_session_create_accepts_known_sources_and_refuses_unknown():
    contract = CANONICAL_METHODS['session.create']
    for source in SURFACES:
        assert canonical_param_problems(contract, {'source': source, 'cwd': '/tmp'}) == []
    assert 'source' in canonical_param_problems(contract, {'source': 'not-a-surface', 'cwd': '/tmp'})
