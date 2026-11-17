import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const start = html.indexOf('async function exportForNotebook(){');
const end = html.indexOf('\nfunction toggleNotebookConnection(){', start);
assert.ok(start > 0 && end > start, 'exporter is present');

const saved = {
  'gestao-umbanda-v1': JSON.stringify({ '👥 Médiuns': [{ id: '1', nome: 'Registro local' }] }),
  'gestao-umbanda-radiestesia-fichas-v1': JSON.stringify([{ id: 'ficha-1' }]),
  'gestao-umbanda-v1-device-sync-base': JSON.stringify({ shouldNotExport: true }),
};
let exportedBlob = null;
let flushed = false;
const context = {
  localKey: 'gestao-umbanda-v1',
  localStorage: { keys: () => Object.keys(saved), getItem: key => saved[key] ?? null },
  window: { GESTAO_UNSAVED_FORM: false, GESTAO_RADIO_DIRTY: false, GESTAO_STORAGE_FLUSH: async () => { flushed = true; } },
  URL: { createObjectURL: blob => { exportedBlob = blob; return 'blob:test'; }, revokeObjectURL: () => {} },
  document: { body: { append: () => {} }, createElement: () => ({ click: () => {}, remove: () => {} }) },
  Blob,
  setTimeout: () => {},
};
vm.createContext(context);
vm.runInContext(html.slice(start, end), context);
await vm.runInContext('exportForNotebook()', context);
assert.ok(flushed, 'pending local writes were flushed');
const backup = JSON.parse(await exportedBlob.text());
assert.equal(backup.format, 'gestao-transferencia-notebook');
assert.equal(JSON.parse(backup.storage['gestao-umbanda-v1'])['👥 Médiuns'][0].nome, 'Registro local');
assert.ok(backup.storage['gestao-umbanda-radiestesia-fichas-v1']);
assert.equal(backup.storage['gestao-umbanda-v1-device-sync-base'], undefined);

context.window.GESTAO_UNSAVED_FORM = true;
await assert.rejects(vm.runInContext('exportForNotebook()', context), /Salve primeiro/);
console.log('Exportacao segura para o notebook: OK');
