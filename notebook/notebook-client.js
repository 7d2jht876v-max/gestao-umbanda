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
