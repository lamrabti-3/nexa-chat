import os
import json
import html
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

APP_NAME = "NEXA | مساعدي الشخصي"
DB_PATH = os.environ.get("NEXA_DB", "nexa.db")
AI_KEY = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
AI_URL = os.environ.get("AI_API_URL") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
MEMORY_LIMIT = 40

RESEARCH = [
    {
        "title": "NIST AI Risk Management Framework",
        "url": "https://www.nist.gov/itl/ai-risk-management-framework",
        "summary": "الشفافية، تقليل البيانات، الخصوصية، وتحديد مسؤولية الإنسان عناصر أساسية عند تصميم نظام ذكاء اصطناعي موثوق.",
        "category": "سلامة وخصوصية"
    },
    {
        "title": "APA: Self-Determination Theory",
        "url": "https://www.apa.org/research-practice/conduct-research/self-determination-theory.html",
        "summary": "تدعم الدافعية ثلاثة احتياجات: الاستقلالية، الإحساس بالكفاءة، والعلاقة بالآخرين. لذلك يقترح المساعد خيارات بدل فرض قرار.",
        "category": "الدافعية"
    },
    {
        "title": "APA Dictionary: Big Five Personality Model",
        "url": "https://dictionary.apa.org/big-five-personality-model",
        "summary": "نموذج وصفي للفروق الفردية، وليس تشخيصًا طبيًا أو حكمًا نهائيًا على شخصية الإنسان.",
        "category": "فهم الشخصية"
    },
    {
        "title": "APA Guidelines for Psychological Assessment",
        "url": "https://www.apa.org/about/policy/guidelines-psychological-assessment-evaluation.pdf",
        "summary": "تؤكد إرشادات التقييم النفسي أهمية الغرض من التقييم، والانتباه للخطأ والتحيز، وعدم استعمال النتائج بلا سياق.",
        "category": "حدود التحليل"
    }
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'تفضيل',
        source TEXT NOT NULL DEFAULT 'اختيار المستخدم',
        created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL CHECK(role IN ('user','assistant')),
        text TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS consents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version TEXT NOT NULL,
        accepted_at TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS research_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE,
        summary TEXT NOT NULL,
        category TEXT NOT NULL
    )""")
    c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('profile','{}')")
    for item in RESEARCH:
        c.execute("""INSERT OR IGNORE INTO research_sources(title,url,summary,category)
                     VALUES(?,?,?,?)""", (item["title"], item["url"], item["summary"], item["category"]))
    c.commit()
    return c


def rows(c, query, args=()):
    return [dict(x) for x in c.execute(query, args).fetchall()]


def profile(c):
    raw = c.execute("SELECT value FROM settings WHERE key='profile'").fetchone()
    try:
        value = json.loads(raw[0]) if raw else {}
    except Exception:
        value = {}
    return {
        "name": value.get("name", "صاحب NEXA"),
        "tone": value.get("tone", "واضح وعملي"),
        "goal": value.get("goal", "مساعد شخصي يفهمني ويحترم خصوصيتي")
    }


def has_consent(c):
    return c.execute("SELECT 1 FROM consents WHERE version='1' LIMIT 1").fetchone() is not None


def json_body(handler):
    try:
        length = min(int(handler.headers.get("Content-Length", "0")), 200000)
        return json.loads(handler.rfile.read(length).decode("utf-8")) if length else {}
    except Exception:
        return {}


def send(handler, payload, status=200):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def system_prompt(c):
    p = profile(c)
    mem = rows(c, "SELECT content,category FROM memories ORDER BY id DESC LIMIT ?", (MEMORY_LIMIT,))
    memories = "\n".join(f"- [{m['category']}] {m['content']}" for m in reversed(mem)) or "لا توجد ذكريات محفوظة بعد."
    sources = "\n".join(f"- {s['title']}: {s['summary']}" for s in rows(c, "SELECT title,summary FROM research_sources ORDER BY id"))
    return f"""أنت NEXA، مساعد شخصي خاص بالمستخدم.

هوية المستخدم وتفضيلاته الحالية:
- الاسم: {p['name']}
- النبرة المفضلة: {p['tone']}
- الهدف: {p['goal']}

