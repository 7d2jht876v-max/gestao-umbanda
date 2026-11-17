"""Protect the cloud-write opt-out without changing saved user records."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CloudDisabledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'index.html').read_text(encoding='utf-8')

    def test_main_sync_and_medium_publication_require_notebook(self):
        self.assertIn("const localNotebookSync=typeof window.notebookAPI==='function';", self.html)
        self.assertIn('async function publishMediumData(){\nif(!localNotebookSync)', self.html)
        self.assertIn('async function synchronizeDevices(push=false,manual=false){\n if(!localNotebookSync)', self.html)
        self.assertIn("root.querySelector('#cloud-device-sync').textContent='Nuvem desativada';", self.html)

    def test_medium_agenda_is_saved_on_device_without_remote_upsert(self):
        self.assertIn("const personalAgendaStorageKey='gestao-agenda-pessoal-'+user.id;", self.html)
        self.assertIn('if(!localNotebookSync){\n const stored=readPersonalAgenda();', self.html)
        self.assertIn('await window.GESTAO_STORAGE_FLUSH?.();', self.html)

    def test_radiesthesia_disables_cloud_transport_but_preserves_local_records(self):
        self.assertIn('function queueCloud(record){if(!window.notebookAPI)return;', self.html)
        self.assertIn('async function syncCloud(){\n if(!window.notebookAPI)', self.html)
        self.assertIn("radioSyncButton.textContent='Nuvem desativada';", self.html)


if __name__ == '__main__':
    unittest.main()
