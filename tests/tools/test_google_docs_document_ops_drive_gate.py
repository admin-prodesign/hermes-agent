"""Drive ACL fallback for Google Docs document-ops authorization."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools.pd_one_ops import google_docs_document_ops as docs

_TOOLS_DIR = str(Path(docs.__file__).resolve().parent)

_MM_ID = 'abcdefghijklmnopqrstuvwxyz'
_MM_ALLOWLISTED = 'allowlistuserabcdefghijklm'
_FILE_ID = '1QG9ectl_Qn2iAzkilHT8gU88P_us1Gc4DV8c3yb58WI'

_SAMPLE_REGISTRY = {
    'schema': 'pd-one.google-docs-document-ops.v1',
    'allowed_requester_ids': [_MM_ALLOWLISTED],
    'documents': {
        'qa_manual': {
            'document_id': _FILE_ID,
            'title': 'QA Manual',
            'scope': 'work-manual',
            'live_enabled': True,
            'allowed_actions': ['inspect', 'list_registered_documents'],
        },
    },
}

_SAMPLE_DOCUMENT = _SAMPLE_REGISTRY['documents']['qa_manual']


def _registry_path(tmp_path: Path) -> Path:
    path = tmp_path / 'google_docs_document_ops_registry.json'
    path.write_text(json.dumps(_SAMPLE_REGISTRY), encoding='utf-8')
    return path


def _drive_writer():
    return {'status': 'ok', 'canWrite': True, 'canRead': True, 'canComment': False}

def _drive_viewer():
    return {'status': 'ok', 'canWrite': False, 'canRead': True, 'canComment': False}

def _drive_denied():
    return {'status': 'denied', 'canWrite': False, 'canRead': False, 'reason': 'no_matching_ace'}


def _patch_drive_authorize(monkeypatch, handler):
    if _TOOLS_DIR not in sys.path:
        monkeypatch.syspath_prepend(_TOOLS_DIR)
    import drive_acl_authorize as drive_mod

    monkeypatch.setattr(drive_mod, 'authorize', handler)
    return drive_mod


def test_non_allowlisted_drive_writer_can_inspect(monkeypatch, tmp_path):
  """Writer/editor Drive ACL permits inspect without registry allowlist."""
  registry_path = _registry_path(tmp_path)
  registry = json.loads(registry_path.read_text(encoding='utf-8'))

  def fake_authorize(file_id, *, mattermost_user_id='', **kwargs):
      assert file_id == _FILE_ID
      assert mattermost_user_id == _MM_ID
      return _drive_writer()

  monkeypatch.setattr(docs, '_authorize_work_manual_grant', lambda *a, **k: False)
  _patch_drive_authorize(monkeypatch, fake_authorize)

  docs._authorize_document_requester(
      registry,
      _SAMPLE_DOCUMENT,
      requester_user_id=_MM_ID,
      live=False,
  )


def test_non_writer_stays_not_authorized(monkeypatch, tmp_path):
  registry_path = _registry_path(tmp_path)
  registry = json.loads(registry_path.read_text(encoding='utf-8'))

  _patch_drive_authorize(monkeypatch, lambda *a, **k: _drive_viewer())
  monkeypatch.setattr(docs, '_authorize_work_manual_grant', lambda *a, **k: False)

  with pytest.raises(PermissionError, match='not authorized'):
      docs._authorize_document_requester(
          registry,
          _SAMPLE_DOCUMENT,
          requester_user_id=_MM_ID,
          live=False,
      )


def test_allowlisted_requester_skips_drive_check(monkeypatch, tmp_path):
  registry_path = _registry_path(tmp_path)
  registry = json.loads(registry_path.read_text(encoding='utf-8'))
  called = {'n': 0}

  def boom(*a, **k):
      called['n'] += 1
      raise AssertionError('drive authorize must not run for allowlisted requesters')

  _patch_drive_authorize(monkeypatch, boom)

  docs._authorize_document_requester(
      registry,
      _SAMPLE_DOCUMENT,
      requester_user_id=_MM_ALLOWLISTED,
      live=False,
  )
  assert called['n'] == 0


def test_list_stays_denied_without_allowlist_even_if_drive_would_allow(monkeypatch, tmp_path):
  """list_registered_documents never consults Drive ACL (document is None)."""
  registry_path = _registry_path(tmp_path)
  called = {'n': 0}

  def fake_authorize(*a, **k):
      called['n'] += 1
      return _drive_writer()

  _patch_drive_authorize(monkeypatch, fake_authorize)
  monkeypatch.setattr(docs, 'RECEIPT_ROOT', lambda: tmp_path / 'receipts')

  result = docs.execute_document_ops(
      action='list_registered_documents',
      requester_user_id=_MM_ID,
      registry_path=registry_path,
  )
  assert result['status'] == 'error'
  assert result.get('error') == 'not_authorized'
  assert called['n'] == 0


def test_non_ok_drive_result_denied(monkeypatch, tmp_path):
  registry_path = _registry_path(tmp_path)
  registry = json.loads(registry_path.read_text(encoding='utf-8'))

  _patch_drive_authorize(monkeypatch, lambda *a, **k: _drive_denied())
  monkeypatch.setattr(docs, '_authorize_work_manual_grant', lambda *a, **k: False)

  with pytest.raises(PermissionError, match='not authorized'):
      docs._authorize_document_requester(
          registry,
          _SAMPLE_DOCUMENT,
          requester_user_id=_MM_ID,
          live=False,
      )