ذكريات اختار المستخدم حفظها بنفسه:
{memories}

مبادئ سلوكية آمنة استخدمها عند الحاجة:
{sources}

قواعد مهمة:
1. أجب بالعربية ما لم يطلب المستخدم لغة أخرى، وبأسلوب {p['tone']}.
2. افهم السياق واسأل سؤالًا توضيحيًا واحدًا عند الضرورة، ولا تتظاهر بأنك تعرف ما لا تعرفه.
3. لا تقل إنك شخص حقيقي، ولا تدّعي تشخيص الشخصية أو المرض النفسي. صغ التحليل كاحتمال قابل للتصحيح: 'قد يبدو من كلامك...'.
4. لا تحفظ أي معلومة جديدة تلقائيًا. إذا ظهرت معلومة مفيدة، اقترح: 'هل تريد حفظها كذكرى؟' واترك القرار للمستخدم.
5. في الطب والقانون والمال والأزمات النفسية، قدّم معلومات عامة ووجّه إلى مختص أو خدمات الطوارئ المناسبة بدل إصدار قرار حاسم.
6. لا تستخدم الذكريات لاستنتاج الدين أو الصحة أو السياسة أو الجنس أو الأصل أو أي سمة حساسة.
7. عند تقديم بحث، ميّز بين المعرفة العامة والاستنتاج، واذكر المصدر إن كان من المصادر المرفقة.
8. هدفك دعم استقلالية المستخدم وكفاءته، لا التحكم به أو دفعه إلى قرار.
"""


def local_answer(text, c):
    p = profile(c)
    memories = rows(c, "SELECT content,category FROM memories ORDER BY id DESC LIMIT 5")
    lower = text.lower()
    if any(x in lower for x in ["من أنا", "شخصيتي", "حللني", "حلل شخصيتي"]):
        if memories:
            points = "، ".join(m["content"] for m in memories[:3])
            return f"أقدر أصف تفضيلاتك الحالية فقط، وليس تشخيص شخصيتك. مما اخترت حفظه يظهر اهتمامك بـ: {points}. هذا وصف قابل للتعديل وليس حكمًا نهائيًا."
        return "لا أملك ذكريات محفوظة عنك بعد. تحدث معي، ثم اختر بنفسك ما تريد حفظه؛ لن أبني تشخيصًا نفسيًا من محادثة قصيرة."
    if any(x in lower for x in ["تذكر", "احفظ", "ذاكرة"]):
        return "أستطيع حفظ المعلومة فقط عندما تختار ذلك من زر حفظ الذكرى. بهذه الطريقة يبقى التعلم تحت سيطرتك."
    return f"أنا NEXA، مساعدك الشخصي. فهمت رسالتك: «{text[:240]}». أستطيع مساعدتك في تنظيم الفكرة وتحويلها إلى خطوات. فعّل AI_API_KEY في إعدادات التشغيل للحصول على ردود نموذج لغوي كاملة؛ حاليًا أعمل في الوضع المحلي الآمن."


def call_ai(messages, c):
    if not AI_KEY:
        return local_answer(messages[-1]["content"], c), False
    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": 0.35,
        "max_tokens": 1200
    }
    req = urllib.request.Request(
        AI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {AI_KEY}"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
        answer = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return (answer or local_answer(messages[-1]["content"], c)), True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError):
        return "تعذر الاتصال بخدمة الذكاء الاصطناعي الآن. لم أفقد رسالتك؛ جرّب مرة أخرى أو راجع إعدادات AI_API_URL وAI_API_KEY.", False


HTML = r'''<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#08121d">
<title>NEXA | مساعدي الشخصي</title>
<style>
:root{--bg:#07111b;--panel:#0e1c2a;--panel2:#132638;--line:#24384a;--text:#eef7fb;--muted:#91a8b8;--accent:#49e0b0;--accent2:#2ab896;--bubble:#172c3b;--mine:#135c55;--danger:#ff7373;--shadow:0 20px 60px #0004}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 85% 0,#103b49 0,#07111b 38%);color:var(--text);font-family:Arial,"Noto Sans Arabic",sans-serif;height:100vh}button,input,textarea{font:inherit}button{cursor:pointer;border:0}.app{height:100vh;display:grid;grid-template-columns:300px 1fr;max-width:1500px;margin:auto}.side{background:#0b1926dd;border-left:1px solid var(--line);padding:22px;display:flex;flex-direction:column;gap:20px}.brand{display:flex;align-items:center;gap:12px}.mark{width:45px;height:45px;display:grid;place-items:center;border-radius:15px;background:linear-gradient(135deg,var(--accent),#1a7f88);color:#05231e;font-size:21px;font-weight:900}.brand b{font-size:22px}.brand small{display:block;color:var(--muted);margin-top:3px}.nav{display:grid;gap:8px}.nav button{background:transparent;color:var(--muted);text-align:right;padding:13px 14px;border-radius:12px}.nav button.active,.nav button:hover{background:var(--panel2);color:var(--text)}.tip{margin-top:auto;border:1px solid var(--line);border-radius:16px;padding:15px;color:var(--muted);font-size:13px;line-height:1.7}.content{min-width:0;display:flex;flex-direction:column}.head{height:78px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 28px;background:#091824aa}.head h1{font-size:20px;margin:0}.head p{color:var(--muted);font-size:12px;margin:5px 0 0}.badge{background:#123c38;color:var(--accent);border:1px solid #246859;padding:7px 11px;border-radius:30px;font-size:12px}.view{display:none;height:calc(100vh - 78px);padding:25px;overflow:auto}.view.active{display:block}.chat{display:flex;flex-direction:column;min-height:100%;max-width:920px;margin:auto}.messages{flex:1;display:flex;flex-direction:column;gap:13px;padding-bottom:18px}.welcome{margin:auto;max-width:610px;text-align:center;padding:30px}.welcome .orb{font-size:48px;margin-bottom:10px}.welcome h2{font-size:30px;margin:7px 0}.welcome p{color:var(--muted);line-height:1.8}.chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:20px}.chip{background:var(--panel2);border:1px solid var(--line);color:var(--text);border-radius:25px;padding:9px 13px}.msg{max-width:78%;padding:14px 16px;border:1px solid var(--line);border-radius:18px;line-height:1.75;white-space:pre-wrap;box-shadow:0 8px 25px #0002}.msg.user{align-self:flex-start;background:var(--mine);border-bottom-left-radius:5px}.msg.assistant{align-self:flex-end;background:var(--bubble);border-bottom-right-radius:5px}.meta{font-size:11px;color:var(--muted);margin-top:5px}.save{background:transparent;color:var(--accent);font-size:11px;padding:0;margin-top:7px}.composer{display:flex;gap:10px;align-items:flex-end;padding-top:12px;border-top:1px solid var(--line)}textarea{width:100%;resize:none;min-height:52px;max-height:150px;border:1px solid var(--line);background:var(--panel);color:var(--text);border-radius:16px;padding:14px;outline:0}textarea:focus{border-color:var(--accent)}.send{background:var(--accent);color:#05231e;border-radius:15px;padding:14px 19px;font-weight:bold;height:52px}.send:disabled{opacity:.5}.panel{max-width:900px;margin:auto}.panel h2{margin-top:0}.sub{color:var(--muted);line-height:1.8}.card{background:#0e1c2aee;border:1px solid var(--line);border-radius:18px;padding:18px;margin:12px 0;box-shadow:var(--shadow)}.memory{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.memory b{display:block;color:var(--accent);font-size:12px;margin-bottom:6px}.memory p{margin:0;line-height:1.6}.delete{background:transparent;color:var(--danger);font-size:18px}.form{display:grid;gap:10px;margin:16px 0}.form input{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:12px;padding:13px;outline:0}.primary{background:var(--accent);color:#05231e;border-radius:12px;padding:12px 17px;font-weight:bold}.source{display:flex;gap:14px;align-items:flex-start}.source .icon2{font-size:24px}.source h3{font-size:16px;margin:0 0 7px}.source p{color:var(--muted);line-height:1.7;margin:0 0 8px}.source a{color:var(--accent);font-size:12px}.overlay{position:fixed;inset:0;background:#020810dd;backdrop-filter:blur(8px);display:none;place-items:center;padding:20px;z-index:10}.overlay.show{display:grid}.consent{max-width:550px;background:var(--panel);border:1px solid #35536a;border-radius:22px;padding:27px;box-shadow:var(--shadow)}.consent h2{margin-top:0}.consent p,.consent li{color:var(--muted);line-height:1.8}.check{display:flex;gap:10px;align-items:flex-start;margin:20px 0}.check input{accent-color:var(--accent);margin-top:6px}.empty{color:var(--muted);text-align:center;padding:30px}@media(max-width:780px){.app{display:block}.side{height:auto;padding:12px 15px;border-left:0;border-bottom:1px solid var(--line)}.brand{justify-content:center}.nav{display:flex;overflow:auto}.nav button{white-space:nowrap}.tip{display:none}.content{height:calc(100vh - 135px)}.head{padding:0 15px}.view{height:calc(100vh - 213px);padding:15px}.msg{max-width:90%}.welcome h2{font-size:24px}}
</style></head>
<body>
<div class="app">
<aside class="side"><div class="brand"><div class="mark">N</div><div><b>NEXA</b><small>مساعدك الشخصي</small></div></div>
<nav class="nav"><button class="active" data-view="chat">💬 المحادثة</button><button data-view="memories">🧠 ذاكرتي</button><button data-view="research">📚 مصادر علمية</button></nav>
<div class="tip">يتعلم NEXA فقط من المعلومات التي تختار حفظها. يمكنك حذفها في أي وقت، ولن يحوّل كلامك إلى تشخيص نفسي.</div></aside>
<main class="content"><header class="head"><div><h1 id="title">محادثة خاصة</h1><p id="subtitle">مساحة شخصية لك وحدك</p></div><span class="badge" id="status">الوضع المحلي</span></header>
<section class="view active" id="view-chat"><div class="chat"><div class="messages" id="messages"></div><form class="composer" id="composer"><textarea id="input" rows="1" placeholder="اكتب ما تفكر فيه..."></textarea><button class="send" id="send" type="submit">إرسال</button></form></div></section>
<section class="view" id="view-memories"><div class="panel"><h2>ذاكرتي</h2><p class="sub">أضف تفضيلات أو أهدافًا تريد أن يستخدمها NEXA. لا تضف معلومات حساسة لا تحتاجها.</p><form class="form" id="memory-form"><input id="memory" maxlength="300" placeholder="مثال: أفضل الإجابات المختصرة مع خطوات عملية" required><input id="category" maxlength="40" value="تفضيل" placeholder="التصنيف"><button class="primary">حفظ الذكرى</button></form><div id="memory-list"></div></div></section>
<section class="view" id="view-research"><div class="panel"><h2>مصادر علمية مختارة</h2><p class="sub">هذه المراجع تساعد NEXA على استخدام مبادئ عامة بحذر. لا تُستخدم لتشخيصك أو إصدار حكم نهائي على شخصيتك.</p><div id="research-list"></div></div></section>
</main></div>
<div class="overlay" id="consent"><div class="consent"><h2>قبل أن نبدأ</h2><p>هذا مساعد ذكاء اصطناعي شخصي. لكي يعمل، اقرأ ووافق:</p><ul><li>الردود آلية وقد تكون غير دقيقة.</li><li>تحليل الشخصية تقريبي وليس تشخيصًا طبيًا أو نفسيًا.</li><li>لا تعتمد عليه وحده في القرارات الطبية أو القانونية أو المالية.</li><li>لن يحفظ NEXA معلومة كذكرى إلا باختيارك، ويمكنك حذفها.</li></ul><label class="check"><input type="checkbox" id="agree"><span>أفهم هذه الحدود وأوافق على استخدام المساعد.</span></label><button class="primary" id="accept" disabled>أوافق وأبدأ</button></div></div>
<script>
const $=s=>document.querySelector(s);const state={messages:[],memories:[],research:[],consent:false};
async function api(path,opts={}){const r=await fetch(path,{headers:{'Content-Type':'application/json',...(opts.headers||{})},...opts});const d=await r.json();if(!r.ok)throw new Error(d.error||'حدث خطأ');return d}
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function show(view){document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===view));document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id==='view-'+view));const titles={chat:['محادثة خاصة','مساحة شخصية لك وحدك'],memories:['ذاكرتي','أنت تختار ما الذي يتعلمه NEXA عنك'],research:['مصادر علمية مختارة','مبادئ عامة، وليست تشخيصًا']};$('#title').textContent=titles[view][0];$('#subtitle').textContent=titles[view][1]}
function renderMessages(){const box=$('#messages');if(!state.messages.length){box.innerHTML='<div class="welcome"><div class="orb">🧠</div><h2>مرحبًا، أنا NEXA</h2><p>مساعدك الشخصي لفهم الأفكار وتنظيمها. ابدأ برسالة، وإذا أردت أن أتذكر شيئًا اضغط «حفظ كذكرى» بنفسك.</p><div class="chips"><button class="chip" onclick="quick('ساعدني أنظم أهدافي')">تنظيم الأهداف</button><button class="chip" onclick="quick('كيف يمكن أن أفهم سلوكي دون تشخيص؟')">فهم السلوك</button></div></div>';return}box.innerHTML=state.messages.map(m=>'<div class="msg '+m.role+'"><div>'+esc(m.text)+'</div><div class="meta">'+(m.role==='user'?'أنت':'NEXA')+' · '+new Date(m.created_at).toLocaleTimeString('ar-MA',{hour:'2-digit',minute:'2-digit'})+'</div>'+(m.role==='user'?'<button class="save" onclick="saveText('+JSON.stringify(m.text)+')">＋ حفظ كذكرى</button>':'')+'</div>').join('');box.scrollTop=box.scrollHeight}
function renderMemories(){const box=$('#memory-list');box.innerHTML=state.memories.length?state.memories.map(m=>'<div class="card memory"><div><b>'+esc(m.category)+'</b><p>'+esc(m.content)+'</p></div><button class="delete" onclick="removeMemory('+m.id+')">×</button></div>').join(''):'<div class="empty">لا توجد ذكريات محفوظة بعد.</div>'}
function renderResearch(){ $('#research-list').innerHTML=state.research.map(s=>'<article class="card source"><div class="icon2">📖</div><div><h3>'+esc(s.title)+'</h3><p>'+esc(s.summary)+'</p><a href="'+esc(s.url)+'" target="_blank" rel="noreferrer">فتح المصدر ↗</a></div></article>').join('') }
async function load(){const d=await api('/api/state');Object.assign(state,d);$('#status').textContent=d.ai_ready?'AI متصل':'وضع محلي';renderMessages();renderMemories();renderResearch();if(!d.consent)$('#consent').classList.add('show');else enable()}
function enable(){$('#input').disabled=false;$('#send').disabled=false}
async function sendMessage(text){text=(text||'').trim();if(!text||!state.consent)return;$('#input').value='';$('#send').disabled=true;state.messages.push({role:'user',text,created_at:new Date().toISOString()});renderMessages();try{const d=await api('/api/chat',{method:'POST',body:JSON.stringify({text})});state.messages.push(d.message);renderMessages()}catch(e){alert(e.message)}finally{$('#send').disabled=false;$('#input').focus()}}
function quick(t){show('chat');sendMessage(t)}
async function saveText(text){const category=prompt('تصنيف الذكرى؟','تفضيل');if(category===null)return;try{const d=await api('/api/memories',{method:'POST',body:JSON.stringify({content:text,category})});state.memories.unshift(d.memory);renderMemories();alert('تم حفظ الذكرى ويمكنك حذفها من قسم ذاكرتي.')}catch(e){alert(e.message)}}
async function removeMemory(id){if(!confirm('حذف هذه الذكرى؟'))return;await api('/api/memories?id='+id,{method:'DELETE'});state.memories=state.memories.filter(m=>m.id!==id);renderMemories()}
$('#composer').addEventListener('submit',e=>{e.preventDefault();sendMessage($('#input').value)});$('#input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('#composer').requestSubmit()}});document.querySelectorAll('.nav button').forEach(b=>b.addEventListener('click',()=>show(b.dataset.view)));$('#agree').addEventListener('change',e=>$('#accept').disabled=!e.target.checked);$('#accept').addEventListener('click',async()=>{try{await api('/api/consent',{method:'POST',body:JSON.stringify({accepted:true})});state.consent=true;$('#consent').classList.remove('show');enable()}catch(e){alert(e.message)}});$('#memory-form').addEventListener('submit',async e=>{e.preventDefault();try{const d=await api('/api/memories',{method:'POST',body:JSON.stringify({content:$('#memory').value,category:$('#category').value})});state.memories.unshift(d.memory);$('#memory').value='';renderMemories()}catch(e){alert(e.message)}});load();
</script></body></html>'''


class Server(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def send_html(self):
        data = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        c = db()
        try:
            if path == "/":
                return self.send_html()
            if path == "/api/state":
                return send(self, {
                    "consent": has_consent(c),
                    "ai_ready": bool(AI_KEY),
                    "profile": profile(c),
                    "messages": rows(c, "SELECT id,role,text,created_at FROM messages ORDER BY id ASC LIMIT 100"),
                    "memories": rows(c, "SELECT id,content,category,source,created_at FROM memories ORDER BY id DESC"),
                    "research": rows(c, "SELECT id,title,url,summary,category FROM research_sources ORDER BY id")
                })
            if path == "/api/export":
                return send(self, {"profile": profile(c), "memories": rows(c, "SELECT * FROM memories"), "messages": rows(c, "SELECT * FROM messages"), "research": rows(c, "SELECT * FROM research_sources")})
            return send(self, {"error": "غير موجود"}, 404)
        finally:
            c.close()

    def do_POST(self):
        path = urlparse(self.path).path
        c = db()
        try:
            data = json_body(self)
            if path == "/api/consent":
                if not data.get("accepted"):
                    return send(self, {"error": "الموافقة مطلوبة"}, 400)
                c.execute("INSERT INTO consents(version,accepted_at) VALUES('1',?)", (now(),)); c.commit()
                return send(self, {"ok": True})
            if path == "/api/memories":
                content = str(data.get("content", "")).strip()[:300]
                category = str(data.get("category", "تفضيل")).strip()[:40] or "تفضيل"
                if len(content) < 2:
                    return send(self, {"error": "اكتب ذكرى مفيدة أولًا"}, 400)
                c.execute("INSERT INTO memories(content,category,source,created_at) VALUES(?,?,?,?)", (content, category, "اختيار المستخدم", now())); c.commit()
                memory = dict(c.execute("SELECT id,content,category,source,created_at FROM memories ORDER BY id DESC LIMIT 1").fetchone())
                return send(self, {"ok": True, "memory": memory})
            if path == "/api/chat":
                if not has_consent(c):
                    return send(self, {"error": "وافق على الشروط قبل المحادثة"}, 403)
                text = str(data.get("text", "")).strip()[:5000]
                if not text:
                    return send(self, {"error": "الرسالة فارغة"}, 400)
                c.execute("INSERT INTO messages(role,text,created_at) VALUES('user',?,?)", (text, now())); c.commit()
                history = rows(c, "SELECT role,text FROM messages ORDER BY id DESC LIMIT 16")
                history.reverse()
                messages = [{"role": "system", "content": system_prompt(c)}] + [{"role": x["role"], "content": x["text"]} for x in history]
                answer, _ = call_ai(messages, c)
                c.execute("INSERT INTO messages(role,text,created_at) VALUES('assistant',?,?)", (answer, now())); c.commit()
                message = dict(c.execute("SELECT id,role,text,created_at FROM messages ORDER BY id DESC LIMIT 1").fetchone())
                return send(self, {"ok": True, "message": message})
            return send(self, {"error": "غير موجود"}, 404)
        finally:
            c.close()

    def do_DELETE(self):
        path = urlparse(self.path)
        c = db()
        try:
            if path.path == "/api/memories":
                try: memory_id = int(parse_qs(path.query).get("id", [""])[0])
                except Exception: return send(self, {"error": "معرف غير صحيح"}, 400)
                c.execute("DELETE FROM memories WHERE id=?", (memory_id,)); c.commit()
                return send(self, {"ok": True})
            return send(self, {"error": "غير موجود"}, 404)
        finally:
            c.close()


if __name__ == "__main__":
    db().close()
    port = int(os.environ.get("PORT", "8080"))
    print(f"{APP_NAME} يعمل على المنفذ {port}")
    ThreadingHTTPServer(("0.0.0.0", port), Server).serve_forever()
