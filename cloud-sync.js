/* Gestão Umbanda: login e sincronização explícita; exige executar supabase-setup.sql.
   Dados locais existentes nunca são enviados automaticamente. */
(()=>{'use strict';
const cfg=window.GESTAO_UMBANDA_SUPABASE;
const supa=window.supabase;
if(!cfg||!cfg.publishableKey||!supa){return;}
const client=supa.createClient(cfg.url,cfg.publishableKey);
const root=document.createElement('div');
root.id='cloud-access';
root.style.cssText='max-width:720px;margin:14px auto;padding:14px;background:#fff;border:2px solid #b8d2c8;border-radius:12px;font:15px system-ui';
root.innerHTML='<h2 style="margin:0 0 8px">☁️ Acesso seguro</h2><p id="cloud-status">Verificando acesso…</p><div id="cloud-controls"></div>';
document.querySelector('main').prepend(root);
const status=root.querySelector('#cloud-status'),controls=root.querySelector('#cloud-controls');
const localKey='gestao-umbanda-v1';
let role=null;
let recovering=window.location.hash.includes('type=recovery')||window.location.search.includes('type=recovery');
client.auth.onAuthStateChange((event)=>{if(event==='PASSWORD_RECOVERY'){recovering=true;setTimeout(showRecoveryForm,0)}});
function msg(s){status.textContent=s}
function errorText(e){return e?.message||'Erro desconhecido'}
function showRecoveryForm(){msg('Crie uma nova senha para sua conta.');controls.innerHTML='<form id="cloud-recover"><label>Nova senha (mínimo 8 caracteres)</label><input id="cloud-newpass" type="password" autocomplete="new-password" minlength="8" required><label>Confirmar nova senha</label><input id="cloud-confirmpass" type="password" autocomplete="new-password" minlength="8" required><button style="margin-top:12px">Salvar nova senha</button></form>';controls.querySelector('form').onsubmit=async e=>{e.preventDefault();const p=root.querySelector('#cloud-newpass').value,c=root.querySelector('#cloud-confirmpass').value;if(p!==c){msg('As senhas não coincidem.');return;}msg('Atualizando senha…');const {error}=await client.auth.updateUser({password:p});if(error){msg('Não foi possível alterar: '+errorText(error));return;}recovering=false;history.replaceState(null,'',location.pathname);msg('Senha alterada com sucesso.');await refresh()}}
function formLogin(){controls.innerHTML='<form id="cloud-login"><label>E-mail</label><input type="email" id="cloud-email" autocomplete="username" required><label>Senha</label><input type="password" id="cloud-password" autocomplete="current-password" required><button style="margin-top:12px">Entrar</button><button id="cloud-forgot" type="button" style="margin:12px 0 0 8px;background:#526b63">Esqueci minha senha</button></form>';controls.querySelector('#cloud-forgot').onclick=async()=>{const email=root.querySelector('#cloud-email').value.trim();if(!email){msg('Informe seu e-mail acima para receber a recuperação.');return;}msg('Solicitando e-mail…');const {error}=await client.auth.resetPasswordForEmail(email,{redirectTo:location.origin+location.pathname});msg(error?'Falha ao solicitar recuperação: '+errorText(error):'Se o e-mail estiver cadastrado, você receberá um link para criar nova senha. Verifique também o spam.')};controls.querySelector('form').onsubmit=async e=>{e.preventDefault();msg('Entrando…');const email=root.querySelector('#cloud-email').value,password=root.querySelector('#cloud-password').value;const {error}=await client.auth.signInWithPassword({email,password});if(error)msg('Não foi possível entrar: '+errorText(error));else await refresh()};}
async function refresh(){if(recovering){showRecoveryForm();return;}const {data:{user},error}=await client.auth.getUser();if(error||!user){role=null;msg('Entre com seu e-mail e senha cadastrados no Supabase. Os dados atuais permanecem no iPhone.');formLogin();return;}
const result=await client.from('perfis').select('perfil').eq('id',user.id).single();if(result.error){role=null;msg('Login realizado, mas o perfil não foi encontrado: '+errorText(result.error));controls.innerHTML='<button id="cloud-out">Sair</button>';root.querySelector('#cloud-out').onclick=logout;return;}
role=result.data.perfil;msg('Conectado: '+user.email+' • '+(role==='admin'?'Administrador':'Médium')+'. Sincronização manual: confira os dados antes de substituir.');
controls.innerHTML='<div style="display:flex;gap:8px;flex-wrap:wrap"><button id="cloud-load">Carregar dados da nuvem</button>'+(role==='admin'?'<button id="cloud-save">Enviar dados para nuvem</button>':'')+'<button id="cloud-out" style="background:#666">Sair</button></div>';
root.querySelector('#cloud-out').onclick=logout;
root.querySelector('#cloud-load').onclick=load;
if(role==='admin')root.querySelector('#cloud-save').onclick=upload;
}
async function logout(){await client.auth.signOut();await refresh()}
async function load(){msg('Consultando nuvem…');const {data:row,error}=await client.from('gestao_dados').select('conteudo,atualizado_em').eq('id','templo').maybeSingle();if(error){msg('Falha ao consultar. Execute o SQL de configuração: '+errorText(error));return;}if(!row){msg('Ainda não há dados na nuvem. O administrador deve enviar um backup.');return;}if(!confirm('Substituir os dados deste aparelho pelos dados da nuvem? Faça um backup local antes.')){await refresh();return;}localStorage.setItem(localKey,JSON.stringify(row.conteudo));location.reload()}
async function upload(){if(role!=='admin')return;const raw=localStorage.getItem(localKey);if(!raw){msg('Não há dados locais para enviar.');return;}let content;try{content=JSON.parse(raw)}catch{msg('Dados locais inválidos.');return;}if(!confirm('Enviar os dados deste aparelho para a nuvem? Isto substituirá o conjunto compartilhado para todos os médiuns.'))return;msg('Salvando na nuvem…');const {error}=await client.from('gestao_dados').upsert({id:'templo',conteudo:content,atualizado_em:new Date().toISOString()},{onConflict:'id'});if(error){msg('Não foi possível salvar. Verifique se executou o SQL: '+errorText(error));return;}msg('Dados enviados para a nuvem com sucesso. Para atualizar outros aparelhos, use Carregar dados da nuvem.')}
refresh();
})();
