/* Compatibility adapter: same screens, local HTTPS API, HttpOnly sessions. */
(()=>{'use strict';
window.GESTAO_UMBANDA_SUPABASE={url:location.origin,publishableKey:'notebook-local'};
const unsupported=async()=>({data:null,error:{message:'Solicite ao administrador a criação ou recuperação do acesso no servidor do notebook.'}});
window.notebookAPI=async(path,body,signal)=>{
 try{
  const response=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'same-origin',cache:'no-store',headers:body===undefined?{}:{'Content-Type':'application/json','X-Notebook':'1'},body:body===undefined?undefined:JSON.stringify(body),signal:signal||AbortSignal.timeout(30000)});
  const result=await response.json();
  if(!response.ok&&!result.error)result.error={message:'Servidor do notebook indisponível.'};
  return result;
 }catch(error){return {data:null,error:{message:'Não foi possível conectar ao notebook. Confira se está ligado e na mesma rede Wi-Fi.',code:'NETWORK'}};}
};
class Query{
 constructor(table){this.args={table,action:'select',columns:'*',filters:{}};}
 select(columns='*'){this.args.columns=columns;return this;}
 eq(key,value){this.args.filters[key]=value;return this;}
 limit(value){this.args.limit=value;return this;}
 upsert(values){this.args.action='upsert';this.args.values=values;return this;}
 single(){this.args.single='one';return this;}
 maybeSingle(){this.args.single='maybe';return this;}
 abortSignal(signal){this.signal=signal;return this;}
 then(resolve,reject){return notebookAPI('/api/table',this.args,this.signal).then(resolve,reject);}
}
class Rpc{
 constructor(name,args){this.body={name,args};}
 abortSignal(signal){this.signal=signal;return this;}
 then(resolve,reject){return notebookAPI('/api/rpc',this.body,this.signal).then(resolve,reject);}
}
const auth={
 async getSession(){return notebookAPI('/api/session');},
 async getUser(){const result=await this.getSession();return {data:{user:result.data?.session?.user||null},error:result.error};},
 async signInWithPassword(args){return notebookAPI('/api/login',args);},
 async signOut(){return notebookAPI('/api/logout',{});},
 onAuthStateChange(){return {data:{subscription:{unsubscribe(){}}}};},
 signUp:unsupported,resetPasswordForEmail:unsupported,updateUser:unsupported,exchangeCodeForSession:unsupported,verifyOtp:unsupported
};
window.supabase={createClient:()=>({auth,from:table=>new Query(table),rpc:(name,args={})=>new Rpc(name,args),functions:{invoke:async(name)=>{
 if(name!=='provisionar-mediuns')return unsupported();
 const result=await notebookAPI('/api/provision',{});
 if(result.data?.credentials?.length){
  const dialog=document.createElement('dialog');
  const title=document.createElement('h2');title.textContent='Acessos criados — anote as senhas';
  const note=document.createElement('p');note.textContent='Estas senhas exclusivas aparecem somente agora. Entregue cada uma apenas ao respectivo médium. Contas existentes foram mantidas.';
  const text=document.createElement('pre');text.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere';text.textContent=result.data.credentials.map(x=>x.email+'\nSenha: '+x.password).join('\n\n');
  const close=document.createElement('button');close.textContent='Anotei, fechar';close.onclick=()=>{dialog.close();dialog.remove();};
  dialog.append(title,note,text,close);document.body.append(dialog);dialog.showModal();
 }
 return result;
}}})};
})();

/* iPhone installation and local server identity. Uses the existing sync engine. */
(()=>{
 const mount=()=>{
  const style=document.createElement('style');
  style.textContent=`
   @media(max-width:600px){
    html,body{max-width:100%;overflow-x:hidden}
    input,select,textarea{font-size:16px!important;max-width:100%;box-sizing:border-box}
    button{min-height:44px}
    header{height:auto!important;min-height:0}
    header p,header h1{position:static!important;white-space:normal!important}
    dialog{max-width:calc(100vw - 32px);box-sizing:border-box}
   }
   #notebook-phone{margin:12px;padding:16px;border:1px solid #cbb9a7;border-radius:16px;background:#fff9f1;color:#402b20;font:16px system-ui;overflow-wrap:anywhere}
   #notebook-phone summary{cursor:pointer;font-weight:700}
   #notebook-phone button{background:#70452d;color:white;border:0;border-radius:10px;padding:12px;margin:8px 8px 0 0}
  `;
  document.head.append(style);
  const panel=document.createElement('details');panel.id='notebook-phone';
  const heading=document.createElement('summary');heading.textContent='iPhone e notebook — Templo Xangô';
  const info=document.createElement('p');info.textContent='Os dois aparelhos usam o mesmo servidor do templo. Mantenha o notebook ligado e na mesma rede Wi-Fi. A sincronização automática funciona enquanto o aplicativo está aberto; ao voltar para ele, aguarde a confirmação na área Acesso seguro.';
  const url=document.createElement('p');url.textContent='Servidor deste aplicativo: '+location.origin;
  const install=document.createElement('p');install.textContent='No iPhone: abra este endereço no Safari, entre com sua conta e toque em Compartilhar → Adicionar à Tela de Início → Adicionar. Abra o novo ícone para continuar. Se houver aviso de certificado, confira o endereço com o exibido no notebook.';
  const copy=document.createElement('button');copy.type='button';copy.textContent='Copiar endereço para o iPhone';
  const result=document.createElement('p');result.setAttribute('role','status');
  copy.onclick=async()=>{try{await navigator.clipboard.writeText(location.origin+'/');result.textContent='Endereço copiado.';}catch{result.textContent='Copie o endereço: '+location.origin+'/';}};
  const test=document.createElement('button');test.type='button';test.textContent='Testar servidor';
  test.onclick=async()=>{test.disabled=true;result.textContent='Verificando…';const r=await notebookAPI('/api/status');result.textContent=r.error?r.error.message:'Servidor do templo respondeu. Confira também a confirmação de sincronização na área Acesso seguro.';test.disabled=false;};
  panel.append(heading,info,url,install,copy,test,result);
  const header=document.querySelector('header');if(header)header.after(panel);else document.body.prepend(panel);
 };
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
