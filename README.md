# IPTV — catálogo personalizado

Playlist automática a partir do projeto público [IPTV-org](https://github.com/iptv-org/iptv).

**Link para Sparkle TV (GitHub Pages, após ativação):** https://adailtononline-cmd.github.io/iptv/playlist.m3u

**Link direto do arquivo hospedado no GitHub (assim que gerado):** https://raw.githubusercontent.com/adailtononline-cmd/iptv/main/playlist.m3u

A rotina está em [GitHub Actions](../../actions). O gerador busca canais e logos oficiais, organiza por país/categoria, remove conteúdo NSFW e deduplica por identificador. A verificação semanal é HTTP e não garante reprodução nem ausência de restrições geográficas. O relatório de atualização fica em report.json. A lista só deve ser usada após confirmar a existência do arquivo playlist.m3u.
