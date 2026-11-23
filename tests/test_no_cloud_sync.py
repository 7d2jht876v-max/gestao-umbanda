"""Regressions for the hosted cloud-only application."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CloudStorageTests(unittest.TestCase):
    def test_hosted_storage_and_concurrent_updates(self):
        subprocess.run(['node', '-e', """
const {readFileSync} = require('node:fs');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const html = readFileSync('index.html', 'utf8');
const scripts = [...html.matchAll(/<script\\b[^>]*>([\\s\\S]*?)<\\/script>/gi)].map(match => match[1]);
for (const script of scripts) new vm.Script(script);
const context = vm.createContext({
  window: {}, location: {hostname: '7d2jht876v-max.github.io'},
  document: {createElement: () => ({}), head: {append() {}}, documentElement: {dataset: {}}}
});
const storageScript = scripts.find(script => script.includes('window.GESTAO_STORAGE_READY='));
vm.runInContext(storageScript.slice(storageScript.indexOf('window.GESTAO_STORAGE_READY=')), context);
(async () => {
  const store = await context.window.GESTAO_STORAGE_READY;
  store.setItem('gestao-umbanda-v1', 'example');
  assert.equal(store.getItem('gestao-umbanda-v1'), 'example');
  store.removeItem('gestao-umbanda-v1');
  assert.equal(store.getItem('gestao-umbanda-v1'), null);
  vm.runInContext(html.slice(html.indexOf('function syncCanonical('),html.indexOf('function createSyncDelta(')), context);
  const doc = value => ({section:[{id:'same', attachment:value}]});
  const original = doc('old'), modified = doc('new');
  const saved = context.mergeDeviceData(original, modified, original).data;
  assert.equal(saved.section[0].attachment, 'new');
  assert.equal(context.mergeDeviceData(saved, modified, original).data.section.length, 1);
  assert.throws(() => context.mergeDeviceData(saved, doc('other'), original), /simultânea/);
})().catch(error => {console.error(error); process.exitCode=1;});
"""], cwd=ROOT, check=True)
