/* v9 search (round 4): engine + UI, built by r4/srcA/apply_search.py */
/* PCS-ENGINE-BEGIN */
var PCS_ENGINE=(function(){
"use strict";
var PCS_ALIAS=
"tnf,northface,north face>the north face|north face;cg>canada goose;lv,luis vuitton,louis vutton>louis vuitton;"+
"rl,polo ralph,ralph>ralph lauren;ysl,st laurent>saint laurent|ysl;cdg>comme des garcons;nb,new balence>new balance;"+
"yzy,yeezys,yezzy>yeezy;fog>fear of god|essentials;ggdb>golden goose;gg>gucci;ald>aime leon dore;cp>cp company;"+
"si,stoney>stone island;mm,mmm,margiela,margela>maison margiela|margiela;bv,bottega>bottega veneta;lp,loropiana>loro piana;"+
"ch>chrome hearts;gd,gallery department>gallery dept;bp>broken planet;ow,offwhite,off white>off white;"+
"pa>palm angels;dt>denim tears;ua>under armour;arc,arcteryx,arcterix>arcteryx;balenci,bal,balenciga,balenchiaga>balenciaga;"+
"lulu>lululemon;crtz,cortiez,corteis>corteiz;ee>eric emanuel;vw,westwood>vivienne westwood;ro,rick>rick owens;"+
"tb>thom browne;ck>calvin klein;th,tommy>tommy hilfiger;mk>michael kors;pj,pjs>parajumpers;sp5,spider>sp5der;"+
"hell star>hellstar;trap star>trapstar;ami paris>ami;uggs>ugg;hermès>hermes;jordans>jordan;"+
"monclear,moncller>moncler;burbery,burberrys>burberry;gucchi>gucci;pradda>prada;stussey>stussy;"+
"addidas,adiddas>adidas;lacost>lacoste;hokka>hoka;goyarde>goyard;essentails>essentials;carhart>carhartt;salomons>salomon;"+
"af1>air force 1;aj1,j1>jordan 1;aj4,j4>jordan 4;aj3,j3>jordan 3;aj11,j11>jordan 11;tn,tns>air max plus;"+
"am95>air max 95;am90>air max 90;tech>tech fleece;nuptse,1996>nuptse;ts,triple s>triple s;350>yeezy 350;"+
"foam>foam runner;2002>2002r;gat>replica;"+
"dunjakke,boblejakke,dunjacka,dynejakke,daunenjacke,pufferjacke,doudoune,plumifero,anorak>puffer;"+
"skjorte,skjorta,hemd,chemise,camisa>shirt;t-skjorte,tskjorte>t shirt;lue,mössa,hue,mütze,bonnet,gorro>beanie;"+
"caps,keps,kappe>cap;sekk,ryggsekk,ryggsäck,rygsæk,rucksack,sac a dos,mochila>backpack;"+
"lommebok,plånbok,pung,geldbörse,portemonnaie,portefeuille,cartera>wallet;klokke,klocka,ur,uhr,montre,reloj>watch;"+
"solbriller,solglasögon,sonnenbrille,lunettes de soleil,gafas de sol>sunglasses;"+
"joggebukse,mjukisbyxor,jogginghose>sweatpants|joggers;træningsbukser,pantalon de chandal>sweatpants;"+
"treningsdress,träningsoverall,træningsdragt,trainingsanzug,survetement,chandal>tracksuit;jogging>sweatpants|joggers|tracksuit;"+
"olabukse,dongeribukse,jean,vaqueros>jeans;støvler,stövlar,stiefel,bottes,botas>boots;sandaler>sandals|slides;"+
"skjerf,halsduk,tørklæde,schal,echarpe,bufanda>scarf;kjede,halskjede,halskette,kette>necklace|chain;"+
"halsband,halskæde,collier,collar>necklace;armbånd,armband,pulsera>bracelet;"+
"frakk,kåpe,kappa,rock,frakke,mantel,manteau,abrigo>coat;vest,weste,chaleco>vest|gilet;väst>vest;gilet>gilet|vest;"+
"turnschuhe>sneaker;pull>sweater|hoodie;sweat a capuche,sudadera con capucha>hoodie;short>shorts;"+
"claquettes,chanclas>slides;slides>slides;"+
"gray>grey;grey>gray;svart,sort,schwarz,noir,negro,nero,zwart,negra,nera,noire,schwarze,schwarzer,黑>black;hvit,vit,hvid,weiss,blanc,blanco,bianco,wit,blanca,bianca,blanche,weisse,白>white;"+
"grå,grau,gris,grigio,grijs,grise,灰>grey;blå,blau,bleu,azul,blu,blauw,bleue,蓝>blue;marine,marineblå,marinblå,marino>navy;"+
"rød,röd,rot,rouge,rojo,rosso,rood,roja,rossa,rote,roter,红>red;grønn,grön,grøn,grün,vert,verde,groen,verte,绿>green;"+
"brun,braun,marron,marrone,bruin>brown;rosa,rose,roze,粉>pink;gul,gelb,jaune,amarillo,giallo,geel,amarilla,gialla>yellow;"+
"lilla,lila,violet,morado,viola,paars,morada>purple";
var TYPES="hoodie sweater sweatshirt crewneck knit jacket puffer coat vest gilet parka windbreaker shirt tee polo "+
"pants trousers jeans cargo sweatpants joggers shorts tracksuit sneaker sneakers trainer shoe shoes boots slides sandals "+
"loafers beanie cap hat bucket bag backpack wallet belt watch sunglasses scarf necklace bracelet ring earring chain "+
"outerwear";
var W=[1.3,1.0,0.8,0.7,0.3];
var CJK=/[㐀-鿿]/;
function fold(s){
s=String(s==null?"":s).toLowerCase();
if(!/[^\x00-\x7f]/.test(s))return s.replace(/['`]/g,"").replace(/[^a-z0-9]+/g," ").trim();
s=s.normalize("NFD").replace(/[̀-ͯ]/g,"");
return s.replace(/['’‘`´]/g,"").replace(/[^\p{L}\p{N}]+/gu," ").trim();
}
function twins(raw){
var a=[raw],r=raw.replace(/ø/g,"o").replace(/æ/g,"ae").replace(/ß/g,"ss").replace(/å/g,"a");
if(r!==raw)a.push(r);
var u=raw.replace(/ü/g,"ue").replace(/ö/g,"oe").replace(/ä/g,"ae").replace(/ø/g,"oe").replace(/æ/g,"ae").replace(/ß/g,"ss");
if(u!==raw&&u!==r)a.push(u);
return a;
}
function now(){try{return(typeof performance!=="undefined"&&performance.now)?performance.now():Date.now();}catch(e){return Date.now();}}
function dl(a,b,k){
var la=a.length,lb=b.length;if(Math.abs(la-lb)>k)return k+1;
var p2=[],p1=[],c=[],i,j;
for(j=0;j<=lb;j++)p1[j]=j;
for(i=1;i<=la;i++){
c=[i];var mn=i;
for(j=1;j<=lb;j++){
var cost=a.charCodeAt(i-1)===b.charCodeAt(j-1)?0:1;
var v=Math.min(p1[j]+1,c[j-1]+1,p1[j-1]+cost);
if(i>1&&j>1&&a.charCodeAt(i-1)===b.charCodeAt(j-2)&&a.charCodeAt(i-2)===b.charCodeAt(j-1))v=Math.min(v,p2[j-2]+1);
c[j]=v;if(v<mn)mn=v;
}
if(mn>k)return k+1;
p2=p1;p1=c;
}
return p1[lb];
}
function create(opts){
opts=opts||{};
var E={stats:{buildMs:0,lastMs:0,maxMs:0,n:0},ready:false,items:null};
var N=0,IT=[],keys,keysC,titleF,brandOf,catOf,pop,popRaw,base,P,words,byLen,ALIAS,maxPh=1;
var mb,sb,bc,brands,brandByFold,cats,catCount,catWords,tmp=[],tot,hit,bigC,bigStart,memo=new Map(),predMemo=null;
function aliasMap(){
var m=new Map(),add=function(k,s,w){
var a=m.get(k);if(!a)m.set(k,a=[]);
for(var i=0;i<a.length;i++)if(a[i].s===s){if(w>a[i].w)a[i].w=w;return;}
a.push({s:s,w:w});
};
PCS_ALIAS.split(";").forEach(function(e){
var x=e.split(">");if(x.length<2)return;
var tg=x[1].split("|").map(fold);
x[0].split(",").forEach(function(k){twins(k.trim()).forEach(function(t){var f=fold(t);if(f)tg.forEach(function(s){if(s&&s!==f)add(f,s,0.9);});});});
});
var syn=opts.syn||{};
Object.keys(syn).forEach(function(k){
twins(k).forEach(function(t){
var f=fold(t);if(!f)return;var own=m.has(f);
(syn[k]||[]).forEach(function(s){s=fold(s);if(s&&s!==f)add(f,s,own?0.7:0.9);});
});
});
m.forEach(function(v,k){var n=k.split(" ").length;if(n>maxPh)maxPh=n;});
return m;
}
var B=null;
E.build=function(items){E.begin(items);return E.finish();};
E.pending=function(){return!!B;};
E.begin=function(items){
var t0=now(),fc=new Map(),ff=function(s){var v=fc.get(s);if(v==null){v=fold(s);fc.set(s,v);}return v;};
IT=items||[];N=IT.length;E.items=IT;E.ready=false;
keys=new Array(N);keysC=new Array(N);titleF=new Array(N);brandOf=new Int32Array(N);catOf=new Int32Array(N);
var post=new Map(),bmap=new Map(),cmap=new Map();
brands=[];cats=[];catCount=[];
function put(w,i,f){var e=post.get(w);if(!e)post.set(w,e={a:[],l:-1});if(e.l!==i){e.a.push(i*8+f);e.l=i;}}
B={ms:0,post:post,ff:ff,add:function(from,to){for(var i=from;i<to;i++){
var p=IT[i],tf=fold(p.title),bn=p.brand||"",bf=ff(bn),cf=ff(p.cat||""),sf=ff(p.seller||"");
var parts=[];if(tf)parts.push(tf);if(bf)parts.push(bf);if(cf)parts.push(cf);if(sf)parts.push(sf);
var k=" "+parts.join(" ");keys[i]=k;keysC[i]=k.replace(/ /g,"");titleF[i]=" "+tf+" ";
var bi=bmap.get(bn);if(bi==null){bi=brands.length;bmap.set(bn,bi);brands.push({name:bn,f:bf,n:0,c:bf.replace(/ /g,"")});}brands[bi].n++;brandOf[i]=bi;
var ci=cmap.get(p.cat);if(ci==null){ci=cats.length;cmap.set(p.cat,ci);cats.push(p.cat);catCount.push(0);}catCount[ci]++;catOf[i]=ci;
var a,j;
if(bf){a=bf.split(" ");for(j=0;j<a.length;j++)put(a[j],i,0);}
if(tf){a=tf.split(" ");for(j=0;j<a.length;j++)put(a[j],i,1);}
if(cf){a=cf.split(" ");for(j=0;j<a.length;j++)put(a[j],i,2);}
if(opts.colors){var cl=[];try{cl=opts.colors(p)||[];}catch(e){}for(var c=0;c<cl.length;c++){a=ff(cl[c]).split(" ");for(j=0;j<a.length;j++)if(a[j])put(a[j],i,3);}}
if(sf){a=sf.split(" ");for(j=0;j<a.length;j++)put(a[j],i,4);}
}}};
B.add(0,N>>1);B.ms=now()-t0;
return E;
};
E.finish=function(){
if(!B)return E;
var t0=now(),post=B.post,i;B.add(N>>1,N);
P=new Map();post.forEach(function(e,w){P.set(w,Int32Array.from(e.a));});
words=Array.from(P.keys()).sort();
ALIAS=aliasMap();
byLen=new Map();
var voc=words.concat(Array.from(ALIAS.keys()).filter(function(k){return k.indexOf(" ")<0&&!P.has(k);}));
voc.forEach(function(w){if(/\d/.test(w)||w.length<4)return;var l=w.length,b=byLen.get(l);if(!b)byLen.set(l,b=[]);b.push(w);});
brandByFold=new Map();brands.forEach(function(b,i){if(b.f)brandByFold.set(b.f,i);});
catWords=new Map();
var addCW=function(w,ci,q){if(!w||w.length<2)return;var a=catWords.get(w);if(!a)catWords.set(w,a=[]);for(var i=0;i<a.length;i++)if(a[i].c===ci){if(q>a[i].q)a[i].q=q;return;}a.push({c:ci,q:q});};
cats.forEach(function(c,ci){
addCW(fold(c),ci,1);
((opts.catNames||{})[c]||[]).forEach(function(nm){twins(String(nm).toLowerCase()).forEach(function(t){var f=fold(t);addCW(f,ci,1);f.split(" ").forEach(function(x){if(x.length>=3)addCW(x,ci,0.95);});});});
});
TYPES.split(" ").forEach(function(w){
var pp=P.get(w);if(!pp)return;var cnt=new Map(),tot2=0;
for(var i=0;i<pp.length;i++){if((pp[i]&7)!==1)continue;var ci=catOf[pp[i]>>3];cnt.set(ci,(cnt.get(ci)||0)+1);tot2++;}
cnt.forEach(function(n,ci){if(tot2>=3&&n/tot2>=0.6)addCW(w,ci,0.85);});
});
bigStart=new Int32Array(N);var acc=0;for(i=0;i<N;i++){bigStart[i]=acc;acc+=keysC[i].length+1;}
bigC=keysC.join("\n");
tot=new Float32Array(N);hit=new Uint8Array(N);tmp=[];mb=new Int32Array(N);sb=new Float32Array(N);bc=new Int32Array(brands.length);
E.refresh();memo.clear();predMemo=null;E.ready=true;
var fm=now()-t0;E.stats.buildMs=Math.round((fm+B.ms)*10)/10;E.stats.parts=[Math.round(B.ms*10)/10,Math.round(fm*10)/10];B=null;
return E;
};
E.refresh=function(){
pop=new Float32Array(N);popRaw=new Float32Array(N);base=new Float32Array(N);
var s=new Float64Array(N),i;
for(i=0;i<N;i++){var p=IT[i];s[i]=(p.views||0)+(p.views7||0)+3*(p.favs||0);popRaw[i]=(p.views||0)+(p.views7||0);}
var srt=Array.from(s).sort(function(a,b){return a-b;}),p99=srt.length?srt[Math.min(srt.length-1,Math.floor(srt.length*0.99))]:0,lp=Math.log1p(p99);
for(i=0;i<N;i++){
var q=IT[i],sold=false,ph=false;
try{sold=opts.sold?!!opts.sold(q):false;}catch(e){}
try{ph=opts.ph?!!opts.ph(q.price):false;}catch(e){}
pop[i]=lp>0?Math.min(1,Math.log1p(s[i])/lp):0;
base[i]=18*pop[i]+((q.qc||0)>=1?6:0)-(sold?30:0)-(ph?4:0);
}
memo.clear();predMemo=null;
};
function arr(n){var a=tmp[n];if(!a)a=tmp[n]=new Float32Array(N);else a.fill(0);return a;}
function range(w){
var lo=0,hi=words.length;
while(lo<hi){var m=(lo+hi)>>1;if(words[m]<w)lo=m+1;else hi=m;}
var s=lo;hi=words.length;
while(lo<hi){var m2=(lo+hi)>>1;if(words[m2].lastIndexOf(w,0)===0)lo=m2+1;else hi=m2;}
return[s,lo];
}
function evalWord(w,last,out,scale){
var r=range(w),n=0;
for(var k=r[0];k<r[1];k++){
var wd=words[k],q=(wd===w?1:(last||w.length>=3)?0.8:0.5)*scale,pp=P.get(wd);n++;
for(var j=0;j<pp.length;j++){var c=pp[j],i=c>>3,v=q*W[c&7];if(v>out[i])out[i]=v;}
}
return n;
}
function evalPhrase(ph,out,scale,last){
if(ph.indexOf(" ")<0)return evalWord(ph,last!==false,out,scale);
var first=ph.slice(0,ph.indexOf(" ")),pp=P.get(first),n=0,need=" "+ph;if(!pp)return 0;
for(var j=0;j<pp.length;j++){
var i=pp[j]>>3,k=keys[i],at=k.indexOf(need);if(at<0)continue;
var b=" "+(brands[brandOf[i]].f),f=b.indexOf(need)>=0?0:titleF[i].indexOf(need)>=0?1:2;
var end=k.charAt(at+need.length),q=(end===""||end===" "?1:0.8)*scale*W[f];
if(q>out[i])out[i]=q;n++;
}
return n;
}
function evalToken(tok,last,out,ctx,depth){
var n=evalWord(tok,last,out,1);
if(tok.length>3&&/s$/.test(tok)&&!/ss$/.test(tok))n+=evalWord(tok.slice(0,-1),last,out,0.95);
if(/(ch|sh|ss|x)es$/.test(tok))n+=evalWord(tok.slice(0,-2),last,out,0.95);
var al=ALIAS.get(tok);
if(al)for(var a=0;a<al.length;a++)n+=evalPhrase(al[a].s,out,al[a].w,last)?1:0;
if(n||al||depth||/\d/.test(tok)||tok.length<4||CJK.test(tok))return n;
var k=tok.length>=8?2:1,best=null,bd=k+1,bc=-1;
for(var L=tok.length-k;L<=tok.length+k;L++){
var b=byLen.get(L);if(!b)continue;
for(var j=0;j<b.length;j++){
var d=dl(tok,b[j],Math.min(k,bd));if(d>k)continue;
var cnt=P.has(b[j])?P.get(b[j]).length:0;
if(d<bd||(d===bd&&cnt>bc)){bd=d;best=b[j];bc=cnt;}
}
}
if(!best)return 0;
ctx.fix[tok]=best;
var t2=arr(9);
evalToken(best,false,t2,ctx,1);
var sc=bd===1?0.6:0.4,m=0;
for(var i=0;i<N;i++)if(t2[i]>0){var v=t2[i]*sc;if(v>out[i])out[i]=v;m++;}
return m;
}
function parse(f){
var raw=f.split(" "),toks=[];
raw.forEach(function(t){
if(!CJK.test(t)||ALIAS.has(t)){toks.push(t);return;}
var found=[],i=0;
while(i<t.length){var hitk="";for(var L=Math.min(4,t.length-i);L>=1;L--){var s=t.substr(i,L);if(ALIAS.has(s)){hitk=s;break;}}if(hitk){found.push(hitk);i+=hitk.length;}else i++;}
if(found.length)toks.push.apply(toks,found);else toks.push(t);
});
var g=[],i=0;
while(i<toks.length){
var done=false;
for(var n=Math.min(maxPh,toks.length-i);n>=2;n--){
var k=toks.slice(i,i+n).join(" ");
if(ALIAS.has(k)){g.push({toks:toks.slice(i,i+n),key:k,exp:ALIAS.get(k),last:i+n===toks.length});i+=n;done=true;break;}
}
if(!done){g.push({toks:[toks[i]],key:toks[i],exp:ALIAS.get(toks[i])||null,last:i===toks.length-1});i++;}
}
return g;
}
function run(f){
var ctx={fix:{}},G=parse(f),g,i,j;
tot.fill(0);hit.fill(0);
for(j=0;j<G.length;j++){
g=G[j];var out=arr(0);
if(g.toks.length===1)evalToken(g.key,g.last,out,ctx,0);
else{
var parts=g.toks.map(function(t,x){var a=arr(1+x);evalToken(t,g.last&&x===g.toks.length-1,a,ctx,0);return a;});
for(i=0;i<N;i++){var mn=1e9;for(var x=0;x<parts.length;x++){var v=parts[x][i];if(v<mn)mn=v;}if(mn>0&&mn<1e9)out[i]=mn;}
for(x=0;x<g.exp.length;x++)evalPhrase(g.exp[x].s,out,g.exp[x].w,g.last);
}
for(i=0;i<N;i++)if(out[i]>0){tot[i]+=out[i];hit[i]++;}
}
var GL=G.length,m=mb,n=0,comp=f.replace(/ /g,"");
for(i=0;i<N;i++)if(hit[i]===GL)m[n++]=i;
if(comp.length>=6){
var pos=0,seen=null;
while((pos=bigC.indexOf(comp,pos))>=0){
var lo=0,hi=N-1;while(lo<hi){var md=(lo+hi+1)>>1;if(bigStart[md]<=pos)lo=md;else hi=md-1;}
if(hit[lo]!==GL){if(!seen)seen=new Set();if(!seen.has(lo)){seen.add(lo);m[n++]=lo;tot[lo]=0.5*GL;}}
pos=lo+1<N?bigStart[lo+1]:bigC.length;
}
}
var fixed=Object.keys(ctx.fix).length?f.split(" ").map(function(t){return ctx.fix[t]||t;}).join(" "):"";
var seqs=[" "+f],ex=" "+G.map(function(x){return x.exp&&x.exp[0].w>=0.9?x.exp[0].s:x.key;}).join(" ");
if(ex!==seqs[0])seqs.push(ex);if(fixed)seqs.push(" "+fixed);
var multi=G.length>1||seqs.some(function(s){return s.indexOf(" ",1)>0;});
var cover=new Set(),qs=" "+f+" ",qf=fixed?" "+fixed+" ":"";
brands.forEach(function(b,bi){if(b.f&&(qs.indexOf(" "+b.f+" ")>=0||(qf&&qf.indexOf(" "+b.f+" ")>=0)))cover.add(bi);});
G.forEach(function(x){(x.exp||[]).forEach(function(e){var bi=brandByFold.get(e.s);if(bi!=null&&e.w>=0.9)cover.add(bi);});});
var first=" "+G[0].key,first2=G[0].exp&&G[0].exp[0].w>=0.9?" "+G[0].exp[0].s:first;
var score=sb;
for(j=0;j<n;j++){
i=m[j];var t=tot[i]/GL,bo=0,tf=titleF[i];
if(multi)for(var s=0;s<seqs.length;s++)if(tf.indexOf(seqs[s])>=0){bo+=0.25;break;}
if(cover.has(brandOf[i]))bo+=0.2;
if(tf.lastIndexOf(first,0)===0||tf.lastIndexOf(first2,0)===0)bo+=0.05;
score[j]=100*(t+bo)+base[i];
}
return{G:G,m:m,n:n,score:score,fix:ctx.fix,fixed:fixed,cover:cover};
}
function order(r,lim){
var m=r.m,sc=r.score,n=r.n,ix=[],j;
var cmp=function(a,b){return(sc[b]-sc[a])||(popRaw[m[b]]-popRaw[m[a]])||(m[a]-m[b]);};
if(lim&&n>lim*4){
var top=[];
for(j=0;j<n;j++){
if(top.length<lim){top.push(j);top.sort(cmp);}
else if(cmp(j,top[lim-1])<0){top[lim-1]=j;top.sort(cmp);}
}
return top.map(function(j2){return m[j2];});
}
for(j=0;j<n;j++)ix.push(j);
ix.sort(cmp);if(lim)ix=ix.slice(0,lim);
return ix.map(function(j2){return m[j2];});
}
function brandSugs(f,r){
var out=[],qs=" "+f+" ",qf=r.fixed?" "+r.fixed+" ":"",fc=f.replace(/ /g,"");
var inRes=bc;inRes.fill(0);for(var j=0;j<r.n;j++)inRes[brandOf[r.m[j]]]++;
brands.forEach(function(b,bi){
if(!b.f)return;var q=0;
if(r.cover.has(bi)||qs.indexOf(" "+b.f+" ")>=0||(qf&&qf.indexOf(" "+b.f+" ")>=0))q=1;
else if(b.f.lastIndexOf(f,0)===0||(fc.length>=3&&b.c.lastIndexOf(fc,0)===0))q=0.9;
else if(f.length>=2&&b.f.indexOf(" "+f)>0)q=0.7;
else if(f.length>=3&&f.split(" ").every(function(t){return t&&(" "+b.f).indexOf(" "+t)>=0;}))q=0.85;
if(q)out.push({i:bi,q:q});
});
if(!out.length&&fc.length>=4&&!/\d/.test(fc)){
var ws=f.split(" ");
brands.forEach(function(b,bi){
if(!b.f||b.c.length<4)return;var n=b.f.split(" ").length,head=ws.slice(0,n).join(""),k=b.c.length>=8?2:1;
if(dl(head,b.c,k)<=k||dl(fc,b.c,k)<=k)out.push({i:bi,q:0.6});
});
}
out.sort(function(a,b){return(b.q-a.q)||(inRes[b.i]-inRes[a.i])||(brands[b.i].n-brands[a.i].n);});
return out.slice(0,3).map(function(x){return{name:brands[x.i].name,n:brands[x.i].n,q:x.q,hit:inRes[x.i]};});
}
function catSugs(r){
var best=new Map(),see=function(w,q,last){
var l=catWords.get(w);if(l)l.forEach(function(e){var v=e.q*q;if(v>(best.get(e.c)||0))best.set(e.c,v);});
if(last&&w.length>=3)catWords.forEach(function(l2,k){if(k!==w&&k.lastIndexOf(w,0)===0)l2.forEach(function(e){var v=e.q*q*0.8;if(v>(best.get(e.c)||0))best.set(e.c,v);});});
};
r.G.forEach(function(g){
see(g.key,1,g.last);if(g.toks.length>1)g.toks.forEach(function(t){see(t,0.9,false);});
(g.exp||[]).forEach(function(e){see(e.s,0.9,false);});
g.toks.forEach(function(t){if(r.fix[t]){see(r.fix[t],0.6,false);(ALIAS.get(r.fix[t])||[]).forEach(function(e){see(e.s,0.55,false);});}});
});
var out=[];best.forEach(function(q,c){out.push({c:c,q:q});});
out.sort(function(a,b){return(b.q-a.q)||(catCount[b.c]-catCount[a.c]);});
return out.slice(0,2).map(function(x){return{cat:cats[x.c],n:catCount[x.c],q:x.q};});
}
E.search=function(raw,lim){
if(B)E.finish();
var t0=now(),f=fold(raw);
if(!f)return{f:"",total:0,top:[],brands:[],cats:[],dym:"",closest:[],terms:[]};
var mk=f+"|"+(lim||6),c=memo.get(mk);if(c)return c;
if(/^\d{6,}$/.test(f)){c={f:f,id:f,total:0,top:[],brands:[],cats:[],dym:"",closest:[],terms:[]};memo.set(mk,c);return c;}
var r=run(f),top=order(r,lim||6),closest=[];
if(!r.n&&r.G.length>=2){
var need=Math.ceil(r.G.length/2),cand=[],sc2=[];
for(var i=0;i<N;i++)if(hit[i]>=need){cand.push(i);sc2.push(100*tot[i]/r.G.length+base[i]);}
closest=order({m:cand,score:sc2,n:cand.length},4);
}
var terms=[];
r.G.forEach(function(g){g.toks.forEach(function(t){terms.push(t);if(r.fix[t])terms.push(r.fix[t]);});(g.exp||[]).forEach(function(e){if(e.w>=0.9)e.s.split(" ").forEach(function(w){terms.push(w);});});});
c={f:f,total:r.n,top:top.map(function(i){return IT[i];}),closest:closest.map(function(i){return IT[i];}),
brands:brandSugs(f,r),cats:catSugs(r),dym:r.fixed,terms:terms};
if(memo.size>200)memo.clear();memo.set(mk,c);
var ms=now()-t0;E.stats.lastMs=Math.round(ms*100)/100;if(ms>E.stats.maxMs)E.stats.maxMs=E.stats.lastMs;E.stats.n++;
return c;
};
E.predicate=function(raw){
if(B)E.finish();
var f=fold(raw);if(!f)return null;
if(predMemo&&predMemo.f===f)return predMemo.fn;
var t0=now(),r=run(f),set=new Set(),sc=new Map();
for(var j=0;j<r.n;j++){var p=IT[r.m[j]];set.add(p);sc.set(p,r.score[j]);}
var fn=function(p){return set.has(p);};fn.score=sc;fn.total=set.size;
predMemo={f:f,fn:fn};
var ms=now()-t0;E.stats.lastMs=Math.round(ms*100)/100;if(ms>E.stats.maxMs)E.stats.maxMs=E.stats.lastMs;E.stats.n++;
return fn;
};
E.clear=function(){memo.clear();predMemo=null;};
E.fold=fold;
E.aliasTargets=function(){var o=[];ALIAS.forEach(function(v,k){v.forEach(function(e){o.push([k,e.s,e.w]);});});return o;};
E.count=function(phrase){var a=arr(8);evalPhrase(fold(phrase),a,1,true);var n=0;for(var i=0;i<N;i++)if(a[i]>0)n++;return n;};
return E;
}
return{create:create,fold:fold,dl:dl};
})();
/* PCS-ENGINE-END */
(function(){
"use strict";
var d=document,w=window,A=w.PCS_ENGINE;
if(!A)return;
function $(id){return d.getElementById(id);}
function G(n){
try{
switch(n){
case"ALL":return ALL;case"state":return state;case"render":return render;case"syncQParam":return syncQParam;
case"updatePriceUI":return updatePriceUI;case"openDetail":return openDetail;case"closeDetail":return closeDetail;
case"t":return t;case"T":return T;case"pprice":return pprice;case"thumbOf":return thumbOf;case"catName":return catName;
case"pcExtract":return pcExtract;case"Q_SYN":return Q_SYN;case"productColors":return productColors;case"isPH":return isPH;
case"SOLD":return SOLD;case"STATS":return STATS;case"popScore":return popScore;
}
}catch(e){}
return undefined;
}
function mq(q){try{return w.matchMedia(q).matches;}catch(e){return false;}}
function tr(k){var f=EN_L[k]||k;try{var t=G("t"),v=typeof t==="function"?t(k):f;return v&&v!==k?v:f;}catch(e){return f;}}
function nf(n){var s=G("state");try{return Number(n).toLocaleString((s&&s.lang)||"en");}catch(e){return String(n);}}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
function ic(n,c){return'<svg class="ic'+(c?" "+c:"")+'" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false"><use href="#i-'+n+'"/></svg>';}
function kind(){var p=location.pathname;return p==="/"?"home":/^\/product\//.test(p)?"product":"hub";}
function log(f){try{f(w.pcSearch);}catch(_){}}
var EN_L={};
try{
var KEYS=["pcs_ph","pcs_ph_n","pcs_recent","pcs_clear","pcs_remove","pcs_popular","pcs_cats","pcs_brands","pcs_products","pcs_finds","pcs_dym","pcs_all","pcs_none","pcs_closest","pcs_try","pcs_open_find","pcs_qc_link","pcs_live","pcs_close","pcs_list","pcs_dym_g","pcs_ai_g","pcs_qc_g"];
var L={
en:["Search finds","Search {n} finds","Recent","Clear","Remove {q} from recent searches","Popular","Categories","Brands","Products","{n} finds","Did you mean {q}?","Search all {n} results for “{q}”","No exact matches for “{q}”","Closest matches","Try “{q}”","Open this find","Check QC photos for this link","{s} suggestions, {n} finds","Close search","Search suggestions","Did you mean","AI suggestion","QC photos"],
no:["Søk i funn","Søk i {n} funn","Nylige","Tøm","Fjern {q} fra nylige søk","Populære","Kategorier","Merker","Produkter","{n} funn","Mente du {q}?","Se alle {n} treff for “{q}”","Ingen eksakte treff for “{q}”","Nærmeste treff","Prøv “{q}”","Åpne dette funnet","Sjekk QC-bilder for denne lenken","{s} forslag, {n} funn","Lukk søk","Søkeforslag","Mente du","AI-forslag","QC-bilder"],
sv:["Sök fynd","Sök bland {n} fynd","Senaste","Rensa","Ta bort {q} från senaste sökningar","Populära","Kategorier","Märken","Produkter","{n} fynd","Menade du {q}?","Visa alla {n} träffar för “{q}”","Inga exakta träffar för “{q}”","Närmaste träffar","Prova “{q}”","Öppna det här fyndet","Kolla QC-bilder för länken","{s} förslag, {n} fynd","Stäng sökningen","Sökförslag","Menade du","AI-förslag","QC-bilder"],
da:["Søg i fund","Søg i {n} fund","Seneste","Ryd","Fjern {q} fra seneste søgninger","Populære","Kategorier","Mærker","Produkter","{n} fund","Mente du {q}?","Se alle {n} resultater for “{q}”","Ingen præcise resultater for “{q}”","Nærmeste resultater","Prøv “{q}”","Åbn dette fund","Tjek QC-billeder for linket","{s} forslag, {n} fund","Luk søgning","Søgeforslag","Mente du","AI-forslag","QC-billeder"],
de:["Funde durchsuchen","{n} Funde durchsuchen","Zuletzt gesucht","Löschen","{q} aus den letzten Suchen entfernen","Beliebt","Kategorien","Marken","Produkte","{n} Funde","Meintest du {q}?","Alle {n} Ergebnisse für „{q}“","Keine genauen Treffer für „{q}“","Ähnliche Treffer","„{q}“ versuchen","Diesen Fund öffnen","QC-Fotos für diesen Link prüfen","{s} Vorschläge, {n} Funde","Suche schließen","Suchvorschläge","Meintest du","KI-Vorschlag","QC-Fotos"],
nl:["Zoek vondsten","Zoek in {n} vondsten","Recent","Wissen","{q} uit recente zoekopdrachten verwijderen","Populair","Categorieën","Merken","Producten","{n} vondsten","Bedoelde je {q}?","Alle {n} resultaten voor “{q}”","Geen exacte resultaten voor “{q}”","Beste overeenkomsten","Probeer “{q}”","Open deze vondst","QC-foto’s voor deze link bekijken","{s} suggesties, {n} vondsten","Zoeken sluiten","Zoeksuggesties","Bedoelde je","AI-suggestie","QC-foto’s"],
fr:["Rechercher des trouvailles","Rechercher parmi {n} trouvailles","Récentes","Effacer","Retirer {q} des recherches récentes","Populaires","Catégories","Marques","Produits","{n} trouvailles","Vouliez-vous dire {q} ?","Voir les {n} résultats pour « {q} »","Aucun résultat exact pour « {q} »","Résultats proches","Essayer « {q} »","Ouvrir cette trouvaille","Voir les photos QC de ce lien","{s} suggestions, {n} trouvailles","Fermer la recherche","Suggestions de recherche","Vouliez-vous dire","Suggestion IA","Photos QC"],
it:["Cerca nei find","Cerca tra {n} find","Recenti","Cancella","Rimuovi {q} dalle ricerche recenti","Popolari","Categorie","Marchi","Prodotti","{n} find","Forse cercavi {q}?","Tutti i {n} risultati per “{q}”","Nessun risultato esatto per “{q}”","Risultati simili","Prova “{q}”","Apri questo find","Vedi le foto QC di questo link","{s} suggerimenti, {n} find","Chiudi la ricerca","Suggerimenti di ricerca","Forse cercavi","Suggerimento IA","Foto QC"],
es:["Buscar hallazgos","Buscar entre {n} hallazgos","Recientes","Borrar","Quitar {q} de las búsquedas recientes","Populares","Categorías","Marcas","Productos","{n} hallazgos","¿Quisiste decir {q}?","Ver los {n} resultados de “{q}”","Sin resultados exactos para “{q}”","Resultados parecidos","Prueba “{q}”","Abrir este hallazgo","Ver fotos QC de este enlace","{s} sugerencias, {n} hallazgos","Cerrar búsqueda","Sugerencias de búsqueda","Quisiste decir","Sugerencia de IA","Fotos QC"],
zh:["搜索好物","搜索 {n} 件好物","最近搜索","清除","从最近搜索中删除 {q}","热门","分类","品牌","商品","{n} 件","你是不是要找 {q}？","查看“{q}”的全部 {n} 个结果","没有与“{q}”完全匹配的结果","相近结果","试试“{q}”","打开这件好物","查看此链接的 QC 照片","{s} 条建议，{n} 件好物","关闭搜索","搜索建议","你是不是要找","AI 建议","QC 照片"]
};
KEYS.forEach(function(k,i){EN_L[k]=L.en[i];});
var TT=G("T");
if(TT)Object.keys(L).forEach(function(l){if(!TT[l])return;var o={};KEYS.forEach(function(k,i){o[k]=L[l][i];});Object.assign(TT[l],o);});
}catch(e){}
var CATS=[["Shoes","/img/cat/shoes.webp"],["Tops","/img/cat/tops.webp"],["Outerwear","/img/cat/outerwear.webp"],["Pants","/img/cat/pants.webp"],
["Shorts","/img/cat/shorts.webp"],["Bags","/img/cat/bags.webp"],["Accessories","/img/cat/accessories.webp"],["Headwear","/img/cat/headwear.webp"]];
var EN=null,builtLen=-1,seenStats=null,seenSold=null;
function all(){var a=G("ALL");return Array.isArray(a)?a:null;}
function mk(){
if(!EN){
var T2=G("T")||{},names={};
CATS.forEach(function(c){names[c[0]]=Object.keys(T2).map(function(l){return T2[l]&&T2[l]["cat_"+c[0]];}).filter(Boolean);});
var pc=G("productColors"),ph=G("isPH");
EN=A.create({syn:G("Q_SYN")||{},colors:typeof pc==="function"?pc:null,catNames:names,ph:typeof ph==="function"?ph:null,
sold:function(p){var s=G("SOLD");return!!(s&&s.has(String(p.id)));}});
PCS.stats=EN.stats;
}
return EN;
}
function begin(a){EN.begin(a);builtLen=a.length;seenStats=G("STATS")||null;seenSold=G("SOLD")||null;}
function ensure(){
var a=all();if(!a)return null;mk();
if(builtLen!==a.length)begin(a);
if(EN.pending())EN.finish();
else{var st=G("STATS")||null,so=G("SOLD")||null;if(st!==seenStats||so!==seenSold){seenStats=st;seenSold=so;EN.refresh();}}
return EN;
}
function idle(f){(w.requestIdleCallback||function(g){return setTimeout(g,1);})(f,{timeout:300});}
function warm(){
var a=all();if(!a||(EN&&builtLen===a.length&&!EN.pending()))return;
idle(function(){try{mk();if(builtLen!==a.length)begin(a);if(EN.pending())idle(function(){try{if(EN.pending())EN.finish();}catch(e){}});}catch(e){}});
}
var PCS=w.PCS={
stats:{buildMs:0,lastMs:0,maxMs:0,n:0},
ensure:ensure,
predicate:function(raw){var e=ensure();return e?e.predicate(raw):null;},
search:function(raw){var e=ensure();return e?e.search(raw):null;}
};
var RK="pc.search.recent";
function recent(){try{var a=JSON.parse(localStorage.getItem(RK)||"[]");return Array.isArray(a)?a.filter(function(x){return typeof x==="string"&&x;}).slice(0,6):[];}catch(e){return[];}}
function setRecent(a){try{if(a.length)localStorage.setItem(RK,JSON.stringify(a.slice(0,6)));else localStorage.removeItem(RK);}catch(e){}}
function addRecent(q){
q=String(q||"").trim().replace(/\s+/g," ").slice(0,60);var f=A.fold(q);
if(!f||/^\d{6,}$/.test(f)||/[\/.]/.test(q)&&/\d{6,}/.test(q)||/https?:|www\./i.test(q))return;
setRecent([q].concat(recent().filter(function(x){return A.fold(x)!==f;})));
}
function delRecent(q){var f=A.fold(q);setRecent(recent().filter(function(x){return A.fold(x)!==f;}));}
var POP=null,popLoading=false;
function loadPop(){
if(POP||popLoading)return;popLoading=true;
var done=function(dash){
var out=[],seen={},push=function(q){q=String(q||"").trim();var f=A.fold(q);if(!f||seen[f]||out.length>=8)return;seen[f]=1;out.push(q);};
try{((dash&&dash.search&&dash.search.top)||[]).forEach(function(r){var q=String(r[0]||"").trim();if((r[3]||0)>0&&q.length>=2&&q.length<=40&&!/^\d+$/.test(q)&&!/https?:|www\.|\.[a-z]{2,3}\//i.test(q))push(q);});}catch(e){}
if(out.length<4)try{((dash&&dash.top_brands_7d)||[]).forEach(function(r){push(r[0]);});}catch(e){}
if(!dash)try{
var a=all()||[],ps=G("popScore"),sc={};
a.forEach(function(p){if(p.brand)sc[p.brand]=(sc[p.brand]||0)+(typeof ps==="function"?ps(p):0);});
Object.keys(sc).filter(function(b){return sc[b]>0;}).sort(function(x,y){return sc[y]-sc[x];}).slice(0,8).forEach(push);
}catch(e){}
POP=out;popLoading=false;if(open)paint();
};
try{fetch("/data/dashboard.json",{cache:"no-cache"}).then(function(r){return r.ok?r.json():null;}).then(done,function(){done(null);});}catch(e){done(null);}
}
var panel,list,live,ov,dlg,oi,oclr,back,open=false,mode="",host=null,trigger=null,opts=[],act=-1,kb=false,rafId=0,logT=0,liveT=0,lastN=0,lastQ="",res=null;
var R={rec:[],pop:[],cat:[],br:[],ct:[],pr:[],cl:[]};
function row(cls,inner,tag){var e=d.createElement(tag||"div");e.className="pcs-row "+(cls||"");e.setAttribute("role","option");e.setAttribute("aria-selected","false");if(tag==="a")e.tabIndex=-1;e.innerHTML=inner;return e;}
function sec(id,head,extra){var s=d.createElement("div");s.className="pcs-sec";s.id="pcs-g-"+id;s.setAttribute("role","group");if(head){s.setAttribute("aria-labelledby","pcs-h-"+id);s.innerHTML='<div class="pcs-h"><span id="pcs-h-'+id+'"></span>'+(extra||"")+"</div>";}var b=d.createElement("div");b.className="pcs-b";s.appendChild(b);list.appendChild(s);return s;}
function prodRow(){
var e=row("pcs-prod",'<span class="pcs-well"><img alt="" width="48" height="48" loading="lazy" decoding="async"></span><span class="pcs-pm"><span class="pcs-pt"></span><span class="pcs-ps"></span></span><span class="pcs-pr"><span class="pcs-pp"></span><span class="pcs-qc">'+ic("camera")+"QC</span></span>","a");
var im=e.querySelector("img");im.addEventListener("error",function(){var u=im.getAttribute("src")||"",m=u.match(/\/api\/img\?u=([^&]+)/);if(m&&!im.dataset.r){im.dataset.r=1;im.src=decodeURIComponent(m[1]);}else im.style.visibility="hidden";});
return e;
}
function build(){
if(panel)return;
panel=d.createElement("div");panel.className="pcs-panel";panel.id="pcs-panel";panel.hidden=true;
list=d.createElement("div");list.id="pcs-list";list.setAttribute("role","listbox");list.setAttribute("aria-label",tr("pcs_list"));panel.appendChild(list);
var s,i;
s=sec("rec",1,'<button type="button" class="pcs-clr" tabindex="-1" data-a="clr"></button>');
for(i=0;i<6;i++){R.rec.push(s.lastChild.appendChild(row("pcs-rr",ic("clock")+'<span class="pcs-t"></span><button type="button" class="pcs-x" tabindex="-1" aria-hidden="true" data-a="del">'+ic("x")+"</button>")));}
s=sec("pop",1);s.lastChild.className="pcs-b pcs-chips";
for(i=0;i<8;i++){var c=row("pcs-chip","");c.className="pcs-chip";R.pop.push(s.lastChild.appendChild(c));}
s=sec("cat",1);s.lastChild.className="pcs-b pcs-tiles";
CATS.forEach(function(c,k){var e=row("pcs-tile",'<span class="pcs-cph"><img src="'+esc(c[1])+'" alt="" width="40" height="40" decoding="async" loading="lazy"></span><span class="pcs-tw"><span class="pcs-tl"></span><span class="pcs-tn"></span></span>');e.className="pcs-tile";e.dataset.cat=c[0];R.cat.push(s.lastChild.appendChild(e));});
s=sec("dym",0);s.setAttribute("aria-label",tr("pcs_dym_g"));R.dym=s.lastChild.appendChild(row("",ic("search")+'<span class="pcs-t"></span>'));
s=sec("none",0);s.setAttribute("role","presentation");s.lastChild.className="pcs-b pcs-none";
s=sec("open",1);
s=sec("br",1);for(i=0;i<3;i++)R.br.push(s.lastChild.appendChild(row("",'<span class="pcs-bt">'+ic("tag")+'</span><span class="pcs-t"></span><span class="pcs-n"></span>')));
s=sec("ct",1);for(i=0;i<2;i++)R.ct.push(s.lastChild.appendChild(row("",'<span class="pcs-cph"><img alt="" width="40" height="40" decoding="async" loading="lazy"></span><span class="pcs-t"></span><span class="pcs-n"></span>')));
s=sec("pr",1);for(i=0;i<6;i++)R.pr.push(s.lastChild.appendChild(prodRow()));
s=sec("cl",1);for(i=0;i<4;i++)R.cl.push(s.lastChild.appendChild(prodRow()));
s=sec("ai",0);s.setAttribute("aria-label",tr("pcs_ai_g"));s.lastChild.className="pcs-b pcs-chips";R.ai=row("","");R.ai.className="pcs-chip pcs-ai";s.lastChild.appendChild(R.ai);
s=sec("qc",0);s.setAttribute("aria-label",tr("pcs_qc_g"));R.qc=s.lastChild.appendChild(row("",ic("camera")+'<span class="pcs-t"></span>',"a"));
R.all=row("pcs-all",ic("search")+'<span class="pcs-t"></span>'+ic("arrow-right","pcs-go"));list.appendChild(R.all);
R.secs={};[].forEach.call(list.children,function(x){if(x.id)R.secs[x.id.slice(6)]=x;});
live=d.createElement("div");live.id="pcs-live";live.className="v9-vh";live.setAttribute("role","status");live.setAttribute("aria-live","polite");d.body.appendChild(live);
panel.addEventListener("mousedown",function(e){if(mode==="inline"||mode==="pal")e.preventDefault();});
panel.addEventListener("mousemove",function(e){var o=e.target.closest&&e.target.closest('[role="option"]');if(o&&opts.indexOf(o)>=0&&opts.indexOf(o)!==act){kb=false;setAct(opts.indexOf(o));}});
panel.addEventListener("click",onClick);
}
function buildOv(){
if(ov)return;build();
ov=d.createElement("div");ov.className="pcs-ov";ov.id="pcs-ov";ov.hidden=true;
ov.innerHTML='<div class="pcs-bd" data-a="close"></div><div class="pcs-dlg" role="dialog" aria-modal="true"><div class="pcs-top"><button class="pcs-back" type="button" data-a="close">'+ic("chevron-left","pcs-i-back")+ic("x","pcs-i-x")+'</button><div class="pcs-fld">'+ic("search")+'<input class="pcs-oi" id="pcs-oi" type="search" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" enterkeyhint="search"><button class="pcs-oclr" type="button" data-a="oclr" hidden>'+ic("x")+"</button></div></div></div>";
d.body.appendChild(ov);
dlg=ov.querySelector(".pcs-dlg");oi=$("pcs-oi");oclr=ov.querySelector(".pcs-oclr");back=ov.querySelector(".pcs-back");
ov.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("[data-a]");if(!a||panel.contains(a))return;if(a.dataset.a==="close")close(true);if(a.dataset.a==="oclr"){oi.value="";oclr.hidden=true;oi.focus();schedule();}});
ov.addEventListener("keydown",function(e){
if(e.key!=="Tab")return;var f=[oi,oclr,back].filter(function(x){return x&&!x.hidden&&x.offsetParent!==null;}),i=f.indexOf(d.activeElement);
e.preventDefault();var n=f[(i+(e.shiftKey?-1:1)+f.length)%f.length];if(n)n.focus();
});
wire(oi);
}
function sheetish(){return w.innerWidth<768||(mq("(pointer: coarse)")&&w.innerWidth<1024);}
function setExp(v){[heroIn,hdIn,oi].forEach(function(x){if(x){x.setAttribute("aria-expanded",v&&x===host?"true":"false");if(!v||x!==host)x.setAttribute("aria-activedescendant","");}});}
var inerted=[],scrollY=0,pushed=false,ignorePop=0;
function lockPage(on){
if(on){
inerted=[];d.querySelectorAll("body > *").forEach(function(el){if(el===ov||el===live||el.tagName==="SCRIPT")return;inerted.push([el,el.inert]);el.inert=true;});
scrollY=w.scrollY;d.documentElement.classList.add("pcs-lock");
}else{
inerted.forEach(function(x){x[0].inert=x[1];});inerted=[];
d.documentElement.classList.remove("pcs-lock");if(Math.abs(w.scrollY-scrollY)>1)w.scrollTo(0,scrollY);
}
}
var vvh=function(){try{ov.style.setProperty("--pcs-vvh",w.visualViewport.height+"px");}catch(e){}};
function openAt(inp,m){
build();var was=open;
if(host&&host!==inp)setExp(false);
host=inp;mode=m;open=true;
var hero=m==="inline"&&inp===heroIn,where=m==="inline"?(hero?d.body:$("pcs-hd")):dlg;
if(panel.parentNode!==where)where.appendChild(panel);
panel.hidden=false;panel.classList.toggle("pcs-float",hero);if(hero)posHero();else panel.style.cssText="";
inp.setAttribute("aria-controls","pcs-list");
setExp(true);loadPop();warm();
paint();
}
function posHero(){
if(!heroIn||!panel)return;var r=heroIn.getBoundingClientRect();
panel.style.cssText="top:"+Math.round(r.bottom+w.scrollY+8)+"px;left:"+Math.round(r.left+w.scrollX)+"px;width:"+Math.round(Math.min(r.width,720))+"px";
}
function openOv(m,from){
buildOv();trigger=from||d.activeElement;
var start=(from&&from.value!=null&&from!==oi)?from.value:(heroIn&&heroIn.value)||(hdIn&&hdIn.value)||"";
ov.className="pcs-ov "+(m==="sheet"?"is-sheet":"is-pal");ov.hidden=false;
dlg.setAttribute("aria-label",tr("pcs_ph"));back.setAttribute("aria-label",tr("pcs_close"));
oi.setAttribute("aria-label",tr("pcs_ph"));oi.placeholder=tr("pcs_ph");oclr.setAttribute("aria-label",tr("pcs_clear"));
oi.value=start;oclr.hidden=!start;
try{oi.focus({preventScroll:true});}catch(e){oi.focus();}
lockPage(true);
if(m==="sheet"){
vvh();try{w.visualViewport.addEventListener("resize",vvh);w.visualViewport.addEventListener("scroll",vvh);}catch(e){}
try{history.pushState(Object.assign({},history.state||{},{pcs:1}),"");pushed=true;}catch(e){pushed=false;}
}
openAt(oi,m);
}
function close(restore,fromPop){
if(!open)return;
log(function(s){s&&s.commit();});
open=false;act=-1;if(panel)panel.hidden=true;setExp(false);
clearTimeout(aiT);if(aiCtl){var c0=aiCtl;aiCtl=null;try{c0.abort();}catch(e){}}
if(ov&&!ov.hidden){
var m=mode;ov.hidden=true;lockPage(false);
try{w.visualViewport.removeEventListener("resize",vvh);w.visualViewport.removeEventListener("scroll",vvh);}catch(e){}
if(m==="sheet"&&pushed&&!fromPop){pushed=false;try{if(history.state&&history.state.pcs){ignorePop++;history.back();}}catch(e){}}
pushed=false;
if(restore&&trigger&&trigger.focus&&d.contains(trigger))try{trigger.focus({preventScroll:true});}catch(e){}
}
mode="";host=null;
}
w.addEventListener("popstate",function(e){
if(ignorePop){ignorePop--;e.stopImmediatePropagation();return;}
if(open&&mode==="sheet"&&!(history.state&&history.state.pcs)){pushed=false;close(true,true);e.stopImmediatePropagation();}
},true);
function sh(id,on){var s=R.secs[id];if(s)s.hidden=!on;}
function bold(text,terms,whole){
return String(text).split(/([\p{L}\p{N}'’]+)/u).map(function(seg,i){
if(!(i%2))return esc(seg);
var f=A.fold(seg),best="";
terms.forEach(function(t){if(t&&f.lastIndexOf(t,0)===0&&t.length>best.length)best=t;});
if(!best)return esc(seg);
if(whole||best.length>=f.length||f!==seg.toLowerCase())return"<b>"+esc(seg)+"</b>";
return"<b>"+esc(seg.slice(0,best.length))+"</b>"+esc(seg.slice(best.length));
}).join("");
}
function fillProd(e,p,terms){
var im=e.querySelector("img"),th=G("thumbOf"),src=p.img?(typeof th==="function"?th(p.img):p.img):"";
if(im.getAttribute("src")!==src){delete im.dataset.r;im.style.visibility="";if(src)im.src=src;else im.removeAttribute("src");}
e.href="/product/"+encodeURIComponent(p.id);e.__p=p;
e.querySelector(".pcs-pt").innerHTML=bold(p.title,terms,true);
var cn=G("catName");e.querySelector(".pcs-ps").textContent=[p.brand,typeof cn==="function"?cn(p.cat):p.cat].filter(Boolean).join(" · ");
var pp=G("pprice");e.querySelector(".pcs-pp").textContent=typeof pp==="function"?pp(p.price):"";
e.querySelector(".pcs-qc").hidden=!((p.qc||0)>=1);
}
function catLabel(c){var cn=G("catName");return typeof cn==="function"?cn(c):c;}
function catCount(){var by={};(all()||[]).forEach(function(p){by[p.cat]=(by[p.cat]||0)+1;});return by;}
function idFind(raw){
var f=A.fold(raw),ex=/^\d{6,}$/.test(f)?{id:f}:(/[\/.]/.test(raw)&&/\d{6,}/.test(raw)?(function(){try{var x=G("pcExtract");return x?x(raw):null;}catch(e){return null;}})():null);
if(!ex||!ex.id)return null;
var hits=(all()||[]).filter(function(p){return p.id===ex.id||String(p.itemId||"")===ex.id;});
return{id:ex.id,hits:hits,link:!/^\d+$/.test(f)};
}
function paint(){
if(!open||!panel)return;
var raw=host?host.value:"",f=A.fold(raw),e=f?ensure():null,H=function(id,k,fb,rep){var h=$("pcs-h-"+id);if(h)h.textContent=rep?rep(tr(k,fb)):tr(k,fb);};
try{list.setAttribute("aria-label",tr("pcs_list"));[["dym","pcs_dym_g"],["ai","pcs_ai_g"],["qc","pcs_qc_g"]].forEach(function(g){var x=$("pcs-g-"+g[0]);if(x)x.setAttribute("aria-label",tr(g[1]));});}catch(_){}
var secs=["rec","pop","cat","dym","none","open","br","ct","pr","cl","ai","qc"];secs.forEach(function(s){sh(s,false);});
R.all.hidden=true;lastN=0;lastQ=raw.trim();res=null;
if(!f){
var rc=recent();
if(rc.length){sh("rec",1);H("rec","pcs_recent","Recent");var cb=R.secs.rec.querySelector(".pcs-clr");cb.textContent=tr("pcs_clear");
R.rec.forEach(function(r,i){r.hidden=i>=rc.length;if(i<rc.length){r.querySelector(".pcs-t").textContent=rc[i];r.dataset.q=rc[i];r.querySelector(".pcs-x").setAttribute("aria-label",tr("pcs_remove").replace("{q}",rc[i]));}});}
popPaint();place("pop","cat");
sh("cat",1);H("cat","pcs_cats","Categories");var by=catCount();
R.cat.forEach(function(t){var c=t.dataset.cat;t.querySelector(".pcs-tl").textContent=catLabel(c);t.querySelector(".pcs-tn").textContent=nf(by[c]||0);});
}else{
var idr=idFind(raw);
if(idr){
lastN=idr.hits.length;
if(idr.hits.length){sh("open",1);H("open","pcs_open_find","Open this find");sh("pr",0);R.secs.open.lastChild.appendChild(R.pr[0]);fillProd(R.pr[0],idr.hits[0],[]);R.pr[0].hidden=false;R.all.hidden=false;}
else{none(raw);if(idr.link){sh("qc",1);R.qc.href="/tools/qc-checker?u="+encodeURIComponent(raw.trim());R.qc.querySelector(".pcs-t").textContent=tr("pcs_qc_link");}popPaint();place("pop","all");}
}else if(e){
if(R.pr[0].parentNode!==R.secs.pr.lastChild)R.secs.pr.lastChild.insertBefore(R.pr[0],R.secs.pr.lastChild.firstChild);
var r=res=e.search(raw);lastN=r.total;var terms=r.terms;
if(r.dym){sh("dym",1);R.dym.dataset.q=r.dym;R.dym.querySelector(".pcs-t").innerHTML=esc(tr("pcs_dym")).replace("{q}","<b>"+esc(r.dym)+"</b>");}
if(r.brands.length){sh("br",1);H("br","pcs_brands","Brands");}
R.br.forEach(function(x,i){var b=r.brands[i];x.hidden=!b;if(b){x.dataset.b=b.name;x.querySelector(".pcs-t").innerHTML=bold(b.name,terms.concat([r.f]),false);x.querySelector(".pcs-n").textContent=tr("pcs_finds").replace("{n}",nf(b.n));}});
if(r.cats.length){sh("ct",1);H("ct","pcs_cats","Categories");}
R.ct.forEach(function(x,i){var c=r.cats[i];x.hidden=!c;if(c){x.dataset.cat=c.cat;var u=(CATS.filter(function(k){return k[0]===c.cat;})[0]||[])[1],im=x.querySelector("img");if(u){if(im.getAttribute("src")!==u)im.src=u;im.hidden=false;}else im.hidden=true;x.querySelector(".pcs-t").textContent=catLabel(c.cat);x.querySelector(".pcs-n").textContent=tr("pcs_finds").replace("{n}",nf(c.n));}});
if(r.total){
sh("pr",1);H("pr","pcs_products","Products");
R.pr.forEach(function(x,i){var p=r.top[i];x.hidden=!p;if(p)fillProd(x,p,terms);});
R.all.hidden=false;
}else{
none(raw);
if(r.closest.length){sh("cl",1);H("cl","pcs_closest","Closest matches");}
R.cl.forEach(function(x,i){var p=r.closest[i];x.hidden=!p;if(p)fillProd(x,p,terms);});
aiAsk(raw,r.f);popPaint();place("pop","all");
}
}
if(!R.all.hidden)R.all.querySelector(".pcs-t").textContent=tr("pcs_all").replace("{n}",nf(lastN)).replace("{q}",raw.trim());
}
numberOpts();setAct(-1);
clearTimeout(liveT);liveT=setTimeout(function(){if(!open||!live)return;var s=opts.length-(R.all.hidden?0:1);live.textContent=(res&&res.dym?tr("pcs_dym").replace("{q}",res.dym)+" ":"")+(f&&!lastN&&res?tr("pcs_none").replace("{q}",raw.trim())+". ":"")+tr("pcs_live").replace("{s}",nf(s)).replace("{n}",nf(lastN));},400);
clearTimeout(logT);if(f){var q=raw.trim(),n=lastN;logT=setTimeout(function(){log(function(s){s&&s.q(q,n,kind());});},110);}/* search-log hook A (panel) */
}
function numberOpts(){
opts=[];
[].forEach.call(list.querySelectorAll('[role="option"]'),function(o){o.classList.remove("is-act","is-kb");o.setAttribute("aria-selected","false");if(!o.hidden&&!o.closest("[hidden]")){o.id="pcs-o-"+opts.length;opts.push(o);}else o.removeAttribute("id");});
act=-1;
}
function none(raw){sh("none",1);R.secs.none.lastChild.textContent=tr("pcs_none").replace("{q}",raw.trim());}
function place(id,before){var s=R.secs[id],b=before==="all"?R.all:R.secs[before];if(s&&b&&s.nextSibling!==b)list.insertBefore(s,b);}
function popPaint(){
var s=R.secs.pop;$("pcs-h-pop").textContent=tr("pcs_popular");
if(!POP){sh("pop",1);R.pop.forEach(function(c,i){c.hidden=i>=4;c.className="pcs-chip pcs-sk";c.textContent="";c.setAttribute("role","presentation");});return;}
sh("pop",POP.length>0);
R.pop.forEach(function(c,i){var q=POP[i];c.hidden=!q;c.className="pcs-chip";c.setAttribute("role","option");if(q){c.textContent=q;c.dataset.q=q;}});
}
function setAct(i){
if(opts[act]){opts[act].classList.remove("is-act","is-kb");opts[act].setAttribute("aria-selected","false");}
act=i;var o=opts[i];
if(host)host.setAttribute("aria-activedescendant",o?o.id:"");
if(o){o.classList.add("is-act");if(kb)o.classList.add("is-kb");o.setAttribute("aria-selected","true");if(kb)try{o.scrollIntoView({block:"nearest"});}catch(e){}}
}
function app(){var s=G("state"),r=G("render");return s&&typeof r==="function"?s:null;}
function toAll(){var el=$("v9-all")||d.querySelector(".toolbar")||$("grid");if(el)try{el.scrollIntoView({behavior:mq("(prefers-reduced-motion: reduce)")?"auto":"smooth",block:"start"});}catch(e){}}
function leaveDrawer(){try{var dr=$("drawer"),cd=G("closeDetail");if(dr&&dr.classList.contains("open")&&typeof cd==="function")cd();}catch(e){}}
function rerender(){leaveDrawer();try{var sq=G("syncQParam");if(typeof sq==="function")sq();}catch(e){}try{var u=G("updatePriceUI");if(typeof u==="function")u();}catch(e){}G("render")();}
function reset(s){s.saved=false;s.cat="all";s.cats=[];s.brand="all";s.color="all";s.plat="all";s.gender="all";s.pmin=null;s.pmax=null;s.price="all";}
function setQ(v){var q=$("q");if(q)q.value=v;[heroIn,hdIn].forEach(function(x){if(x&&x!==host)x.value=v;});}
function commit(v){
v=String(v==null?(host?host.value:""):v).trim();
var s=app();if(v)addRecent(v);
log(function(p){p&&p.commit();});
close(false);
if(!s){location.href="/?q="+encodeURIComponent(v);return;}
reset(s);s.q=v;setQ(v);rerender();toAll();
if(mq("(pointer: coarse)"))try{d.activeElement&&d.activeElement.blur();}catch(e){}
}
function fill(v){if(!host)return;host.value=v;if(host===oi)oclr.hidden=!v;try{host.setSelectionRange(v.length,v.length);}catch(e){}paint();}
function choose(o,ev){
if(!o)return;var s=app(),typed=host&&A.fold(host.value)?host.value:"";
if(o===R.all)return commit();
if(o===R.dym||o===R.ai||o.classList.contains("pcs-rr")||(o.classList.contains("pcs-chip")&&o.dataset.q))return fill(o.dataset.q);
if(o===R.qc){log(function(p){p&&p.commit();});close(false);location.href=o.href;return;}
if(o.__p){
if(ev&&(ev.metaKey||ev.ctrlKey||ev.shiftKey||ev.button===1))return;
if(ev)ev.preventDefault();
var od=G("openDetail");if(typed)addRecent(typed);
log(function(p){p&&p.open();});
close(false);
if(typeof od==="function")od(o.__p);else location.href=o.href;
return;
}
var cat=o.dataset.cat,br=o.dataset.b;
if(cat||br){
if(typed)addRecent(typed);
log(function(p){p&&p.commit();});close(false);
if(!s){location.href="/?q="+encodeURIComponent(br||cat);return;}
if(br){reset(s);s.brand=br;}else{s.cats=[cat];s.cat="all";s.saved=false;}
s.q="";setQ("");rerender();toAll();
}
}
function onClick(e){
var a=e.target.closest&&e.target.closest("[data-a]");
if(a&&a.dataset.a==="clr"){setRecent([]);paint();return;}
if(a&&a.dataset.a==="del"){e.preventDefault();e.stopPropagation();var r=a.closest(".pcs-rr");if(r)delRecent(r.dataset.q);paint();return;}
var o=e.target.closest&&e.target.closest('[role="option"]');
if(o&&opts.indexOf(o)>=0){if(o.tagName==="A"&&!o.__p&&o!==R.qc)e.preventDefault();if(o===R.qc)e.preventDefault();choose(o,e);}
}
var aiT=0,aiCtl=null,aiMemo={},aiCalls=0;
function aiOff(){try{return sessionStorage.getItem("pcs.ai.off")==="1";}catch(e){return false;}}
function aiStop(){try{sessionStorage.setItem("pcs.ai.off","1");}catch(e){}}
function aiShow(f,terms){
if(!open||!res||res.f!==f||res.total||!terms||!terms.length)return;
var q=terms.join(" "),r2=ensure()&&ensure().search(q);if(!r2||!r2.total)return;
sh("ai",1);R.ai.dataset.q=q;R.ai.innerHTML=ic("zap")+esc(tr("pcs_try").replace("{q}",q))+'<span class="pcs-ail">AI</span>';
var a=act;numberOpts();setAct(a);
}
function aiAsk(raw,f){
clearTimeout(aiT);
if(f.length<3||aiOff()||!w.fetch)return;
if(aiMemo[f]){aiShow(f,aiMemo[f]);return;}
aiT=setTimeout(function(){
if(aiCalls>=12||aiOff())return;aiCalls++;
if(aiCtl)try{aiCtl.abort();}catch(e){}
var ctl=aiCtl=w.AbortController?new AbortController():null,to=setTimeout(function(){if(ctl)ctl.abort();},2500);
fetch("/api/ai-search",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({q:raw.trim().slice(0,80)}),signal:ctl?ctl.signal:undefined})
.then(function(r){if(!r.ok){if([404,405,501].indexOf(r.status)>=0)aiStop();return null;}return r.json();})
.then(function(j){clearTimeout(to);if(!j)return;if(j.ai===false){aiStop();return;}var t=(Array.isArray(j.terms)?j.terms:[]).filter(function(x){return typeof x==="string"&&x.length<40;}).slice(0,4);aiMemo[f]=t;aiShow(f,t);})
.catch(function(e){clearTimeout(to);if(ctl!==aiCtl)return;aiStop();});
},450);
}
function schedule(){
if(rafId)return;rafId=1;
var run=function(){if(!rafId)return;rafId=0;clearTimeout(tmo);paint();},tmo=setTimeout(run,50);
if(w.requestAnimationFrame)w.requestAnimationFrame(run);
}
function move(dl){if(!opts.length)return;kb=true;var n=act<0?(dl>0?0:opts.length-1):(act+dl+opts.length)%opts.length;setAct(n);}
function wire(inp){
if(!inp||inp.__pcs)return;inp.__pcs=1;
inp.setAttribute("role","combobox");inp.setAttribute("aria-autocomplete","list");inp.setAttribute("aria-expanded","false");inp.setAttribute("aria-controls","pcs-list");inp.setAttribute("aria-activedescendant","");
inp.addEventListener("input",function(){if(inp===oi)oclr.hidden=!oi.value;if(!open||host!==inp){if(!start(inp))return;}schedule();});
inp.addEventListener("focus",function(){if(inp!==oi&&!(open&&host===inp))start(inp);});
inp.addEventListener("keydown",function(e){
if(e.isComposing||e.keyCode===229)return;
var k=e.key;
if(k==="ArrowDown"||k==="ArrowUp"){e.preventDefault();if(!open||host!==inp){start(inp);return;}if(e.altKey&&k==="ArrowDown")return;move(k==="ArrowDown"?1:-1);return;}
if(k==="Enter"){e.preventDefault();e.stopPropagation();if(open&&host===inp&&opts[act])choose(opts[act]);else{host=inp;commit(inp.value);}return;}
if(k==="Escape"){
e.stopPropagation();
if(open&&host===inp){if(mode==="inline"){close(false);}else close(true);e.preventDefault();return;}
if(inp.value){inp.value="";e.preventDefault();}
return;
}
if(k==="Delete"&&e.shiftKey&&opts[act]&&opts[act].classList.contains("pcs-rr")){e.preventDefault();delRecent(opts[act].dataset.q);paint();return;}
if(k==="Tab"&&mode==="inline")close(false);
});
inp.addEventListener("blur",function(){setTimeout(function(){if(open&&mode==="inline"&&host===inp&&d.activeElement!==inp)close(false);},0);});
}
function start(inp){
if(inp===oi){openAt(oi,mode||"pal");return true;}
if(inp===heroIn&&sheetish())return false;
openAt(inp,"inline");return true;
}
function launch(from){
if(hdIn&&hdIn.offsetParent!==null&&hdIn.getBoundingClientRect().width>0){hdIn.focus();return;}
if(open&&mode!=="inline"){oi.focus();return;}
if(open)close(false);
openOv(sheetish()?"sheet":"pal",from);
}
var heroIn=$("v9-q"),hdIn=$("pcs-hi"),hb=$("pcs-hb");
wire(heroIn);wire(hdIn);
if(heroIn)heroIn.addEventListener("click",function(){if(sheetish()&&!(open&&mode==="sheet")){heroIn.blur();openOv("sheet",heroIn);}});
if(hb)hb.addEventListener("click",function(){launch(hb);});
var hf=hdIn&&hdIn.form;if(hf)hf.addEventListener("submit",function(e){if(app()){e.preventDefault();host=hdIn;commit(hdIn.value);}});
try{var kbd=d.querySelector("#pcs-hd .pcs-kbd");if(kbd)kbd.textContent=/Mac|iPhone|iPad|iPod/.test(navigator.platform||navigator.userAgent)?"⌘K":"Ctrl K";}catch(e){}
d.addEventListener("keydown",function(e){
if((e.key==="k"||e.key==="K")&&(e.metaKey||e.ctrlKey)&&!e.altKey){e.preventDefault();launch(d.activeElement);return;}
if(e.key==="/"&&!e.metaKey&&!e.ctrlKey&&!e.altKey){
var a=d.activeElement,tg=a&&a.tagName;
if(tg==="INPUT"||tg==="TEXTAREA"||tg==="SELECT"||(a&&a.isContentEditable))return;
e.preventDefault();launch(a);
}
});
d.addEventListener("pointerdown",function(e){if(open&&mode==="inline"&&panel&&!panel.contains(e.target)&&e.target!==host)close(false);},true);
w.addEventListener("resize",function(){if(open&&mode==="inline"&&host){if(host.offsetParent===null)close(false);else if(host===heroIn)posHero();}});
try{
var u=new URL(location.href);
if(u.searchParams.get("s")==="1"){
u.searchParams.delete("s");history.replaceState(history.state,"",u.pathname+u.search+u.hash);
var go=function(){launch(null);};if(d.readyState==="complete")setTimeout(go,0);else w.addEventListener("load",go,{once:true});
}
}catch(e){}
PCS.commit=function(v){host=host||heroIn;commit(v);};
PCS.open=function(){launch(null);};
PCS.close=function(){close(true);};
})();
