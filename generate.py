#!/usr/bin/env python3
import datetime as dt,html,json,os,re,sys,urllib.request
from pathlib import Path

U="dSofikitis";A=Path("assets");W=880
FONT="'JetBrains Mono', ui-monospace, 'SF Mono', 'Cascadia Code', Menlo, Consolas, monospace"
P=dict(bg="#000000",text="#e6e6e6",dim="#808080",accent="#e5252a")
LC={"Python":"#3776AB","TypeScript":"#3178C6","JavaScript":"#F7DF1E","Go":"#00ADD8","Rust":"#DEA584","C":"#A8B9CC","C++":"#00599C","C#":"#512BD4","Java":"#ED8B00","Shell":"#89E051","Dockerfile":"#2496ED","Jupyter Notebook":"#DA5B0B","Svelte":"#FF3E00"}
BOOT=["init engineering trust","securing agentic systems","breaking what shouldn't be trusted"]
WHOAMI=[("mantra",["I build things that need to be trusted","and break things that shouldn't be."]),
("by_day",["Building full-stack Agentic AI end-to-end, backend to agent tooling.","Evals, MLOps, and defenses against hallucinations and prompt injection."]),
("by_night",["Reverse-engineering something I shouldn't be,","reading threat reports, or over-engineering a personal project."]),
("based_in",["Norway mostly. Fueled by curiosity, passion,","and a mild obsession with making machines behave."])]
STACK=[("langs","python,ts,js,go,rust,c,cpp,cs,java,bash,swift,kotlin"),("web/api","fastapi,flask,nodejs,react,nextjs,svelte,tailwind,html,css,postman,vite,graphql"),("data/cloud","postgres,mysql,redis,mongodb,aws,azure,gcp,docker,kubernetes,terraform,pytorch,tensorflow")]
Q="query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){contributionsCollection(from:$f,to:$t){totalCommitContributions restrictedContributionsCount}}}"
CSS=(f".t{{fill:{P['text']}}}.m{{fill:{P['dim']}}}.a{{fill:{P['accent']}}}.b{{font-weight:700}}.name{{font-size:26px;font-weight:700}}.motto{{font-size:15px}}.sm{{font-size:12px}}.xs{{font-size:11px}}"
+".blink{animation:blink 1.05s step-end infinite}@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}"
+"".join(f".f{i}{{opacity:0;animation:in .5s ease-out {(i-1)*.1:.1f}s forwards}}" for i in range(1,6))+"@keyframes in{to{opacity:1}}"
+".reveal{clip-path:inset(0 100% 0 0);animation:reveal 1.2s cubic-bezier(.23,1,.32,1) .4s forwards}@keyframes reveal{to{clip-path:inset(0)}}"
+"@media (prefers-reduced-motion:reduce){*{animation:none!important}[class^=f]{opacity:1}.reveal{clip-path:none}}")

def get(url,body=None):
    h={"User-Agent":f"{U}-readme","Accept":"application/vnd.github+json"};t=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if t and "api.github.com" in url:h["Authorization"]=f"Bearer {t}"
    if body:h["Content-Type"]="application/json";body=json.dumps(body).encode()
    with urllib.request.urlopen(urllib.request.Request(url,body,h),timeout=30) as r:return r.read().decode()
def gh(p,body=None):return json.loads(get("https://api.github.com/"+p,body))
def warn(m):print("warn: "+m,file=sys.stderr)
def parse(raw):
    a,inner=re.search(r"<svg([^>]*)>(.*)</svg>",raw,re.S).groups();v=re.search(r'viewBox\s*=\s*"([^"]+)"',a)
    return(inner,*map(float,v[1].split()[2:]))if v else(inner,float(re.search(r'width="([\d.]+)',a)[1]),float(re.search(r'height="([\d.]+)',a)[1]))

def stats():
    rs,pg=[],1
    while len(c:=gh(f"users/{U}/repos?per_page=100&page={pg}&type=owner&sort=pushed"))==100:rs+=c;pg+=1
    rs=[r for r in rs+c if not r["fork"] and not r["private"]];lb={}
    for r in rs:
        if r["archived"]:continue
        try:
            for k,v in gh(f"repos/{U}/{r['name']}/languages").items():lb[k]=lb.get(k,0)+v
        except Exception:pass
    for k in("HTML","CSS"):lb.pop(k,None)
    tot=sum(lb.values()) or 1;now=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None);since=now-dt.timedelta(30);iso=lambda d:d.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        cc=gh("graphql",{"query":Q,"variables":{"l":U,"f":iso(since),"t":iso(now)}})["data"]["user"]["contributionsCollection"];commits=cc["totalCommitContributions"]+cc["restrictedContributionsCount"]
    except Exception as e:
        warn(f"graphql failed ({e}), using commit search")
        try:commits=gh(f"search/commits?q=author:{U}+author-date:>={since:%Y-%m-%d}&per_page=1")["total_count"]
        except Exception as e:warn(f"commit search failed ({e})");commits=0
    return dict(stars=sum(r["stargazers_count"] for r in rs),commits=commits,
        active=sum((now-dt.datetime.strptime(r["pushed_at"],"%Y-%m-%dT%H:%M:%SZ")).days<=90 for r in rs if r.get("pushed_at")),
        langs=[(k,p) for k,v in sorted(lb.items(),key=lambda kv:-kv[1])[:6] if (p:=round(100*v/tot))],
        repos=[r["name"] for r in rs if not r["archived"] and r["name"].lower() not in(U.lower(),"gh-profile","film-hunter")][:3])

