#!/usr/bin/env python3
"""Gera playlist.m3u, epg.xml e logos/ a partir de dados/canais.json (lista mundial testada)."""
import concurrent.futures, gzip, hashlib, io, json, os, re, sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone

UA = "Mozilla/5.0"
BASE_URL = (os.environ.get("BASE_URL") or "https://raw.githubusercontent.com/adailtononline-cmd/iptv/main/").rstrip("/") + "/"
RAW_BASE = BASE_URL
EXCLUIR = set()
PRIORIDADE = ["BR"]
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
PLUTO_URL = "https://i.mjh.nz/PlutoTV/all.xml"
_PLUTO = {}
EPG_SOURCES = [
    "https://i.mjh.nz/PlutoTV/all.xml",
    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_SPORTS1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CA2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AU1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_NZ1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_ES1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR2.xml.gz",
] + ["https://epgshare01.online/epgshare01/epg_ripper_%s1.xml.gz" % c for c in "IT FR DE MX AR CL CO PE PT TR NL PL RO HU CZ GR IN RU".split()]
EPG_DAYS = 4

def pluto_bytes():
    """Guia do Pluto TV (i.mjh.nz): baixado uma vez, casa pelo ID do canal que está no link da playlist."""
    if "data" not in _PLUTO:
        try:
            req = urllib.request.Request(PLUTO_URL, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as response:
                _PLUTO["data"] = response.read(120_000_000)
        except Exception:
            _PLUTO["data"] = b""
    return _PLUTO["data"]

def pluto_id(url):
    m = re.match(r"https://jmp2\.uk/plu-([0-9a-f]+)\.m3u8", url or "")
    return m.group(1) if m else ""

def plain_title(title):
    return re.sub(r"\s*(\([^)]*\)|\[[^\]]*\]|[ⒼⓈⓎ])", "", title).strip()

def placeholder_logo(title, slug):
    """Logo gerado com o nome do canal, para o canal nunca ficar sem identificação."""
    from PIL import Image, ImageDraw, ImageFont
    digest = int(hashlib.md5(slug.encode()).hexdigest(), 16)
    palette = [(24, 54, 98), (92, 38, 110), (21, 94, 84), (122, 45, 45), (60, 70, 20), (30, 30, 30), (16, 76, 120), (110, 70, 15)]
    bg = palette[digest % len(palette)]
    size = 512
    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    name = plain_title(title) or title
    font_path = next((f for f in FONTS if os.path.exists(f)), None)
    for px in (84, 72, 62, 52, 44, 36):
        font = ImageFont.truetype(font_path, px) if font_path else ImageFont.load_default()
        lines, line = [], ""
        for word in name.split():
            trial = (line + " " + word).strip()
            if draw.textlength(trial, font=font) <= size - 60:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        height = len(lines) * (px + 10)
        if height <= size - 80 and all(draw.textlength(l, font=font) <= size - 40 for l in lines):
            break
    y = (size - len(lines) * (px + 10)) // 2
    for l in lines:
        w = draw.textlength(l, font=font)
        draw.text(((size - w) / 2, y), l, font=font, fill=(255, 255, 255))
        y += px + 10
    os.makedirs("logos", exist_ok=True)
    img.save("logos/" + slug + ".png", optimize=True)
    return RAW_BASE + "logos/" + slug + ".png"

def norm(s):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\([^)]*\)|\[[^]]*\]", "", (s or "").lower()))

def title_of(ext):
    """Título do canal: o texto depois da primeira vírgula FORA de aspas (atributos como http-user-agent têm vírgula)."""
    inside = False
    for i, ch in enumerate(ext):
        if ch == '"':
            inside = not inside
        elif ch == "," and not inside:
            return ext[i + 1:].strip()
    return ext.rsplit(",", 1)[-1].strip()

def attr(ext, name):
    m = re.search(r'(?<![\w-])' + re.escape(name) + r'="([^"]*)"', ext)
    return m.group(1).strip() if m else ""

