"""The 217 shell update must keep the existing storage and notebook mode."""

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'notebook'))
from server import local_index


class Release217Tests(unittest.TestCase):
    def test_version_and_local_notebook_mode(self):
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('Gestão Umbanda — atualização 217', html)
        self.assertIn("url.searchParams.set('v','217')", html)
        self.assertIn("const localNotebookSync=typeof window.notebookAPI==='function';", html)
        notebook = local_index(html)
        self.assertIn('Gestão Umbanda — Notebook 1.0', notebook)
        self.assertIn('/notebook-client.js', notebook)
        self.assertNotIn('supabase.min.js', notebook)

    def test_existing_pwa_identity_is_unchanged(self):
        manifest = json.loads((ROOT / 'manifest.webmanifest').read_text(encoding='utf-8'))
        self.assertEqual(manifest['id'], './')
        self.assertEqual(manifest['scope'], './')
        self.assertEqual(manifest['start_url'], './?v=217')

    def test_update_page_does_not_clear_personal_data(self):
        updater = (ROOT / 'atualizar-217.html').read_text(encoding='utf-8')
        self.assertIn("url.searchParams.set('v','217')", updater)
        self.assertIn('Gestão Umbanda — atualização 217', updater)
        for destructive in ('localStorage.clear(', 'indexedDB.deleteDatabase(', 'caches.delete('):
            self.assertNotIn(destructive, updater)

    def test_new_service_worker_is_published(self):
        worker = (ROOT / 'sw.js').read_text(encoding='utf-8')
        install = (ROOT / 'install.js').read_text(encoding='utf-8')
        workflow = (ROOT / '.github/workflows/jekyll-gh-pages.yml').read_text(encoding='utf-8')
        self.assertIn("const CACHE = 'gestao-shell-217-notebook-iphone';", worker)
        self.assertIn('./sw.js?v=217-notebook-iphone', install)
        self.assertIn('atualizar-217.html _site/', workflow)


if __name__ == '__main__':
    unittest.main()
