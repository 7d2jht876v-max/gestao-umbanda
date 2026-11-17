# Gestão Umbanda — atualização 217

## Instalação pela tela inicial
Abra https://7d2jht876v-max.github.io/gestao-umbanda/ no navegador do aparelho. No Android, use Instalar aplicativo quando oferecido. No iPhone/iPad, use Safari → Compartilhar → Adicionar à Tela de Início → Abrir como App da Web.

Para atualizar o aplicativo existente para a versão 217, use `atualizar-217.html` no mesmo endereço. Não desinstale o aplicativo anterior nem limpe os dados do navegador antes de exportar seus backups.

O aplicativo mantém as mesmas chaves de armazenamento da versão existente. Não apaga cadastros ao atualizar. Um navegador, perfil ou aplicativo nativo diferente tem armazenamento separado: exporte o backup antes da mudança e importe no destino. As fichas de radiestesia também possuem exportação própria; preserve esse arquivo separadamente. A instalação não restaura backups automaticamente nem sincroniza aparelhos por si só.

O cache offline contém apenas arquivos públicos do aplicativo. Na versão web 217, o envio de dados e a sincronização com Supabase permanecem desativados; o login antigo ainda utiliza Supabase e necessita de internet. O notebook usa seu próprio servidor HTTPS e banco local. Para sincronizar o iPhone com o notebook, use o endereço HTTPS do notebook na mesma rede Wi-Fi, preservando antes os registros que existam somente no iPhone. Videoaulas e outros recursos externos podem necessitar de internet.

## Botão Sincronizar notebook e iPhone

Na versão aberta pelo GitHub Pages, o botão orienta a transferência local: **Baixar backup completo deste aparelho** salva os cadastros e fichas locais em JSON, sem enviar nada para a nuvem. Depois, **Abrir servidor e importar backup** abre a administração HTTPS do notebook, onde a importação preserva diferenças como cópias. É necessário fazer esse processo para cada aparelho que tenha registros exclusivos.

Na versão aberta diretamente pelo endereço HTTPS do notebook, o mesmo botão executa a sincronização com o banco local. O notebook precisa estar ligado, os aparelhos na mesma Wi-Fi e a conta autorizada. Endereços GitHub Pages e HTTPS do notebook têm armazenamentos separados; abrir um não transfere automaticamente o conteúdo do outro.

## Projeto nativo Android e iOS
Esta é a base de empacotamento Capacitor, ainda sem binários validados para distribuição. Em ambiente com Node 22 e os SDKs oficiais:

```
npm install
npm run build
npx cap add android
npx cap add ios
npx cap sync
npx cap open android
npx cap open ios
```

iOS exige macOS com Xcode. Android exige Android Studio/SDK e Java compatível com Capacitor 7. Para futuras alterações use `npm run android` ou `npm run ios` após gerar as plataformas.

Antes de distribuir: implementar e validar exportação/importação de arquivos na WebView nativa, conferir login e permissões, backup/restauração incluindo radiestesia, anexos, migração dos dados, rotação, teclado e uso offline em aparelhos reais. O download por Blob do navegador não é garantia de funcionamento na WebView; não distribuir como final sem essa validação.

Play Store/App Store exigem contas do responsável, assinatura e processo de revisão. Nenhum APK/IPA assinado ou publicação nas lojas foi produzido nesta atualização. Não incluir dados reais de médiuns ou o backup pessoal nos pacotes.