def build_epg(results, now):
    """Une os guias de várias fontes e guarda só canais da playlist e os próximos EPG_DAYS dias."""
    index = {}
    for ext, link, _ in results:
        pid = attr(ext, "tvg-id")
        if not pid:
            continue
        if pluto_id(link):
            index.setdefault(pluto_id(link), set()).add(pid)
        for key in {pid, pid.split("@")[0], norm(title_of(ext)), norm(pid.split("@")[0].split(".")[0])}:
            if key and (key == pid or key == pid.split("@")[0] or len(key) >= 4):
                index.setdefault(key, set()).add(pid)
    matched = set()
    out_channels, out_programmes = [], []
    per_source = {}
    lo, hi = now - 24 * 3600, now + EPG_DAYS * 24 * 3600
    for url in EPG_SOURCES:
        try:
            if url == PLUTO_URL:
                data = pluto_bytes()
            else:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=90) as response:
                    data = response.read(80_000_000)
            stream = io.BytesIO(gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data)
            mapping = {}
            count = 0
            for event, el in ET.iterparse(stream, events=("end",)):
                if el.tag == "channel":
                    gid = el.get("id") or ""
                    names = [norm(n.text) for n in el.findall("display-name")]
                    pids = set(index.get(gid, set())) | set(index.get(gid.split("@")[0], set()))
                    if not pids:
                        for n in names:
                            options = index.get(n, set()) if len(n) >= 4 else set()
                            if options:
                                pids |= options
                    pids -= matched
                    if pids:
                        mapping[gid] = sorted(pids)
                        matched |= pids
                        for pid in sorted(pids):
                            node = ET.fromstring(ET.tostring(el))
                            node.set("id", pid)
                            out_channels.append(node)
                    el.clear()
                elif el.tag == "programme":
                    gid = el.get("channel") or ""
                    if gid in mapping:
                        try:
                            start = datetime.strptime((el.get("start") or "")[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp()
                            stop = datetime.strptime((el.get("stop") or el.get("start") or "")[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp()
                        except ValueError:
                            start = stop = now
                        if start <= hi and stop >= lo:
                            for pid in mapping[gid]:
                                node = ET.fromstring(ET.tostring(el))
                                node.set("channel", pid)
                                out_programmes.append(node)
                                count += 1
                    el.clear()
            per_source[url.rsplit("/", 1)[-1]] = {"channels": len(mapping), "programmes": count}
        except Exception as exc:
            per_source[url.rsplit("/", 1)[-1]] = {"error": str(exc)[:120]}
    return matched, out_channels, out_programmes, per_source


def pluto_icons():
    text = pluto_bytes().decode("utf-8", "ignore")
    return {m.group(1): m.group(2) for m in re.finditer(r'<channel id="([0-9a-f]+)">.*?<icon src="([^"]+)"', text, re.S)}


def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except Exception:
        return []


def _encolher(slug):
    from PIL import Image
    img = Image.open("logos/" + slug + ".png"); img.thumbnail((160, 160))
    img.save("logos/" + slug + ".png", optimize=True)


def baixar_logo(job):
    slug, urls = job
    if os.path.exists("logos/" + slug + ".png"):
        return slug, True
    from PIL import Image
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=12) as r:
                raw = r.read(3_000_000)
            if raw.lstrip()[:5].lower() in (b"<?xml", b"<svg ") or b"<svg" in raw[:300].lower():
                continue                      # SVG: o Pillow não abre, tenta a próxima origem
            img = Image.open(io.BytesIO(raw)); img.load()
            img = img.convert("RGBA"); img.thumbnail((160, 160))
            img.save("logos/" + slug + ".png", optimize=True)
            return slug, True
        except Exception:
            continue
    return slug, False


def tvlogos_index():
    """Logos do projeto tv-logo/tv-logos, por pasta de país + nome normalizado (igualdade exata)."""
    data = fetch_json("https://api.github.com/repos/tv-logo/tv-logos/git/trees/main?recursive=1")
    index = {}
    for node in (data.get("tree", []) if isinstance(data, dict) else []):
        m = re.match(r"countries/([^/]+)/([^/]+)\.png$", node.get("path", ""))
        if not m:
            continue
        folder, stem = m.groups()
        stem = re.sub(r"-(us|ca|au|nz|br|uk|gb|[a-z]{2})$", "", stem)
        stem = re.sub(r"-(hd|sd|4k)$", "", stem)
        index.setdefault((folder, norm(stem.replace("-", " "))), "https://raw.githubusercontent.com/tv-logo/tv-logos/main/" + node["path"].replace(" ", "%20"))
    return index


def main():
    now = datetime.now(timezone.utc).timestamp()
    canais = [c for c in json.load(open("dados/canais.json", encoding="utf-8")) if c.get("p") not in EXCLUIR]
    nomes_pais = {c["pn"] for c in canais if c.get("pn")}
    por_cod = {c["p"]: c["pn"] for c in canais if c.get("p") and c.get("pn")}
    for c in canais:
        if c.get("p") in ("", "??", None):
            c["p"], c["pn"] = "", ""
        elif not c.get("pn"):
            c["pn"] = por_cod.get(c["p"], c["p"])
        if c.get("c") in nomes_pais:
            c["c"] = ""
    os.makedirs("logos", exist_ok=True)

    # tvg-id (iptv-org) pelo endereço do fluxo: liga o canal ao guia de programação
    ids = {}
    for s in fetch_json("https://iptv-org.github.io/api/streams.json"):
        if s.get("channel") and s.get("url"):
            ids.setdefault(s["url"], s["channel"] + ("@" + s["feed"] if s.get("feed") else ""))

    for c in canais:
        c["slug"] = hashlib.md5(((c.get("p") or "") + "|" + c["n"]).encode()).hexdigest()[:12]
    # quadros gerados em rodadas anteriores são refeitos: a cada rodada tenta de novo achar o logo de verdade
    if os.path.exists("logos_geradas.json"):
        for sl in json.load(open("logos_geradas.json")):
            if os.path.exists("logos/" + sl + ".png"):
                os.remove("logos/" + sl + ".png")
    catalogo = {}
    for lg in fetch_json("https://iptv-org.github.io/api/logos.json"):
        if lg.get("channel") and lg.get("url", "").startswith("https://"):
            catalogo.setdefault(lg["channel"], []).append((0 if lg.get("in_use") else 1, lg["url"]))
    tvl = tvlogos_index()
    icones = pluto_icons()
    jobs = {}
    for c in canais:
        origens = [c["l"]] if c.get("l") else []
        base = ids.get(c["u"], "").split("@")[0]
        origens += [u for _, u in sorted(catalogo.get(base, []))]
        pid = pluto_id(c["u"])
        if icones.get(pid): origens.append(icones[pid])
        u = tvl.get((re.sub(r"[^a-z0-9]+", "-", (c.get("pn") or "").lower()).strip("-"), norm(plain_title(c["n"]))))
        if u: origens.append(u)
        if origens: jobs[c["slug"]] = list(dict.fromkeys(origens))
    with concurrent.futures.ThreadPoolExecutor(32) as pool:
        ok = dict(pool.map(baixar_logo, jobs.items()))
    sem_logo, geradas = 0, []
    for c in canais:
        if ok.get(c["slug"]) or os.path.exists("logos/" + c["slug"] + ".png") and c.get("l"):
            c["logo"] = BASE_URL + "logos/" + c["slug"] + ".png"
        else:
            placeholder_logo(c["n"], c["slug"]); _encolher(c["slug"]); geradas.append(c["slug"]); c["logo"] = BASE_URL + "logos/" + c["slug"] + ".png"; sem_logo += 1
    json.dump(sorted(geradas), open("logos_geradas.json", "w"))
    usados = {c["slug"] for c in canais}
    for f in os.listdir("logos"):
        if f[:-4] not in usados:
            os.remove("logos/" + f)

    def pais(c):
        return c["pn"] if c.get("p") else "Sem país identificado"
    def chave(c):
        cod = c.get("p") or ""
        return (0 if cod in PRIORIDADE else (2 if not cod else 1), PRIORIDADE.index(cod) if cod in PRIORIDADE else 0, pais(c).lower(), c.get("pp", 9999), 0 if c.get("o") else 1, c["n"].lower())
    canais.sort(key=chave)

    linhas, results = [], []
    for c in canais:
        tid = ids.get(c["u"], "")
        nome = c["n"] + (" (" + c["q"] + ")" if c.get("q") and c["q"] not in c["n"] else "")
        if c.get("nv"):
            nome += " [não testado]"
        elif c.get("r"):
            nome += " [testado só em: " + ", ".join(c["r"]) + "]"
        a = ['tvg-id="%s"' % tid] if tid else []
        a += ['tvg-name="%s"' % c["n"].replace('"', ""), 'tvg-logo="%s"' % c["logo"]]
        if c.get("p"): a.append('tvg-country="%s"' % c["p"])
        if c.get("lg"): a.append('tvg-language="%s"' % c["lg"].replace('"', ""))
        if c.get("c"): a.append('tvg-category="%s"' % c["c"].replace('"', ""))
        a.append('group-title="%s"' % pais(c).replace('"', ""))
        ext = "#EXTINF:-1 " + " ".join(a) + "," + nome.replace("\n", " ")
        bloco = [ext]
        if c.get("ua"): bloco.append("#EXTVLCOPT:http-user-agent=" + c["ua"])
        if c.get("ref"): bloco.append("#EXTVLCOPT:http-referrer=" + c["ref"])
        bloco.append(c["u"])
        linhas.append(bloco)
        results.append((ext, c["u"], c.get("p") or ""))

    matched, ep_ch, ep_pr, per_source = build_epg(results, now)
    epg_url = BASE_URL + "epg.xml.gz"
    if matched:
        root = ET.Element("tv", {"generator-info-name": "IPTV Mundi"})
        for n in ep_ch + ep_pr:
            root.append(n)
        with gzip.open("epg.xml.gz", "wb", 9) as out:
            out.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    cab = "#EXTM3U" + (' url-tvg="%s" x-tvg-url="%s"' % (epg_url, epg_url) if matched else "")
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join([cab] + [l for b in linhas for l in b]) + "\n")

    rel = {"atualizado": datetime.now(timezone.utc).isoformat(), "canais": len(canais),
           "paises": len({c.get("p") for c in canais if c.get("p")}), "sem_pais": sum(1 for c in canais if not c.get("p")),
           "com_logo_original": len(canais) - sem_logo, "logo_gerado": sem_logo,
           "com_id_de_guia": sum(1 for c in canais if ids.get(c["u"])), "canais_com_guia": len(matched),
           "so_em_algumas_regioes": sum(1 for c in canais if c.get("r")), "guia_por_fonte": per_source}
    json.dump(rel, open("report.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rel.items() if k != "guia_por_fonte"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
