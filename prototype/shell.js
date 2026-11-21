/* Prototype only: shared sidebar, role preview, phone menu, command menu and shortcuts help.
   The real app gets the role from the API. */
(function(){
var KEY='fs_role',P={admin:{n:'Priya Nair',r:'System Admin',i:'PN'},audit:{n:'Daniel Okoye',r:'Audit & Compliance',i:'DO'},fin:{n:'Asha Kapoor',r:'Corporate Finance & Planners',i:'AK'},exec:{n:'Rohan Mehta',r:'Executive Leadership',i:'RM'}};
function get(){try{var v=sessionStorage.getItem(KEY);return P[v]?v:'fin'}catch(e){return 'fin'}}
var role=get(),adm=role==='admin',can={ask:!adm,docs:true,dash:!adm,charts:!adm,reports:!adm,upload:role==='fin',users:adm,audit:adm||role==='audit',cost:adm||role==='exec'};
var HOME={admin:'settings.html#profile',exec:'dashboard.html',fin:'ask.html',audit:'ask.html'};
var MAC=typeof navigator!=='undefined'&&/Mac|iPhone|iPad/.test(navigator.platform||navigator.userAgent||''),MOD=MAC?'⌘':'Ctrl';
function sym(id,d){return '<symbol id="fs-'+id+'" viewBox="0 0 24 24">'+d+'</symbol>'}
var SP='<svg width="0" height="0" style="position:absolute"><defs>'+
sym('chat','<path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-5.4A8 8 0 1 1 21 12z"/>')+
sym('doc','<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6"/>')+
sym('up','<path d="M12 16V4M7 9l5-5 5 5M5 20h14"/>')+
sym('gear','<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/>')+
sym('chev','<path d="M9 6l6 6-6 6"/>')+
sym('dash','<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>')+
sym('chart','<path d="M4 20V10M10 20V4M16 20v-8M2 20h20"/>')+
sym('rep','<path d="M8 3v3M16 3v3M4 8h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM8 13h4M8 16h8"/>')+
sym('lock','<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>')+
sym('menu','<path d="M4 7h16M4 12h16M4 17h16"/>')+
sym('search','<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>')+
sym('x','<path d="M6 6l12 12M18 6 6 18"/>')+'</defs></svg>';
function ic(n){return '<svg class="i"><use href="#fs-'+n+'"/></svg>'}
function $(id){return document.getElementById(id)}

/* overlays (command menu, shortcuts help) */
var ovOpen=false,prev=null;
function showOv(html){var o=$('fs-ov');prev=document.activeElement;o.innerHTML=html;o.hidden=false;ovOpen=true}
function closeOv(){if(!ovOpen)return;var o=$('fs-ov');o.hidden=true;o.innerHTML='';ovOpen=false;if(prev&&prev.focus)prev.focus()}
function items(){var a=[];function add(g,t,f){a.push({g:g,t:t,f:f})}function go(u){return function(){location.href=u}}
 if(can.dash)add('Go to','Dashboard',go('dashboard.html'));
 if(can.ask)add('Go to','Ask',go('ask.html'));
 if(can.charts)add('Go to','Charts',go('charts.html'));
 if(can.reports)add('Go to','Reports',go('reports.html'));
 if(can.docs)add('Go to','Documents',go('documents.html'));
 if(can.upload)add('Go to','Upload document',go('upload.html'));
 add('Settings','Profile',go('settings.html#profile'));add('Settings','Notifications',go('settings.html#notifications'));
 if(can.users)add('Settings','Users',go('settings.html#users'));
 if(can.audit)add('Settings','Audit log',go('settings.html#audit'));
 if(can.cost)add('Settings','Cost view',go('settings.html#cost'));
 add('Help','Keyboard shortcuts',openHelp);add('Account','Sign out',go('login.html'));return a}
function openCmd(){var all=items(),cur=0,list=[];
 showOv('<div class="cm" role="dialog" aria-modal="true" aria-label="Command menu"><input id="fs-ci" role="combobox" aria-expanded="true" aria-controls="fs-cl" aria-autocomplete="list" placeholder="Search pages and actions" autocomplete="off"><ul class="cl" id="fs-cl" role="listbox" aria-label="Commands"></ul><div class="ch2">Up and down to move, Enter to open, Esc to close</div></div>');
 var inp=$('fs-ci'),ul=$('fs-cl');
 function draw(){var q=inp.value.trim().toLowerCase();list=all.filter(function(x){return !q||(x.t+' '+x.g).toLowerCase().indexOf(q)>-1});if(cur>=list.length)cur=0;
  ul.innerHTML=list.length?list.map(function(x,i){return '<li role="option" id="fs-o'+i+'" aria-selected="'+(i===cur)+'" data-i="'+i+'"><span>'+x.t+'</span><small>'+x.g+'</small></li>'}).join(''):'<li class="no" role="presentation">No matching commands.</li>';
  inp.setAttribute('aria-activedescendant',list.length?'fs-o'+cur:'');var s=ul.querySelector('[aria-selected=true]');if(s&&s.scrollIntoView)s.scrollIntoView({block:'nearest'})}
 function run(i){var x=list[i];if(x){closeOv();x.f()}}
 inp.oninput=function(){cur=0;draw()};
 inp.onkeydown=function(e){if(e.key==='ArrowDown'){e.preventDefault();cur=Math.min(cur+1,list.length-1);draw()}else if(e.key==='ArrowUp'){e.preventDefault();cur=Math.max(cur-1,0);draw()}else if(e.key==='Enter'){e.preventDefault();run(cur)}else if(e.key==='Tab')e.preventDefault()};
 ul.onclick=function(e){var li=e.target.closest('li[data-i]');if(li)run(+li.getAttribute('data-i'))};
 draw();inp.focus()}
function openHelp(){var rows=[['/','Focus the question box (Ask page)'],['Esc','Close a panel, menu or dialog'],['J','Next citation in the source viewer'],['K','Previous citation in the source viewer'],[MOD+' K','Open the command menu'],['?','Show this help']];
 showOv('<div class="cm hp" role="dialog" aria-modal="true" aria-labelledby="fs-ht"><div class="hh"><h2 id="fs-ht">Keyboard shortcuts</h2><button class="ib" id="fs-hc" type="button" aria-label="Close shortcuts help">'+ic('x')+'</button></div><table><tbody>'+
  rows.map(function(r){return '<tr><td>'+r[0].split(' ').map(function(k){return '<kbd>'+k+'</kbd>'}).join('')+'</td><td>'+r[1]+'</td></tr>'}).join('')+'</tbody></table></div>');
 var c=$('fs-hc');c.onclick=closeOv;c.onkeydown=function(e){if(e.key==='Tab')e.preventDefault()};c.focus()}

/* collapsible sidebar (desktop). The preference is a UI setting, not company data. */
var SK='fs_side';
function isCol(){return document.documentElement.getAttribute('data-side')==='collapsed'}
function setSide(c,keep){document.documentElement.setAttribute('data-side',c?'collapsed':'open');
 if(!keep){try{localStorage.setItem(SK,c?'1':'0')}catch(e){}}
 var b=$('fs-sb');if(b){b.setAttribute('aria-expanded',!c);b.setAttribute('aria-label',c?'Expand sidebar':'Collapse sidebar');b.title=c?'Expand sidebar':'Collapse sidebar'}
 var l=document.querySelectorAll('#side .nav a,#side .gb');for(var i=0;i<l.length;i++){if(c)l[i].title=l[i].getAttribute('aria-label')||'';else l[i].removeAttribute('title')}}

/* phone menu */
function drawer(open){var s=$('side'),b=$('fs-mb');if(!s||!b)return;var was=s.classList.contains('open');s.classList.toggle('open',open);$('fs-sc').classList.toggle('on',open);
 b.setAttribute('aria-expanded',open);b.setAttribute('aria-label',open?'Close menu':'Open menu');
 if(open){var a=s.querySelector('.sclose,a,button');if(a)a.focus()}else if(was)b.focus()}

/* phone tables: tables with 4+ columns inside .tw turn into cards (see styles.css).
   Labels come from the header cells, so the page code does not need to change. */
function cardify(){var ts=document.querySelectorAll('.tw table');
 for(var i=0;i<ts.length;i++){var t=ts[i],hs=t.querySelectorAll('thead th');if(hs.length<4)continue;
  var tw=t.closest('.tw');tw.classList.add('cards');
  var labs=[].map.call(hs,function(h){return h.querySelector('.sr')?'':h.textContent.trim()}),rows=t.querySelectorAll('tbody tr');
  for(var r=0;r<rows.length;r++){var tds=rows[r].children;if(tds.length!==labs.length)continue;
   for(var c=0;c<tds.length;c++){var td=tds[c];if(c===0)td.classList.add('k-t');
    else if(!labs[c])td.classList.add('k-x');
    else if(td.getAttribute('data-l')!==labs[c])td.setAttribute('data-l',labs[c])}}}}
var cq=0;function queueCards(){if(cq)return;cq=setTimeout(function(){cq=0;cardify()},30)}

function mount(o){o=o||{};var cur=o.current;
 document.body.classList.add('has-mbar');
 document.body.insertAdjacentHTML('afterbegin',SP+'<div class="mbar"><button class="ib" id="fs-mb" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="side">'+ic('menu')+'</button><div class="brand"><span class="mark" aria-hidden="true">F</span>FinSight AI</div><button class="ib" id="fs-ms" type="button" aria-label="Search pages and actions" style="margin-left:auto">'+ic('search')+'</button></div><div class="scrim2" id="fs-sc"></div>');
 document.body.insertAdjacentHTML('beforeend','<div class="ov" id="fs-ov" hidden></div>');
 var links=[['ask.html','chat','Ask',can.ask,'ask'],['dashboard.html','dash','Dashboard',can.dash,'dashboard'],['charts.html','chart','Charts',can.charts,'charts'],['reports.html','rep','Reports',can.reports,'reports'],['documents.html','doc','Documents',can.docs,'documents'],['upload.html','up','Upload',can.upload,'upload']].filter(function(x){return x[3]}).map(function(x){return '<a href="'+x[0]+'"'+(cur===x[4]?' aria-current="page"':'')+' aria-label="'+x[2]+'">'+ic(x[1])+'<span class="fs-lb">'+x[2]+'</span></a>'}).join('');
 var secs=[['profile','Profile',true],['notifications','Notifications',true],['users','Users',can.users],['audit','Audit log',can.audit],['cost','Cost view',can.cost]].filter(function(s){return s[2]}).map(function(s){return '<a href="settings.html#'+s[0]+'">'+s[1]+'</a>'}).join('');
 var opts=Object.keys(P).map(function(k){return '<option value="'+k+'"'+(k===role?' selected':'')+'>'+P[k].r.replace('&','&amp;')+'</option>'}).join('');
 var p=P[role];
 $('side').innerHTML='<button class="sbt" id="fs-sb" type="button" aria-controls="side" aria-expanded="true" aria-label="Collapse sidebar">'+ic('chev')+'</button><button class="ib sclose" id="fs-xc" type="button" aria-label="Close menu">'+ic('x')+'</button><div><div class="brand"><span class="mark" aria-hidden="true">F</span><span class="fs-bt">FinSight AI</span></div><div class="co">Northwind Traders Ltd</div></div>'+
 '<button class="cmdk" id="fs-ck" type="button" aria-label="Search pages and actions">'+ic('search')+'<span class="fs-lb">Search</span><kbd>'+MOD+' K</kbd></button>'+
 '<nav class="nav" style="flex:none">'+links+'<div class="grp"><button class="gb" id="fs-g" aria-expanded="'+(cur==='settings')+'" aria-controls="fs-s" aria-label="Settings"'+(cur==='settings'?' aria-current="page"':'')+'>'+ic('gear')+'<span class="fs-lb">Settings</span>'+ic('chev')+'</button><div class="subs" id="fs-s"'+(cur==='settings'?'':' hidden')+'>'+secs+'</div></div></nav>'+
 '<div class="slot" id="fs-slot"></div>'+
 '<button class="kbh" id="fs-kh" type="button"><span>Keyboard shortcuts</span><kbd>?</kbd></button>'+
 '<div class="user"><span class="av" aria-hidden="true">'+p.i+'</span><div><b id="fs-un">'+p.n+'</b><span>'+p.r.replace('&','&amp;')+'</span></div></div>'+
 '<div class="pv" id="pv"><label for="fs-role">Preview as</label><select class="input" id="fs-role">'+opts+'</select></div>';
 $('fs-g').onclick=function(){var s=$('fs-s');if(isCol()){setSide(false);s.hidden=false;this.setAttribute('aria-expanded',true);return}var x=s.hidden;s.hidden=!x;this.setAttribute('aria-expanded',x)};
 var sv='0';try{sv=localStorage.getItem(SK)||'0'}catch(e){}
 setSide(sv==='1',true);$('fs-sb').onclick=function(){setSide(!isCol())};
 $('fs-role').onchange=function(){try{sessionStorage.setItem(KEY,this.value)}catch(e){}location.reload()};
 $('fs-ck').onclick=openCmd;$('fs-ms').onclick=openCmd;$('fs-kh').onclick=openHelp;
 $('fs-mb').onclick=function(){drawer(!$('side').classList.contains('open'))};
 $('fs-xc').onclick=function(){drawer(false)};
 $('fs-sc').onclick=function(){drawer(false)};
 $('side').addEventListener('click',function(e){if(e.target.closest('a')&&$('side').classList.contains('open'))drawer(false)});
 $('fs-ov').onclick=function(e){if(e.target===this)closeOv()};
 /* phone tables become cards: run now and whenever a page redraws its tables */
 cardify();new MutationObserver(queueCards).observe(document.body,{childList:true,subtree:true});
 /* prototype only: charts are drawn for the current width, so redraw (reload) when the phone/desktop size class changes */
 var sm=innerWidth<=640,rt;addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(function(){if(window.FC&&(innerWidth<=640)!==sm)location.reload()},250)});
}
function deny(main){var lab=role==='admin'?'Go to Settings':role==='exec'?'Go to Dashboard':'Go to Ask';
 main.innerHTML='<div class="deny"><span class="dic">'+ic('lock')+'</span><h1>You don’t have access to this.</h1><p>Your role, '+P[role].r.replace('&','&amp;')+', can’t open this page. If you think this is a mistake, ask your administrator.</p><div class="drow"><a class="btn btn-primary" href="'+HOME[role]+'">'+lab+'</a><button class="btn" onclick="history.back()">Go back</button></div></div>'}
