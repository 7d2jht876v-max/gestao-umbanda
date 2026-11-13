import { mkdir, copyFile, rm } from 'node:fs/promises';
await rm('www', {recursive:true,force:true});
await mkdir('www/icons',{recursive:true});
for (const path of ['index.html','baralho-cigano.html','supabase-config.js','install.js','manifest.webmanifest','sw.js','icons/icon-192.png','icons/icon-512.png','icons/apple-touch-icon.png']) await copyFile(path, `www/${path}`);
console.log('Arquivos do aplicativo preparados em www/. Nenhum backup pessoal foi incluído.');
