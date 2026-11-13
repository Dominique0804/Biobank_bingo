const TERMS=[
['Metadata','Your phone saves the date and place each photo was taken. What is this kind of information about a sample called?'],
['Informed consent','Before donating a sample, you learn how it may be used and agree. What is this called?'],
['−80 °C freezer','Which very cold appliance can preserve biological samples for long periods?'],
['Saliva','What liquid from your mouth can be collected as a biological sample?'],
['Unique ID','What code makes it possible to tell one sample apart from another?'],
['Ethics approval','What permission from an independent committee helps protect people in research?'],
['DNA','What molecule contains the genetic instructions of living things?'],
['Backup power','What keeps the freezers running if the electricity goes off?'],
['Tissue','What do we call a collection of cells taken from a body for research?'],
['Withdrawal','What is it called when a participant chooses to stop taking part in research?'],
['Privacy code','What replaces a donor’s name on a sample record to help protect their identity?'],
['Research','What is a systematic investigation that tries to answer questions and create knowledge?'],
['Liquid nitrogen','What extremely cold liquid can be used to preserve samples?'],
['Donor','What do we call a person who provides a biological sample?'],
['POPIA','Which South African law protects personal information?'],
['Access committee','Which group reviews requests to use stored samples or data?']
];
const $=id=>document.getElementById(id);
const cfg=window.BINGO_CONFIG||{};
let db=null,code='',hostToken='',playerToken='',state=null,loading=false;
const colors=['pink','gold','green','blue'];
function notice(s,error=false){$('notice').textContent=s;$('notice').className='notice '+(error?'error':'ok');$('notice').style.display=s?'block':'none';}
function getSaved(k){return localStorage.getItem('bb_'+k)||'';}
function save(k,v){localStorage.setItem('bb_'+k,v);}
function randomToken(){const bytes=new Uint8Array(32);crypto.getRandomValues(bytes);return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function rpc(name,args={}){if(!db)throw Error('Configure Supabase in config.js first.');const {data,error}=await db.rpc('bingo_'+name,args);if(error)throw Error(error.message);return data;}
async function run(fn){if(loading)return;loading=true;try{await fn();notice('');}catch(e){notice(e.message,true);}finally{loading=false;}}
function navigate(path){history.pushState({},'',path);loadRoute();}
function urlFor(c){return location.origin+location.pathname+'?game='+encodeURIComponent(c);}
async function refresh(){if(!code||!db)return;try{state=await rpc('state',{p_code:code,p_host_token:hostToken||null,p_player_token:playerToken||null});render();}catch(e){notice(e.message,true);}}
function render(){if(!state)return;
 if(hostToken){$('playerCount').textContent=state.players;$('calledCount').textContent=state.called.length;$('hostStatus').textContent=state.finished?'Finished':'Live';$('finish').disabled=state.finished;renderClues();$('winners').innerHTML=state.winners.length?state.winners.map(w=>'<p>🏆 '+escapeHtml(w.name)+' — '+escapeHtml(w.kind)+'</p>').join(''):'No winners yet.';}
 else if(state.player){$('playerJoin').hidden=true;$('playerBoard').hidden=false;$('greeting').textContent=state.player.name+'’s card';$('gameStatus').textContent=state.finished?'Finished':'Live';$('claim').disabled=state.finished;renderCard();$('calledTerms').textContent=state.called.length?state.called.map(i=>TERMS[i][0]).join(' · '):'None yet';}
}
function renderClues(){const called=state.called||[];$('clues').innerHTML=TERMS.map(([term,clue],i)=>'<article class="clue '+(called.includes(i)?'called':'')+'"><div class="clue-text"><span class="eyebrow">CLUE '+(i+1)+'</span><p>'+escapeHtml(clue)+'</p><div class="answer">'+(called.includes(i)?'Answer: '+escapeHtml(term):'Answer hidden until revealed')+'</div></div><button data-call="'+i+'" '+(called.includes(i)||state.finished?'disabled':'')+'>'+(called.includes(i)?'Called ✓':'Reveal answer')+'</button></article>').join('');}
function renderCard(){const p=state.player;$('grid').innerHTML=p.card.map((term,i)=>'<button class="square '+colors[term%4]+' '+(p.marked.includes(i)?'marked':'')+'" data-mark="'+i+'" aria-pressed="'+p.marked.includes(i)+'" '+(state.finished?'disabled':'')+'><span class="ring">'+(p.marked.includes(i)?'✓':'')+'</span><span>'+escapeHtml(TERMS[term][0])+'</span></button>').join('');}
function loadRoute(){code=new URLSearchParams(location.search).get('game')?.trim().toUpperCase()||'';hostToken=code?getSaved('host_'+code):'';playerToken=code?getSaved('player_'+code):'';const host=!!hostToken;
 $('home').hidden=!!code;$('host').hidden=!code||!host;$('player').hidden=!code||host;state=null;
 if(!code)return;
 if(host){$('hostCode').textContent=code;const link=urlFor(code);$('joinUrl').textContent=link;$('qr').innerHTML='';if(typeof QRCode!=='undefined')new QRCode($('qr'),{text:link,width:200,height:200,colorDark:'#102b44',colorLight:'#ffffff'});else $('qr').textContent='QR library unavailable — share the link below.';}
 else{$('playerCode').textContent=code;$('playerJoin').hidden=false;$('playerBoard').hidden=true;}
 refresh();}
$('create').onclick=()=>run(async()=>{const x=await rpc('create');save('host_'+x.code,x.host_token);navigate('?game='+x.code);});
$('joinCode').onclick=()=>{const c=$('codeInput').value.trim().toUpperCase();if(!/^[A-Z2-9]{6}$/.test(c)){notice('Enter a six-character game code.',true);return;}navigate('?game='+c);};
$('joinGame').onclick=()=>run(async()=>{const name=$('playerName').value.trim();if(!name){notice('Enter your display name.',true);return;}const t=playerToken||randomToken();await rpc('join',{p_code:code,p_name:name,p_player_token:t});save('player_'+code,t);playerToken=t;await refresh();});
$('clues').onclick=e=>{const b=e.target.closest('[data-call]');if(!b)return;run(async()=>{await rpc('call',{p_code:code,p_host_token:hostToken,p_term:Number(b.dataset.call)});await refresh();});};
$('grid').onclick=e=>{const b=e.target.closest('[data-mark]');if(!b)return;run(async()=>{await rpc('mark',{p_code:code,p_player_token:playerToken,p_position:Number(b.dataset.mark)});await refresh();});};
$('claim').onclick=()=>run(async()=>{const r=await rpc('claim',{p_code:code,p_player_token:playerToken});$('playerFeedback').textContent=r.message;await refresh();});
$('finish').onclick=()=>{if(!confirm('End this game for everyone?'))return;run(async()=>{await rpc('finish',{p_code:code,p_host_token:hostToken});await refresh();});};
$('copyLink').onclick=async()=>{try{await navigator.clipboard.writeText(urlFor(code));notice('Join link copied.');}catch{notice('Copy the link displayed above.');}};
window.addEventListener('popstate',loadRoute);
if(cfg.supabaseUrl?.startsWith('https://')&&cfg.supabaseAnonKey&&!cfg.supabaseAnonKey.startsWith('PASTE_')&&window.supabase){db=window.supabase.createClient(cfg.supabaseUrl,cfg.supabaseAnonKey,{auth:{persistSession:false,autoRefreshToken:false}});}else{notice('Setup required: enter your Supabase URL and publishable key in config.js.',true);}
loadRoute();setInterval(()=>{if(code&&db&&document.visibilityState==='visible'&&!loading)refresh();},3000);