function setUser(n){$('fs-un').textContent=n}

/* global shortcuts */
document.addEventListener('keydown',function(e){
 var t=e.target,typing=/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)||t.isContentEditable;
 if((e.metaKey||e.ctrlKey)&&(e.key||'').toLowerCase()==='k'){e.preventDefault();if(ovOpen)closeOv();else if($('fs-ov'))openCmd();return}
 if(e.key==='Escape'){if(ovOpen){e.stopPropagation();closeOv();return}var s=$('side');if(s&&s.classList.contains('open')){e.stopPropagation();drawer(false)}return}
 if(ovOpen||typing||e.metaKey||e.ctrlKey||e.altKey)return;
 if(e.key==='?'){e.preventDefault();if($('fs-ov'))openHelp()}
 else if(e.key==='/'){var q=$('ta');if(q){e.preventDefault();q.focus()}}
 else if(e.key==='j'||e.key==='k'){var pn=$('panel'),tabs=[].slice.call(document.querySelectorAll('[data-tab]'));
  if(pn&&pn.classList.contains('open')&&tabs.length){var i=-1;tabs.forEach(function(b,k){if(b.getAttribute('aria-selected')==='true')i=k});var n=e.key==='j'?i+1:i-1;if(tabs[n])tabs[n].click()}}
});
window.FS={role:role,can:can,home:HOME[role],persona:P[role],mount:mount,deny:deny,setUser:setUser,ic:ic,openCmd:openCmd,openHelp:openHelp};
})();
