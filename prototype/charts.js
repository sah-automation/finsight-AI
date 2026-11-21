/* Prototype only: tiny SVG chart helpers. The real app gets data from the API; figures are never calculated in the UI. */
(function(){
var W=640,H=220,L=52,R=24,T=28,B=32,FF='Inter, Arial, sans-serif';
/* Phones: draw at the real width so text stays 11 to 12px instead of shrinking with the SVG */
function narrow(){return window.innerWidth<=640}
function setW(){var w=window.innerWidth;W=narrow()?Math.max(280,Math.min(560,w-72)):640;L=narrow()?40:52;R=narrow()?16:24}
function ql(s){return narrow()?String(s).replace(/Q(\d) 20(\d\d)/,'Q$1 $2'):s}
function num(v,d){return new Intl.NumberFormat('en-US',{minimumFractionDigits:d==null?1:d,maximumFractionDigits:d==null?1:d}).format(v).replace('-','−')}
function fmt(t,v){return t==='pct'?num(v,1)+'%':t==='days'?num(v,0)+' days':t==='months'?num(v,1)+' months':num(v,1)}
function tick(t,v){return t==='pct'?num(v,0)+'%':t==='days'||t==='months'?num(v,0):num(v,0)}
function svg(inner,w,h,aria){return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+w+' '+h+'" width="'+w+'" height="'+h+'" role="img" aria-label="'+aria+'" font-family="'+FF+'" style="width:100%;height:auto">'+inner+'</svg>'}
function grid(lo,hi,y,o){var s='';for(var i=0;i<4;i++){var t=lo+(hi-lo)*i/3;s+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y(t)+'" y2="'+y(t)+'" stroke="var(--border-subtle)"/><text x="'+(L-8)+'" y="'+(y(t)+4)+'" text-anchor="end" fill="var(--text-muted)" font-size="11">'+tick(o.t,t)+'</text>'}return s}
function line(o){setW();var v=o.values,n=v.length,lo=Math.min.apply(0,v),hi=Math.max.apply(0,v),p=(hi-lo)*.25||1,y0=lo-p,y1=hi+p;
 var x=function(i){return L+i*(W-L-R)/Math.max(n-1,1)},y=function(a){return T+(y1-a)*(H-T-B)/(y1-y0)};
 var pts=v.map(function(a,i){return x(i)+','+y(a)}).join(' '),d='';
 v.forEach(function(a,i){var l=i===n-1,showv=!narrow()||n<=5||(n-1-i)%2===0;d+='<circle cx="'+x(i)+'" cy="'+y(a)+'" r="'+(l?5:3.5)+'" fill="'+(l?'var(--accent)':'var(--bg-surface)')+'" stroke="var(--accent)" stroke-width="2"/>'+(showv?'<text x="'+x(i)+'" y="'+(y(a)-12)+'" text-anchor="middle" font-size="12" font-weight="600" fill="var(--text-primary)">'+fmt(o.t,a)+'</text>':'')+'<text x="'+x(i)+'" y="'+(H-10)+'" text-anchor="middle" font-size="11" fill="var(--text-muted)">'+ql(o.labels[i])+'</text>'});
 return svg(grid(y0,y1,y,o)+'<polyline points="'+pts+'" fill="none" stroke="var(--accent)" stroke-width="2"/>'+d,W,H,o.aria)}
function bars(o){setW();var v=o.values,n=v.length,hi=Math.max.apply(0,v)*1.15,y=function(a){return T+(hi-a)*(H-T-B)/hi},bw=Math.min(64,(W-L-R)/n*.55),s=grid(0,hi,y,o);
 v.forEach(function(a,i){var cx=L+(i+.5)*(W-L-R)/n,hl=(o.hi==null?n-1:o.hi)===i;
  s+='<rect x="'+(cx-bw/2)+'" y="'+y(a)+'" width="'+bw+'" height="'+(y(0)-y(a))+'" rx="3" fill="var(--accent)" fill-opacity="'+(hl?1:.35)+'"/><text x="'+cx+'" y="'+(y(a)-8)+'" text-anchor="middle" font-size="12" font-weight="600" fill="var(--text-primary)">'+fmt(o.t,a)+'</text><text x="'+cx+'" y="'+(H-10)+'" text-anchor="middle" font-size="11" fill="var(--text-muted)">'+ql(o.labels[i])+'</text>'});
 return svg(s,W,H,o.aria)}
function hbars(o){setW();var it=o.items,nr=narrow(),note=it.some(function(a){return a.note}),rh=nr?(note?62:46):40,h=it.length*rh+16,x0=nr?8:190,x1=nr?W-108:W-110,neg=it.some(function(a){return a.v<0}),mx=Math.max.apply(0,it.map(function(a){return Math.abs(a.v)})),z=neg?(x0+x1)/2:x0,sc=(neg?(x1-x0)/2:(x1-x0))/mx,s='';
 if(neg)s+='<line x1="'+z+'" x2="'+z+'" y1="4" y2="'+(h-4)+'" stroke="var(--border-strong)"/>';
 it.forEach(function(a,i){var top=8+i*rh,cy=nr?top+(note?44:30):top+rh/2,w=Math.abs(a.v)*sc,bx=a.v<0?z-w:z,col=a.tone==='bad'?'var(--negative)':a.tone==='good'?'var(--positive)':'var(--accent)',tx=a.v<0?bx-8:bx+w+8;
  if(nr)s+='<text x="0" y="'+(top+14)+'" font-size="13" fill="var(--text-primary)">'+a.label+'</text>'+(a.note?'<text x="0" y="'+(top+29)+'" font-size="11" fill="var(--text-muted)">'+a.note+'</text>':'');
  else s+='<text x="0" y="'+(cy-(a.note?2:-4))+'" font-size="13" fill="var(--text-primary)">'+a.label+'</text>'+(a.note?'<text x="0" y="'+(cy+12)+'" font-size="11" fill="var(--text-muted)">'+a.note+'</text>':'');
  s+='<rect x="'+bx+'" y="'+(cy-9)+'" width="'+Math.max(w,2)+'" height="18" rx="3" fill="'+col+'"/><text x="'+tx+'" y="'+(cy+4)+'" text-anchor="'+(a.v<0?'end':'start')+'" font-size="12" font-weight="600" fill="var(--text-primary)">'+a.text+'</text>'});
 return svg(s,W,h,o.aria)}
function spark(v){var w=96,h=28,lo=Math.min.apply(0,v),r=(Math.max.apply(0,v)-lo)||1,p=v.map(function(a,i){return [2+i*(w-4)/(v.length-1),h-3-(a-lo)*(h-6)/r]}),l=p[p.length-1];
 return '<svg viewBox="0 0 96 28" width="96" height="28" aria-hidden="true"><polyline points="'+p.map(function(a){return a[0].toFixed(1)+','+a[1].toFixed(1)}).join(' ')+'" fill="none" stroke="var(--text-muted)" stroke-width="1.5"/><circle cx="'+l[0]+'" cy="'+l[1]+'" r="2.5" fill="var(--accent)"/></svg>'}
function table(h,rows,right){return '<div class="fig"><table><thead><tr>'+h.map(function(c,i){return '<th scope="col" class="'+(right.indexOf(i)>-1?'r':'')+'">'+c+'</th>'}).join('')+'</tr></thead><tbody>'+rows.map(function(r){return '<tr>'+r.map(function(c,i){return '<td class="'+(right.indexOf(i)>-1?'r num':'')+'">'+c+'</td>'}).join('')+'</tr>'}).join('')+'</tbody></table></div>'}
function card(o){return '<figure class="fcard" data-title="'+o.title+'"><div class="fh"><div><b>'+o.title+'</b><span>'+o.sub+'</span></div><div class="fa"><div class="seg2" role="group" aria-label="Chart or table"><button data-v="chart" aria-pressed="true">Chart</button><button data-v="table" aria-pressed="false">Table</button></div>'+(o.exp?'<button class="btn sm" data-x="png">Image</button><button class="btn sm" data-x="pdf">PDF</button>':'')+'</div></div><div class="cv">'+o.svg+'</div><div class="ct hidden">'+o.table+'</div>'+(o.cap?'<figcaption>'+o.cap+'</figcaption>':'')+'</figure>'}
function png(s,name){var cs=getComputedStyle(document.documentElement),x=new XMLSerializer().serializeToString(s).replace(/var\((--[\w-]+)\)/g,function(m,n){return cs.getPropertyValue(n).trim()||'#000'}),vb=s.viewBox.baseVal,c=document.createElement('canvas'),k=2;
 c.width=vb.width*k;c.height=vb.height*k;var im=new Image();im.onload=function(){var g=c.getContext('2d');g.fillStyle='#fff';g.fillRect(0,0,c.width,c.height);g.drawImage(im,0,0,c.width,c.height);c.toBlob(function(b){var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name+'.png';a.click()})};
 im.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(x)}
function bind(root,done){root.addEventListener('click',function(e){var b=e.target.closest('[data-v],[data-x]'),c=b&&b.closest('.fcard');if(!c)return;
 if(b.dataset.v){var ch=b.dataset.v==='chart';c.querySelector('.cv').classList.toggle('hidden',!ch);c.querySelector('.ct').classList.toggle('hidden',ch);b.parentNode.querySelectorAll('button').forEach(function(x){x.setAttribute('aria-pressed',x===b)})}
 else if(b.dataset.x==='png'){png(c.querySelector('svg'),(c.dataset.title||'chart').replace(/\W+/g,'-').toLowerCase());done&&done('Image saved.')}
 else{c.classList.add('print-target');window.print();setTimeout(function(){c.classList.remove('print-target')},500)}})}
window.FC={num:num,fmt:fmt,line:line,bars:bars,hbars:hbars,spark:spark,table:table,card:card,bind:bind,narrow:narrow};
})();