def profile(s):
    icons=[parse(get(f"https://skillicons.dev/icons?i={i}&perline={i.count(',')+1}")) for _,i in STACK]
    X,R=136,W-32;bw=R-X;o=[]
    langs=s["langs"] or [("Python",40),("TypeScript",22),("Go",14),("Rust",10),("C++",8),("Shell",6)];tp=sum(p for _,p in langs) or 1
    def g(f,*b):o.append(f'<g class="f{f}">'+"".join(b)+"</g>")
    def t(y,v,c="t",x=X,a=""):return f'<text x="{x}" y="{y}" class="{c}"{a}>{v}</text>'
    def k(y,v):return t(y,v,"m",32)
    def cmd(y,v):return t(y,f'<tspan class="a">$ </tspan>{v}',"t",32)
    def sp(xs):return "".join(f'<tspan dx="{28 if j else 0}">{v}</tspan>' for j,v in enumerate(xs))
    g(1,t(60,"Dimitris Sofikitis","t name",32),t(84,"AI/ML SWE, Full-Stack Agentic AI Engineer","m sm",32),t(102,"Bridging AI and Cybersecurity, based in Norway","m sm",32),
      t(138,'<tspan class="a">&gt; </tspan>Engineering Trust in a world of Chaos<tspan class="a blink">█</tspan>',"t motto",32))
    y=182
    for i,m in enumerate(BOOT):g(2,k(y,"boot") if i==0 else "",t(y,f'<tspan class="a">[ OK ]</tspan><tspan dx="12">{m}</tspan>'));y+=20
    y+=24
    g(3,k(y,"repos"),t(y,sp((s["repos"] or ["aegis-rag-lab","sentinel-stream","zerotrust-gatekeeper"])+["film-hunter"])),
      k(y+20,"stats"),t(y+20,sp(f'<tspan class="b">{v}</tspan> <tspan class="m">{l}</tspan>' for v,l in((s["commits"],"contributions/30d"),(s["active"],"active repos"),(s["stars"],"stars")))),
      k(y+40,"ongoing"),t(y+40,"Digital Infrastructure and Cyber Security @ NTNU, Trondheim, Norway"))
    y+=72;c=0;bars=[]
    for n,p in langs:bars.append(f'<rect x="{X+bw*c/tp:.1f}" y="{y-9}" width="{bw*p/tp:.1f}" height="6" fill="{LC.get(n,P["accent"])}"/>');c+=p
    g(3,k(y,"languages"),f'<clipPath id="bar"><rect x="{X}" y="{y-9}" width="{bw}" height="6" rx="3"/></clipPath><g class="reveal"><g clip-path="url(#bar)">{"".join(bars)}</g></g>')
    y+=22
    g(3,t(y,"".join(f'<tspan dx="{22 if i else 0}" fill="{LC.get(n,P["accent"])}">●</tspan><tspan dx="6">{n}</tspan><tspan dx="6" class="m">{p}%</tspan>' for i,(n,p) in enumerate(langs)),"t sm"))
    y+=56;g(4,cmd(y,"whoami --verbose"));y+=32
    for kk,ls in WHOAMI:g(4,k(y,kk),*(t(y+20*j,html.escape(l,False)) for j,l in enumerate(ls)));y+=20*len(ls)+8
    y+=36;g(5,cmd(y,"ls /usr/stack"));y+=40
    for (l,_),(inner,_,h) in zip(STACK,icons):g(5,k(y,l),f'<g transform="translate({X} {y-26}) scale({40/h:.4f})">{inner}</g>');y+=52
    H=y
    return f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}" font-size="13" role="img" aria-label="Dimitris Sofikitis"><style>{CSS}</style><rect width="{W}" height="{H}" rx="12" fill="{P["bg"]}"/>{"".join(o)}</svg>\n'

def write(n,f):
    try:s=f()
    except Exception as e:return warn(f"kept old {n} ({e})")
    (A/n).write_text(s,encoding="utf-8");print(f"wrote {n} ({len(s):,} chars)")

if __name__=="__main__":
    try:s=stats()
    except Exception as e:warn(f"GitHub API failed ({e}), using defaults");s=dict(stars=0,commits=0,active=0,langs=[],repos=[])
    A.mkdir(exist_ok=True);write("profile.svg",lambda:profile(s))
