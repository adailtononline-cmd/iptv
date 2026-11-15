import concurrent.futures,json,os,re,urllib.request,urllib.error,datetime
from collections import Counter
from pathlib import Path
P=Path(__file__).parent
BASE="https://iptv-org.github.io"
COUNTRIES=set("US CA GB FR PT BR CN JP AU IT TR".split())
LANG={"por","spa"}
def fetch(path):
 r=urllib.request.Request(BASE+path,headers={"User-Agent":"Mozilla/5.0"})
 return urllib.request.urlopen(r,timeout=60).read().decode("utf-8-sig")
def attrs(s):return dict(re.findall(r'([\w-]+)="([^"]*)"',s))
def check(url):
 try:
  req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Range":"bytes=0-1023"})
  with urllib.request.urlopen(req,timeout=7) as r:
   body=r.read(1024)
   return "html" if b"<html" in body.lower() else "ok"
 except urllib.error.HTTPError as e:return str(e.code)
 except Exception:return "network"
def main():
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 channels={c["id"]:c for c in json.loads(fetch("/api/channels.json")) if c.get("id")}
 logos={x["channel"]:x.get("url","") for x in json.loads(fetch("/api/logos.json")) if x.get("channel")}
 countries=json.loads(fetch("/api/countries.json"))
 names={c["code"]:c["name"] for c in countries}
 selected={c["code"] for c in countries if c["code"] in COUNTRIES or LANG.intersection(c.get("languages") or [])}
 lines=fetch("/iptv/index.m3u").splitlines()
 found={};meta=None
 for line in lines:
  if line.startswith("#EXTINF:"):meta=line;continue
  if not meta or not line.startswith(("http://","https://")):continue
  a=attrs(meta);cid=a.get("tvg-id","");ch=channels.get(cid,{})
  if not a.get("tvg-logo") and logos.get(cid):a["tvg-logo"]=logos[cid]
  country=ch.get("country") or "INT";langs=set(ch.get("languages") or [])
  if country not in selected and not LANG.intersection(langs):meta=None;continue
  cats=ch.get("categories") or []
  if ch.get("is_nsfw") or any(c.lower() in ("xxx","adult","porn","pornography","erotic") for c in cats):meta=None;continue
  name=meta.split(",",1)[-1].strip()
  key=(country,cid or name.casefold())
  if key not in found:
   found[key]={"name":name,"id":cid,"country":country,"category":cats[0] if cats else a.get("group-title","General"),"url":line,"attributes":a,"languages":sorted(langs),"logo":a.get("tvg-logo") or logos.get(cid) or ""}
  meta=None
 items=list(found.values())
 try:state=json.loads((P/"stream_status.json").read_text())
 except Exception:state={}
 testing=os.getenv("CHECK_STREAMS","false").lower()=="true"
 if testing:
  with concurrent.futures.ThreadPoolExecutor(max_workers=28) as pool:results=list(pool.map(check,[x["url"] for x in items]))
  for x,result in zip(items,results):
   prev=state.get(x["url"],{})
   state[x["url"]]={"status":result,"failures":0 if result=="ok" else prev.get("failures",0)+1,"checked_at":now}
  items=[x for x in items if state[x["url"]]["failures"]<2 or state[x["url"]]["status"]=="403"]
  (P/"stream_status.json").write_text(json.dumps(state,ensure_ascii=False))
 if len(items)<100:raise RuntimeError("Too few streams; refusing to replace playlist")
 items.sort(key=lambda x:(names.get(x["country"],x["country"]),x["category"],x["name"]))
 output=["#EXTM3U"]
 for x in items:
  a=x["attributes"]
  preserved=" ".join(k+'="'+str(v).replace('"',"'")+'"' for k,v in a.items() if k!="group-title")
  group=(names.get(x["country"],x["country"])+" | "+x["category"]).replace('"',"'")
  output.extend(['#EXTINF:-1 '+preserved+' group-title="'+group+'",'+x["name"],x["url"]])
 (P/"playlist.m3u").write_text("\n".join(output)+"\n")
 (P/"channels.json").write_text(json.dumps(items,ensure_ascii=False))
 (P/"report.json").write_text(json.dumps({"updated_at":now,"total":len(items),"countries":dict(Counter(x["country"] for x in items)),"weekly_http_test":testing},ensure_ascii=False,indent=2))
 print("Generated",len(items),"channels")
if __name__=="__main__":main()
