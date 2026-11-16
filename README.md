# IPTV Mundi

Lista mundial de canais, testada. Os dados vêm de `dados/canais.json` (gerado pelo projeto Canais TV); `exportar.py` monta `playlist.m3u`, o guia `epg.xml.gz` e os logos em `logos/`.

- Grupos por país: Brasil primeiro, os demais em ordem alfabética, "Sem país identificado" no fim.
- Cada canal tem tvg-id (quando existe), tvg-name, logo, país, idioma e categoria.
- Canais que só tocaram em algumas regiões levam o aviso "[testado só em: ...]".
- Para a versão antiga: tag `antes-da-reforma`.
