# Gestão Umbanda 217 — preparação para acesso externo

**Estado:** proposta de segurança, NÃO instalada no notebook e NÃO autorizada para ativar Funnel.

## Alterações na proposta
- Limite de tentativas de login por e-mail, além de endereço IP.
- Validação de Origin para POSTs JSON.
- Bloqueio de configuração inicial fora de localhost.
- Restrição de rotas administrativas no hostname externo.
- Rejeição de login e sessão de administrador no hostname externo.
- Hostname público configurável por GESTAO_PUBLIC_HOST, limitado a .ts.net.

## Pendências obrigatórias antes de publicar
1. Confirmar que o proxy Funnel preserva o Host original em todas as rotas; se reescrever Host para localhost, os bloqueios por hostname podem ser contornados. Nesse caso, usar um proxy separado que autentique a origem e restrinja rotas, ou separar servidores/portas de forma verificável.
2. Substituir a senha padrão compartilhada por credenciais individuais; preservar contas e dados, mas não publicar contas com a mesma senha.
3. Verificar que a interface do cliente envia Origin nas chamadas POST; testar login, consulta individual, agenda, comunicados e sincronização.
4. Fazer cópia consistente de dados/templo.sqlite3 com a API de backup SQLite e preservar uploads e certificados.
5. Revisar políticas de acesso do portal por médium e proteger as rotas administrativas em profundidade.
6. Instalar o código revisado no notebook e reiniciar somente em janela controlada, com possibilidade de retorno à versão anterior.
7. Somente depois habilitar Funnel e confirmar que acesso administrativo externo é negado e acesso de médium autorizado funciona.

Não copiar a pasta dados para o GitHub. Não publicar senhas ou certificados privados.