import sqlite3, json, re, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DB = "nexa.db"

def conn():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row

    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        avatar TEXT DEFAULT '👤',
        bio TEXT DEFAULT '',
        online INTEGER DEFAULT 1,
        device TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS contacts(
        user_id INTEGER,
        contact_id INTEGER,
        UNIQUE(user_id,contact_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender INTEGER,
        receiver INTEGER,
        text TEXT,
        read INTEGER DEFAULT 0,
        edited INTEGER DEFAULT 0,
        deleted INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    c.commit()
    return c


HTML = r'''<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07131a">
<title>NEXA Chat</title>

<style>
*{box-sizing:border-box}

:root{
 --bg:#07131a;
 --panel:#101c23;
 --panel2:#16252d;
 --bubble:#1d3039;
 --mine:#075e54;
 --accent:#22d3a1;
 --accent2:#17b98a;
 --text:#f2f7f8;
 --muted:#8ca0a9;
 --line:#263840;
 --danger:#ef5350;
}

body.light{
 --bg:#eef3f5;
 --panel:#ffffff;
 --panel2:#e8eef1;
 --bubble:#edf2f4;
 --mine:#d5f8e9;
 --accent:#0eaf83;
 --accent2:#078b69;
 --text:#142027;
 --muted:#63747d;
 --line:#d9e1e5;
}

*{scrollbar-width:thin}

body{
 margin:0;
 height:100vh;
 overflow:hidden;
 background:var(--bg);
 color:var(--text);
 font-family:Arial,"Noto Sans Arabic",sans-serif;
}

button,input,textarea,select{font:inherit}

button{cursor:pointer}

.app{
 height:100vh;
 display:flex;
}

.sidebar{
 width:380px;
 min-width:320px;
 background:var(--panel);
 border-left:1px solid var(--line);
 display:flex;
 flex-direction:column;
 z-index:3;
}

.top{
 min-height:72px;
 background:var(--panel2);
 padding:12px 18px;
 display:flex;
 align-items:center;
 justify-content:space-between;
 gap:12px;
}

.logo{
 font-size:26px;
 font-weight:900;
 letter-spacing:1px;
 color:var(--accent);
}

.brand{
 display:flex;
 align-items:center;
 gap:10px;
}

.logoIcon{
 width:40px;
 height:40px;
 border-radius:13px;
 display:grid;
 place-items:center;
 background:linear-gradient(135deg,var(--accent),#087f69);
 color:#06251e;
 font-weight:900;
}

.small{
 color:var(--muted);
 font-size:12px;
 margin-top:4px;
}

.actions{
 display:flex;
 gap:7px;
 align-items:center;
}

.icon{
 width:42px;
 height:42px;
 border:0;
 border-radius:13px;
 background:transparent;
 color:var(--text);
 font-size:21px;
}

.icon:hover{
 background:var(--bubble);
}

.add{
 width:44px;
 height:44px;
 border:0;
 border-radius:14px;
 background:var(--accent);
 color:#04251d;
 font-size:25px;
 font-weight:bold;
}

.search{
 padding:12px;
}

.searchBox{
 display:flex;
 align-items:center;
 gap:8px;
 padding:0 12px;
 background:var(--bubble);
 border-radius:14px;
}

.searchBox span{
 color:var(--muted);
}

.searchBox input{
 width:100%;
 border:0;
 outline:0;
 background:transparent;
 color:var(--text);
 padding:13px 3px;
}

.list{
 overflow:auto;
 flex:1;
}

.person{
 padding:14px 16px;
 border-bottom:1px solid var(--line);
 display:flex;
 align-items:center;
 gap:12px;
 cursor:pointer;
 transition:.15s;
}

.person:hover{
 background:var(--panel2);
}

.avatar{
 width:52px;
 height:52px;
 min-width:52px;
 border-radius:50%;
 background:linear-gradient(135deg,#0b8f7b,#116b76);
 display:grid;
 place-items:center;
 font-size:23px;
 overflow:hidden;
}

.personInfo{
 min-width:0;
 flex:1;
}

.name{
 font-weight:800;
}

.preview{
 color:var(--muted);
 font-size:13px;
 margin-top:6px;
 white-space:nowrap;
 overflow:hidden;
 text-overflow:ellipsis;
}

.emptyList{
 text-align:center;
 color:var(--muted);
 padding:45px 20px;
 line-height:1.8;
}

.main{
 flex:1;
 min-width:0;
 display:flex;
 flex-direction:column;
 background:var(--bg);
}

.chatTop{
 display:flex;
 align-items:center;
 gap:10px;
}

.chatInfo{
 min-width:0;
}

.chatName{
 font-weight:800;
 white-space:nowrap;
 overflow:hidden;
 text-overflow:ellipsis;
}

.messages{
 flex:1;
 overflow:auto;
 padding:25px;
 background:
 radial-gradient(circle at 20% 20%,#ffffff05 1px,transparent 1px),
 radial-gradient(circle at 70% 70%,#ffffff04 1px,transparent 1px);
 background-size:28px 28px;
}

.emptyChat{
 height:100%;
 display:grid;
 place-items:center;
 text-align:center;
 color:var(--muted);
}

.emptyCard{
 max-width:420px;
 padding:30px;
}

.emptyLogo{
 width:85px;
 height:85px;
 margin:auto;
 border-radius:28px;
 display:grid;
 place-items:center;
 font-size:40px;
 background:linear-gradient(135deg,var(--accent),#087f69);
 color:#05271f;
}

.msgRow{
 display:flex;
 margin:7px 0;
}

.msgRow.me{
 justify-content:flex-start;
}

.msgRow.other{
 justify-content:flex-end;
}

.msg{
 max-width:min(70%,650px);
 background:var(--bubble);
 padding:10px 13px;
 border-radius:15px;
 box-shadow:0 2px 5px #0002;
 word-wrap:break-word;
}

.msgRow.me .msg{
 background:var(--mine);
}

.msgText{
 white-space:pre-wrap;
 line-height:1.45;
}

.meta{
 color:var(--muted);
 font-size:10px;
 margin-top:5px;
 text-align:left;
 direction:ltr;
}

.composer{
 padding:12px;
 background:var(--panel2);
 display:flex;
 gap:9px;
}

.composer input{
 flex:1;
 min-width:0;
 border:0;
 outline:0;
 padding:14px 17px;
 border-radius:16px;
 background:var(--bubble);
 color:var(--text);
}

.send{
 width:52px;
 height:52px;
 border:0;
 border-radius:16px;
 background:var(--accent);
 color:#06251e;
 font-size:21px;
 font-weight:bold;
}

.back{
 display:none;
}

.modal{
 display:none;
 position:fixed;
 inset:0;
 background:#0009;
 align-items:center;
 justify-content:center;
 z-index:50;
 padding:18px;
}

.modal.show{
 display:flex;
}

.modalBox{
 width:100%;
 max-width:430px;
 max-height:90vh;
 overflow:auto;
 background:var(--panel);
 border:1px solid var(--line);
 border-radius:25px;
 padding:24px;
 box-shadow:0 25px 80px #0008;
}

.modalBox h2{
 margin:0 0 7px;
}

.field{
 margin-top:12px;
}

.field label{
 display:block;
 color:var(--muted);
 font-size:13px;
 margin-bottom:6px;
}

.modalBox input,
.modalBox textarea,
.modalBox select{
 width:100%;
 border:0;
 outline:0;
 border-radius:13px;
 padding:14px;
 background:var(--bubble);
 color:var(--text);
}

.modalBox textarea{
 resize:vertical;
 min-height:90px;
}

.primary{
 width:100%;
 margin-top:14px;
 padding:14px;
 border:0;
 border-radius:14px;
 background:var(--accent);
 color:#05271f;
 font-weight:800;
}

.secondary{
 width:100%;
 margin-top:9px;
 padding:14px;
 border:0;
 border-radius:14px;
 background:var(--bubble);
 color:var(--text);
}

.danger{
 background:var(--danger);
 color:white;
}

.countryRow{
 display:flex;
 gap:8px;
}

.countryRow select{
 width:42%;
}

.countryRow input{
 width:58%;
}

.profile{
 text-align:center;
 margin-bottom:20px;
}

.profile .avatar{
 width:82px;
 height:82px;
 margin:0 auto 10px;
 font-size:34px;
}

.settingRow{
 display:flex;
 align-items:center;
 justify-content:space-between;
 padding:15px 2px;
 border-bottom:1px solid var(--line);
}

.settingText b{
 display:block;
}

.settingText span{
 color:var(--muted);
 font-size:12px;
}

.switch{
 width:45px;
 height:24px;
 accent-color:var(--accent);
}

.loginPage{
 position:fixed;
 inset:0;
 z-index:100;
 background:
 radial-gradient(circle at 20% 20%,#1b806e33,transparent 35%),
 radial-gradient(circle at 80% 80%,#22d3a122,transparent 35%),
 var(--bg);
 display:none;
 align-items:center;
 justify-content:center;
 padding:20px;
}

.loginPage.show{
 display:flex;
}

.loginCard{
 width:100%;
 max-width:430px;
 background:var(--panel);
 border:1px solid var(--line);
 border-radius:30px;
 padding:30px;
 box-shadow:0 30px 100px #0008;
}

.loginBrand{
 text-align:center;
 margin-bottom:25px;
}

.loginBrand .logoIcon{
 margin:auto;
 width:70px;
 height:70px;
 border-radius:22px;
 font-size:28px;
}

.loginBrand .logo{
 margin-top:12px;
 font-size:34px;
}

.loginBrand p{
 color:var(--muted);
}

.note{
 color:var(--muted);
 font-size:11px;
 line-height:1.6;
 text-align:center;
 margin-top:13px;
}

.toast{
 position:fixed;
 bottom:25px;
 left:50%;
 transform:translateX(-50%) translateY(20px);
 background:#13242b;
 color:white;
 padding:12px 18px;
 border-radius:14px;
 opacity:0;
 pointer-events:none;
 transition:.2s;
 z-index:200;
}

.toast.show{
 opacity:1;
 transform:translateX(-50%) translateY(0);
}

@media(max-width:700px){

 .sidebar{
  width:100%;
  min-width:0;
 }

 .main{
  display:none;
 }

 .app.chatOpen .sidebar{
  display:none;
 }

 .app.chatOpen .main{
  display:flex;
 }

 .back{
  display:block;
 }

 .msg{
  max-width:86%;
 }

 .messages{
  padding:16px;
 }

 .top{
  min-height:66px;
 }

 .loginCard{
  padding:23px;
 }
}

@media(min-width:701px){
 .main{
  display:flex!important;
 }
}
</style>
</head>

<body>

<div class="app" id="app">

<aside class="sidebar">

<div class="top">

<div class="brand">
<div class="logoIcon">N</div>
<div>
<div class="logo">NEXA</div>
<div class="small" id="myNumber">غير مسجل</div>
</div>
</div>

<div class="actions">
<button class="icon" onclick="openSettings()">⚙️</button>
<button class="add" onclick="openAdd()">+</button>
</div>

</div>

<div class="search">
<div class="searchBox">
<span>🔎</span>
<input id="search" placeholder="بحث في المحادثات..." oninput="filterContacts(this.value)">
</div>
</div>

<div class="list" id="contacts"></div>

</aside>

<main class="main">

<div class="top">

<div class="chatTop">

<button class="icon back" onclick="goBack()">‹</button>

<div class="avatar" id="chatAvatar">💬</div>

<div class="chatInfo">
<div class="chatName" id="title">NEXA Chat</div>
<div class="small" id="status">اختر محادثة للبدء</div>
</div>

</div>

<button class="icon" onclick="chatMenu()">⋮</button>

</div>

<div class="messages" id="messages">

<div class="emptyChat">

<div class="emptyCard">
<div class="emptyLogo">N</div>
<h2>مرحبًا بك في NEXA 🚀</h2>
<p>محادثاتك، جهات اتصالك وبروفايلك في مكان واحد.</p>
<p>اضغط <b>+</b> لإضافة شخص والبدء.</p>
</div>

</div>

</div>

<div class="composer">
<input id="text" placeholder="اكتب رسالة..." autocomplete="off"
onkeydown="if(event.key==='Enter')sendMessage()">
<button class="send" onclick="sendMessage()">➤</button>
</div>

</main>

</div>


<div class="loginPage" id="loginPage">

<div class="loginCard">

<div class="loginBrand">

<div class="logoIcon">N</div>

<div class="logo">NEXA</div>

<p>تواصل بطريقة مختلفة.</p>

</div>

<div class="field">
<label>الدولة</label>

<div class="countryRow">

<select id="country">
<option value="+212">🇲🇦 المغرب +212</option>
<option value="+966">🇸🇦 السعودية +966</option>
<option value="+213">🇩🇿 الجزائر +213</option>
<option value="+216">🇹🇳 تونس +216</option>
<option value="+33">🇫🇷 فرنسا +33</option>
<option value="+44">🇬🇧 بريطانيا +44</option>
<option value="+1">🇺🇸 أمريكا/كندا +1</option>
<option value="+34">🇪🇸 إسبانيا +34</option>
<option value="+49">🇩🇪 ألمانيا +49</option>
<option value="+39">🇮🇹 إيطاليا +39</option>
<option value="+90">🇹🇷 تركيا +90</option>
<option value="+971">🇦🇪 الإمارات +971</option>
</select></select>

<input id="phone" inputmode="numeric"
placeholder="رقم الهاتف">
</div>
</div>

<div class="field">
<label>اسمك</label>
<input id="name" maxlength="40" placeholder="اكتب اسمك">
</div>

<button class="primary" onclick="login()">دخول إلى NEXA 🚀</button>

<div class="note">
هذا نظام NEXA مستقل وليس تسجيل دخول إلى WhatsApp.
لا تدخل كلمة مرور أو رمز WhatsApp هنا.
</div>

</div>

</div>


<div class="modal" id="modal">
<div class="modalBox" id="modalContent"></div>
</div>

<div class="toast" id="toast"></div>


<script>

const COUNTRIES = [
["+212","🇲🇦","المغرب"],
["+966","🇸🇦","السعودية"],
["+213","🇩🇿","الجزائر"],
["+216","🇹🇳","تونس"],
["+20","🇪🇬","مصر"],
["+971","🇦🇪","الإمارات"],
["+974","🇶🇦","قطر"],
["+965","🇰🇼","الكويت"],
["+973","🇧🇭","البحرين"],
["+968","🇴🇲","عمان"],
["+962","🇯🇴","الأردن"],
["+33","🇫🇷","فرنسا"],
["+44","🇬🇧","بريطانيا"],
["+1","🇺🇸","أمريكا/كندا"],
["+34","🇪🇸","إسبانيا"],
["+49","🇩🇪","ألمانيا"],
["+39","🇮🇹","إيطاليا"],
["+90","🇹🇷","تركيا"],
["+31","🇳🇱","هولندا"],
["+32","🇧🇪","بلجيكا"],
["+41","🇨🇭","سويسرا"],
["+351","🇵🇹","البرتغال"],
["+7","🇷🇺","روسيا"],
["+81","🇯🇵","اليابان"],
["+82","🇰🇷","كوريا الجنوبية"],
["+86","🇨🇳","الصين"],
["+91","🇮🇳","الهند"],
["+61","🇦🇺","أستراليا"],
["+55","🇧🇷","البرازيل"]
];

let me=null;
let current=null;
let contacts=[];
let lastMessageId=0;


function $(id){
 return document.getElementById(id);
}


function toast(text){
 const t=$("toast");
 t.textContent=text;
 t.classList.add("show");
 setTimeout(()=>t.classList.remove("show"),2200);
}


function esc(x){
 return String(x ?? "").replace(/[&<>"']/g,c=>({
  "&":"&amp;",
  "<":"&lt;",
  ">":"&gt;",
  '"':"&quot;",
  "'":"&#039;"
 }[c]));
}


function device(){
 const u=navigator.userAgent;

 if(/Android/i.test(u))return "Android";
 if(/iPhone|iPad|iPod/i.test(u))return "iPhone/iPad";
 if(/Windows/i.test(u))return "Windows";
 if(/Macintosh/i.test(u))return "macOS";
 if(/Linux/i.test(u))return "Linux";

 return "جهاز";
}


async function api(url,opt={}){
 try{
  const r=await fetch(url,opt);
  return await r.json();
 }catch(e){
  toast("تعذر الاتصال بالسيرفر");
  return {ok:false,error:"connection"};
 }
}


function fillCountries(){

 $("country").innerHTML=COUNTRIES.map(c=>
  `<option value="${c[0]}">${c[1]} ${c[2]} ${c[0]}</option>`
 ).join("");

 $("addCountry").innerHTML=COUNTRIES.map(c=>
  `<option value="${c[0]}">${c[1]} ${c[2]} ${c[0]}</option>`
 ).join("");
}


function showLogin(){

 $("loginPage").classList.add("show");

 const saved=localStorage.getItem("nexa_session");

 if(saved){
  try{
   const x=JSON.parse(saved);
   $("phone").value=x.phone?.replace(/^\\+212/,"") || "";
   $("name").value=x.name || "";
  }catch(e){}
 }
}


async function login(){

 let code=$("country").value;
 let phone=$("phone").value.replace(/\D/g,"");
 let name=$("name").value.trim();

 if(!/^\d+$/.test(phone) || phone.length<6 || phone.length>12){
  toast("أدخل رقم هاتف صحيح");
  return;
 }

 if(!name || name.length<2){
  toast("أدخل اسمك");
  return;
 }

 const d=await api("/api/login",{
  method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({
   phone:code+phone,
   name:name,
   device:device()
  })
 });

 if(!d.ok){
  toast(d.error || "فشل تسجيل الدخول");
  return;
 }

 me=d.user;

 localStorage.setItem("nexa_session",JSON.stringify(me));

 $("loginPage").classList.remove("show");

 updateMe();
 loadContacts();

 toast("مرحبًا "+me.name+" 👋");
}


function updateMe(){

 $("myNumber").textContent=
 me.phone+" • "+me.device;

}


async function restore(){
  // لا تدخل مباشرة للحساب القديم عند فتح الموقع
  localStorage.removeItem("nexa_session");

  me=null;
  current=null;

  const page=document.getElementById("loginPage");
  if(page) page.classList.add("show");

  // تنظيف واجهة المحادثات
  const contacts=document.getElementById("contacts");
  if(contacts) contacts.innerHTML="";

  const messages=document.getElementById("messages");
  if(messages){
    messages.innerHTML=`
      <div class="empty">
        <h2>مرحباً في NEXA 🚀</h2>
        <p>سجّل دخولك للبدء</p>
      </div>`;
  }
}

async function loadContacts(){

 if(!me)return;

 const d=await api("/api/contacts?user="+me.id);

 if(!d.contacts){
  contacts=[];
 }else{
  contacts=d.contacts;
 }

 renderContacts(contacts);

}


function renderContacts(list){

 if(!list.length){

  $("contacts").innerHTML=`
  <div class="emptyList">
  لا توجد محادثات بعد<br>
  اضغط <b>+</b> لإضافة رقم
  </div>`;

  return;
 }

 $("contacts").innerHTML=list.map(x=>`

 <div class="person" onclick="openChat(${x.id})">

  <div class="avatar">${esc(x.avatar || "👤")}</div>

  <div class="personInfo">

   <div class="name">${esc(x.name)}</div>

   <div class="preview">
   ${esc(x.bio || x.phone)}
   </div>

  </div>

 </div>

 `).join("");

}


function filterContacts(q){

 q=q.toLowerCase();

 renderContacts(
  contacts.filter(x=>
   (x.name+" "+x.phone+" "+(x.bio||""))
   .toLowerCase()
   .includes(q)
  )
 );

}


function openAdd(){

 $("modalContent").innerHTML=`

 <h2>➕ إضافة جهة اتصال</h2>

 <div class="field">
 <label>الدولة</label>
 <select id="addCountry"></select>
 </div>

 <div class="field">
 <label>رقم الهاتف</label>
 <input id="addPhone" inputmode="numeric"
 placeholder="أدخل الرقم بدون رمز الدولة">
 </div>

 <button class="primary" onclick="doAdd()">إضافة الشخص</button>
 <button class="secondary" onclick="closeModal()">إلغاء</button>

 `;

 $("modal").classList.add("show");

 $("addCountry").innerHTML=COUNTRIES.map(c=>
  `<option value="${c[0]}">${c[1]} ${c[2]} ${c[0]}</option>`
 ).join("");

}


async function doAdd(){

 let code=$("addCountry").value;
 let phone=$("addPhone").value.replace(/\D/g,"");

 if(!/^\d+$/.test(phone) || phone.length<6 || phone.length>12){
  toast("رقم غير صحيح");
  return;
 }

 const d=await api("/api/add",{
  method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({
   user:me.id,
   phone:code+phone
  })
 });

 if(!d.ok){
  toast(d.error || "لم تتم الإضافة");
  return;
 }

 closeModal();
 await loadContacts();

 toast("تمت إضافة جهة الاتصال ✅");

}


async function openChat(id){

 current=id;

 const x=contacts.find(a=>Number(a.id)===Number(id));

 if(!x)return;

 $("title").textContent=x.name;
 $("chatAvatar").textContent=x.avatar || "👤";
 $("status").textContent=x.online ? "متصل الآن" : "غير متصل";

 $("app").classList.add("chatOpen");

 await refreshMessages(true);

}


async function refreshMessages(force=false){

 if(!me || !current)return;

 const d=await api(
  "/api/messages?me="+me.id+"&with="+current
 );

 if(!d.messages)return;

 const messages=d.messages;

 if(!force && messages.length===0)return;

 $("messages").innerHTML=messages.map(x=>{

  const mine=Number(x.sender)===Number(me.id);

  return `

  <div class="msgRow ${mine?"me":"other"}">

   <div class="msg">

    <div class="msgText">
    ${x.deleted ? "<i>تم حذف هذه الرسالة</i>" : esc(x.text)}
    </div>

    <div class="meta">
    ${formatTime(x.created_at)}
    ${mine ? (x.read ? " ✓✓" : " ✓") : ""}
    </div>

   </div>

  </div>

  `;

 }).join("");

 const box=$("messages");
 box.scrollTop=box.scrollHeight;

}


function formatTime(x){

 try{

  return new Date(
   String(x).replace(" ","T")+"Z"
  ).toLocaleTimeString([],{
   hour:"2-digit",
   minute:"2-digit"
  });

 }catch(e){

  return "";

 }

}


async function sendMessage(){

 if(!current){
  toast("اختر محادثة أولًا");
  return;
 }

 const input=$("text");
 const text=input.value.trim();

 if(!text)return;

 input.disabled=true;

 const d=await api("/api/send",{
  method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({
   sender:me.id,
   receiver:current,
   text:text
  })
 });

 input.disabled=false;

 if(!d.ok){
  toast(d.error || "تعذر إرسال الرسالة");
  return;
 }

 input.value="";

 await refreshMessages(true);

}


function goBack(){

 $("app").classList.remove("chatOpen");
 current=null;

}


function closeModal(){

 $("modal").classList.remove("show");

}


function openSettings(){

 $("modalContent").innerHTML=`

 <h2>⚙️ إعدادات NEXA</h2>

 <div class="profile">

  <div class="avatar">${esc(me.avatar||"👤")}</div>

  <h3>${esc(me.name)}</h3>

  <div class="small">${esc(me.phone)}</div>

 </div>

 <div class="settingRow">
  <div class="settingText">
   <b>🌙 الوضع الداكن</b>
   <span>تغيير مظهر NEXA</span>
  </div>
  <input class="switch" type="checkbox"
   ${document.body.classList.contains("light")?"":"checked"}
   onchange="toggleTheme(this)">
 </div>

 <div class="settingRow">
  <div class="settingText">
   <b>📱 الجهاز</b>
   <span>${esc(me.device)}</span>
  </div>
 </div>

 <button class="primary" onclick="editProfile()">
 👤 تعديل البروفايل
 </button>

 <button class="secondary" onclick="closeModal()">
 إغلاق
 </button>

 <button class="primary danger" onclick="logout()">
 🚪 تسجيل الخروج
 </button>

 `;

 $("modal").classList.add("show");

}


function toggleTheme(el){

 document.body.classList.toggle("light",!el.checked);

 localStorage.setItem(
  "nexa_theme",
  el.checked ? "dark" : "light"
 );

}


function loadTheme(){

 const t=localStorage.getItem("nexa_theme");

 if(t==="light")
  document.body.classList.add("light");

}


function editProfile(){

 $("modalContent").innerHTML=`

 <h2>👤 تعديل البروفايل</h2>

 <div class="field">
 <label>الاسم</label>
 <input id="editName" maxlength="40"
 value="${esc(me.name)}">
 </div>

 <div class="field">
 <label>النبذة</label>
 <textarea id="editBio">${esc(me.bio||"")}</textarea>
 </div>

 <div class="field">
 <label>الصورة الرمزية</label>
 <input id="editAvatar" maxlength="4"
 value="${esc(me.avatar||"👤")}">
 </div>

 <button class="primary" onclick="saveProfile()">
 حفظ التغييرات
 </button>

 <button class="secondary" onclick="openSettings()">
 رجوع
 </button>

 `;

}


async function saveProfile(){

 const name=$("editName").value.trim();
 const bio=$("editBio").value.trim();
 const avatar=$("editAvatar").value.trim() || "👤";

 if(name.length<2){
  toast("الاسم قصير جدًا");
  return;
 }

 const d=await api("/api/profile",{
  method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({
   id:me.id,
   name:name,
   bio:bio,
   avatar:avatar
  })
 });

 if(!d.ok){
  toast(d.error || "فشل الحفظ");
  return;
 }

 me=d.user;

 localStorage.setItem(
  "nexa_session",
  JSON.stringify(me)
 );

 updateMe();
 await loadContacts();

 closeModal();

 toast("تم حفظ البروفايل ✅");

}


function logout(){

 if(!confirm("هل تريد تسجيل الخروج؟"))return;

 localStorage.removeItem("nexa_session");

 location.reload();

}


function chatMenu(){

 if(!current)return;

 $("modalContent").innerHTML=`

 <h2>💬 خيارات المحادثة</h2>

 <button class="primary"
 onclick="refreshMessages(true);closeModal()">
 🔄 تحديث
 </button>

 <button class="secondary"
 onclick="closeModal()">
 إلغاء
 </button>

 `;

 $("modal").classList.add("show");

}


$("modal").addEventListener("click",e=>{
 if(e.target===$("modal"))closeModal();
});


loadTheme();
restore();


setInterval(()=>{

 if(me && current)
  refreshMessages(false);

},1200);

</script>

</body>
</html>
'''


class Server(BaseHTTPRequestHandler):

    def send_json(self,data):

        b=json.dumps(
            data,
            ensure_ascii=False
        ).encode()

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )
        self.send_header(
            "Content-Length",
            str(len(b))
        )
        self.send_header(
            "Cache-Control",
            "no-store"
        )
        self.end_headers()

        self.wfile.write(b)


    def body(self):

        try:
            n=int(self.headers.get("Content-Length",0))
            raw=self.rfile.read(n)

            if not raw:
                return {}

            return json.loads(raw)

        except:
            return {}


    def do_GET(self):

        u=urlparse(self.path)
        q=parse_qs(u.query)

        c=conn()

        if u.path=="/":

            b=HTML.encode()

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(b))
            )
            self.end_headers()

            self.wfile.write(b)
            return


        if u.path=="/api/session":

            try:
                uid=int(q.get("id",["0"])[0])
            except:
                uid=0

            row=c.execute(
                "SELECT * FROM users WHERE id=?",
                (uid,)
            ).fetchone()

            if not row:
                return self.send_json({
                    "ok":False,
                    "error":"الجلسة غير موجودة"
                })

            c.execute(
                "UPDATE users SET online=1 WHERE id=?",
                (uid,)
            )

            c.commit()

            return self.send_json({
                "ok":True,
                "user":dict(row)
            })


        if u.path=="/api/contacts":

            try:
                uid=int(q.get("user",["0"])[0])
            except:
                uid=0

            rows=c.execute("""
            SELECT u.*
            FROM users u
            JOIN contacts x
            ON u.id=x.contact_id
            WHERE x.user_id=?
            ORDER BY u.name COLLATE NOCASE
            """,(uid,)).fetchall()

            return self.send_json({
                "contacts":[dict(x) for x in rows]
            })


        if u.path=="/api/messages":

            try:
                a=int(q.get("me",["0"])[0])
                b=int(q.get("with",["0"])[0])
            except:
                return self.send_json({
                    "messages":[]
                })

            c.execute("""
            UPDATE messages
            SET read=1
            WHERE sender=? AND receiver=?
            """,(b,a))

            c.commit()

            rows=c.execute("""
            SELECT *
            FROM messages
            WHERE
            (sender=? AND receiver=?)
            OR
            (sender=? AND receiver=?)
            ORDER BY id ASC
            """,(a,b,b,a)).fetchall()

            return self.send_json({
                "messages":[dict(x) for x in rows]
            })


        self.send_response(404)
        self.end_headers()


    def do_POST(self):

        c=conn()
        d=self.body()

        if self.path=="/api/login":

            phone=re.sub(
                r"\D",
                "",
                str(d.get("phone",""))
            )

            name=str(
                d.get("name","")
            ).strip()

            dev=str(
                d.get("device","جهاز")
            )

            if len(phone)<7 or len(phone)>15:

                return self.send_json({
                    "ok":False,
                    "error":"رقم الهاتف غير صحيح"
                })


            if not name:

                return self.send_json({
                    "ok":False,
                    "error":"اكتب اسمك"
                })


            phone="+"+phone

            row=c.execute(
                "SELECT * FROM users WHERE phone=?",
                (phone,)
            ).fetchone()


            if row:

                c.execute("""
                UPDATE users
                SET name=?,
                    online=1,
                    device=?
                WHERE id=?
                """,(
                    name,
                    dev,
                    row["id"]
                ))

                uid=row["id"]

            else:

                cur=c.execute("""
                INSERT INTO users(
                    phone,
                    name,
                    online,
                    device
                )
                VALUES(?,?,1,?)
                """,(
                    phone,
                    name,
                    dev
                ))

                uid=cur.lastrowid


            c.commit()


            row=c.execute(
                "SELECT * FROM users WHERE id=?",
                (uid,)
            ).fetchone()


            return self.send_json({
                "ok":True,
                "user":dict(row)
            })


        if self.path=="/api/add":

            phone=re.sub(
                r"\D",
                "",
                str(d.get("phone",""))
            )

            uid=int(d.get("user",0))

            if len(phone)<7 or len(phone)>15:

                return self.send_json({
                    "ok":False,
                    "error":"رقم الهاتف غير صحيح"
                })


            phone="+"+phone


            row=c.execute(
                "SELECT * FROM users WHERE phone=?",
                (phone,)
            ).fetchone()


            if not row:

                return self.send_json({
                    "ok":False,
                    "error":"هذا الرقم غير مسجل في NEXA"
                })


            if row["id"]==uid:

                return self.send_json({
                    "ok":False,
                    "error":"لا يمكنك إضافة نفسك"
                })


            c.execute(
                "INSERT OR IGNORE INTO contacts VALUES(?,?)",
                (uid,row["id"])
            )

            c.execute(
                "INSERT OR IGNORE INTO contacts VALUES(?,?)",
                (row["id"],uid)
            )

            c.commit()


            return self.send_json({
                "ok":True
            })


        if self.path=="/api/send":

            try:
                sender=int(d.get("sender"))
                receiver=int(d.get("receiver"))
            except:

                return self.send_json({
                    "ok":False,
                    "error":"حساب غير صحيح"
                })


            text=str(
                d.get("text","")
            ).strip()


            if not text:

                return self.send_json({
                    "ok":False,
                    "error":"الرسالة فارغة"
                })


            if len(text)>5000:

                return self.send_json({
                    "ok":False,
                    "error":"الرسالة طويلة جدًا"
                })


            exists=c.execute(
                "SELECT id FROM users WHERE id=?",
                (receiver,)
            ).fetchone()


            if not exists:

                return self.send_json({
                    "ok":False,
                    "error":"المستخدم غير موجود"
                })


            c.execute("""
            INSERT INTO messages(
                sender,
                receiver,
                text
            )
            VALUES(?,?,?)
            """,(
                sender,
                receiver,
                text
            ))

            c.commit()


            return self.send_json({
                "ok":True
            })


        if self.path=="/api/profile":

            try:
                uid=int(d.get("id"))
            except:

                return self.send_json({
                    "ok":False,
                    "error":"حساب غير صحيح"
                })


            name=str(
                d.get("name","")
            ).strip()[:40]

            bio=str(
                d.get("bio","")
            ).strip()[:200]

            avatar=str(
                d.get("avatar","👤")
            ).strip()[:8]


            if not name:
                name="NEXA User"


            if not avatar:
                avatar="👤"


            c.execute("""
            UPDATE users
            SET name=?,
                bio=?,
                avatar=?
            WHERE id=?
            """,(
                name,
                bio,
                avatar,
                uid
            ))

            c.commit()


            row=c.execute(
                "SELECT * FROM users WHERE id=?",
                (uid,)
            ).fetchone()


            if not row:

                return self.send_json({
                    "ok":False,
                    "error":"المستخدم غير موجود"
                })


            return self.send_json({
                "ok":True,
                "user":dict(row)
            })


        return self.send_json({
            "ok":False,
            "error":"Not found"
        })


conn()

print("")
print("🚀 NEXA Chat v3")
print("🌐 http://127.0.0.1:8080")
print("")

import os

PORT=int(os.environ.get("PORT","8080"))

ThreadingHTTPServer(
    ("0.0.0.0",PORT),
    Server
).serve_forever()
