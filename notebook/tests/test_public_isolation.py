"""Regressões de isolamento do acesso público. Executar: python -m unittest discover -s notebook/tests -v"""
import unittest
from types import SimpleNamespace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Handler, ApiError


class PublicIsolationTests(unittest.TestCase):
    def handler(self, public):
        h = Handler.__new__(Handler)
        h.server = SimpleNamespace(public_listener=public, local_hosts={'localhost', '127.0.0.1'}, allowed_hosts={'cristiano.tail07d7c9.ts.net'} if public else {'localhost'})
        h.headers = {'Host': 'localhost' if public else 'cristiano.tail07d7c9.ts.net'}
        return h

    def test_public_listener_is_public_even_with_local_host(self):
        self.assertTrue(self.handler(True).public_request())

    def test_local_listener_stays_local_even_with_public_host(self):
        self.assertFalse(self.handler(False).public_request())

    def test_public_listener_rejects_unapproved_host(self):
        with self.assertRaises(ApiError):
            self.handler(True).check_host()

    def test_local_listener_rejects_public_host(self):
        from notebook.server import ApiError
        with self.assertRaises(ApiError):
            self.handler(False).check_host()


if __name__ == '__main__':
    unittest.main()
