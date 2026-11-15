# IPTV — catálogo personalizado

Playlist gerada automaticamente a partir do catálogo público [IPTV-org](https://github.com/iptv-org/iptv).

**URL M3U direta para aplicativos IPTV:**
https://raw.githubusercontent.com/adailtononline-cmd/iptv/main/playlist.m3u

**GitHub Pages (somente se o Pages estiver habilitado e publicado):**
https://adailtononline-cmd.github.io/iptv/playlist.m3u

A rotina de atualização está em [GitHub Actions](../../actions), no workflow `update.yml`. O gerador `build.py` seleciona os países configurados, organiza os canais por país e categoria, preenche os metadados disponíveis, exclui conteúdo NSFW sinalizado na origem e escolhe uma alternativa por país/nome, priorizando resultados HTTP positivos e qualidade declarada.

A execução atual do workflow testa os streams por HTTP/HTTPS e verifica a estrutura de playlists HLS quando a URL termina em `.m3u8`. As respostas 401/403 e falhas de rede podem decorrer de autenticação, restrições geográficas ou problemas transitórios e não comprovam que o canal esteja morto. O teste HTTP/HLS **não comprova reprodução de áudio e vídeo no player**.

Antes de publicar, `validate.py` confere a integridade de `playlist.m3u`, `channels.json` e `report.json`. Consulte `report.json` e `stream_status.json` para os números e diagnósticos da última execução. O endereço GitHub Pages e qualquer domínio personalizado exigem verificação independente de disponibilidade; não há domínio personalizado configurado neste repositório por um arquivo `CNAME`.
