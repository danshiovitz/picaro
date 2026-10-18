import {GameStore} from './store';
import type {ActionResponse,ActiveEncounter,EncounterSkillCheck,FinishEncounterResponse,GameData,Hex,PlayerEntity,PlayCard,RunEncounterResponse,TableauCard,TableauData} from './types';

const API=import.meta.env.VITE_API_URL??'';
const PLAYER_NAME='Player 1';
const app=document.querySelector('#app')!;

type Point={x:number;y:number};

async function apiJson<T>(path:string,init?:RequestInit,attempts=1):Promise<T>{
 let lastError:unknown;
 for(let i=0;i<attempts;i++){
  try{
   const r=await fetch(`${API}${path}`,init);
   if(!r.ok){
    let message=`API request failed: ${r.status}`;
    try{const body=await r.json(); message=body?.message??body?.error??message;}catch{}
    throw new Error(message);
   }
   return r.json();
  }catch(err){
   lastError=err;
   if(i<attempts-1)await new Promise(resolve=>setTimeout(resolve,500));
  }
 }
 throw lastError;
}

Promise.all([
 apiJson<GameData>('/api/game',undefined,20),
 apiJson<PlayerEntity>(`/api/entities/${encodeURIComponent(PLAYER_NAME)}`,undefined,20),
 apiJson<TableauData>('/api/tableau',undefined,20),
]).then(([d,player,tableau])=>render(new GameStore(d),player,tableau)).catch(err=>{
 console.error(err);
 app.innerHTML=`<main style="padding:24px"><h2>Unable to load game data</h2><p>${err instanceof Error?err.message:String(err)}</p><p>Check that the API server is running on port 3001.</p></main>`;
});

function esc(value:unknown){
 return String(value).replace(/[&<>"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]!));
}

function outcomeLine(rewards:string[],penalties:string[]){
 const parts=[...rewards.map(item=>`+${item}`),...penalties.map(item=>`-${item}`)];
 return `Outcome: ${parts.join(', ')}`;
}

function skillLine(check:EncounterSkillCheck){
 return `${check.name} vs ${check.target}`;
}


type EncounterCard=TableauCard;

function renderEncounterCard(card:EncounterCard){
 const circles=Array.from({length:5},(_,i)=>`<span class="encounter-pip ${i<card.difficulty?'filled':''}" aria-hidden="true"></span>`).join('');
 return `<article class="play-card encounter-card tableau-encounter" data-encounter-id="${esc(card.id)}">
  <div class="encounter-header">
   <div class="encounter-title-row">
    <span class="encounter-title">${esc(card.title)}</span>
   </div>
   <div class="encounter-meta-row">
    <span class="encounter-location">${esc(card.location)}</span>
    <span class="encounter-ranks">${circles}</span>
   </div>
  </div>
  <div class="play-card-body encounter-body">
   <p>${esc(outcomeLine(card.rewards,card.penalties))}</p>
   <div class="encounter-spacer"></div>
   ${card.skillChecks.map(check=>`<p class="encounter-check">${esc(skillLine(check))}</p>`).join('')}
  </div>
 </article>`;
}

function renderActiveEncounterCard(card:ActiveEncounter){
 return `<article class="play-card encounter-card active-encounter-card" data-encounter-id="${esc(card.id)}">
  <div class="encounter-header">
   <div class="encounter-title-row">
    <span class="encounter-title">${esc(card.title)}</span>
   </div>
  </div>
  <div class="play-card-body encounter-body">
   <p>${esc(outcomeLine(card.rewards,card.penalties))}</p>
   <div class="encounter-spacer"></div>
   ${card.skillChecks.map(check=>`<p class="encounter-check">${esc(`${check.name} vs ${check.target}`)}</p><p class="encounter-result">${esc(`1d10 (${check.roll}) + ${check.modifier} = ${check.total} .. ${check.success?'Success! ✅':'Failure! ☠️'}`)}</p>`).join('')}
  </div>
 </article>`;
}

function render(store:GameStore,player:PlayerEntity,tableau:TableauData){
 const encounterById=new Map(tableau.encounters.map(encounter=>[encounter.id, encounter] as const));
 const encounterByLocation=new Map(tableau.encounters.map(encounter=>[encounter.location, encounter] as const));
 app.innerHTML=`<div class="layout"><main><section class="top-strip"><div class="bar"><button id="minus">-</button><span id="z"></span><button id="plus">+</button><button id="fit">Fit</button><button id="snap">Snap</button></div></section><div class="map-shell"><div class="map-pane"><div id="map-scroll"><div id="map"></div><section class="tableau">${tableau.encounters.map(renderEncounterCard).join('')}</section></div></div><section class="map-side"><section class="character-summary"><h2>Character</h2><div id="character-stats"></div></section><section class="action-section"><button id="travel" class="action-button" type="button"><img src="/images/actions/boots.svg" alt=""/><span>Travel</span></button><button id="camp" class="action-button" type="button"><img src="/images/actions/campfire.svg" alt=""/><span>Camp</span></button><button id="attack" class="action-button" type="button"><img src="/images/actions/swords.svg" alt=""/><span>Attack</span></button></section><section class="play-section"><div id="play-content"></div></section></section></div></main><aside><h2>Picaro</h2><p>Bogus right-panel intelligence reports, rumors, inventories, and diplomacy notes.</p></aside><footer><b>Log</b><p>Bogus bottom panel: marching orders, dice results, chat, and event feed will appear here.</p></footer></div><div id="tip"></div>`;
 const map=document.querySelector('#map') as HTMLElement;
 const mapScroll=document.querySelector('#map-scroll') as HTMLElement;
 const tip=document.querySelector('#tip') as HTMLElement;
 const stats=document.querySelector('#character-stats') as HTMLElement;
 const playContent=document.querySelector('#play-content') as HTMLElement;
 const tableauEl=document.querySelector('.tableau') as HTMLElement;
 const actionButtons=[...document.querySelectorAll('.action-button')] as HTMLButtonElement[];
 let zoom=.72;
 const size=44;
 const w=Math.sqrt(3)*size,h=2*size;
 const svgNS='http://www.w3.org/2000/svg';
 let route:string[]|null=null;
 let busy=false;
 let manualZoom=false;
 let centerPlayerAfterDraw=false;
 const mapBounds=store.data.hexes.reduce((acc,hex)=>{
  const {x,y}=hexCenter(hex);
  return {
   minX:Math.min(acc.minX,x-size),
   minY:Math.min(acc.minY,y-size),
   maxX:Math.max(acc.maxX,x+size),
   maxY:Math.max(acc.maxY,y+size),
  };
 },{minX:Infinity,minY:Infinity,maxX:-Infinity,maxY:-Infinity});

 function updateActionButtons(){
  const hasPlay=playContent.innerHTML.trim().length>0;
  actionButtons.forEach(button=>button.disabled=busy||hasPlay);
 }
 function setPlay(html:string){playContent.innerHTML=html; updateActionButtons();}
 function clearPlay(){playContent.innerHTML=''; updateActionButtons();}
 function hexCenter(hex:Hex):Point{return {x:(Math.sqrt(3)*size)*(hex.q+hex.r/2)+70,y:size*1.5*hex.r+60};}
 function isAdjacent(a:Hex,b:Hex){return store.distance(a,b)===1;}
 function clamp(value:number,min:number,max:number){return Math.max(min,Math.min(max,value));}

 function renderSummary(){
  stats.innerHTML=`<dl><div><dt>Name</dt><dd>${esc(player.name)}</dd></div><div><dt>Health</dt><dd>${player.curHealth}/${player.maxHealth}</dd></div><div><dt>Luck</dt><dd>${player.curLuck}/${player.maxLuck}</dd></div><div><dt>Gold</dt><dd>${player.gold}</dd></div><div><dt>Reputation</dt><dd>${player.reputation}</dd></div><div><dt>Turns</dt><dd>${player.turns}</dd></div><div><dt>Location</dt><dd>${esc(player.location)}</dd></div></dl>`;
 }

 function showGenericCard(card:PlayCard,buttonText='OK',onClick=clearPlay){
  setPlay(`<article class="play-card"><h3>${esc(card.title)}</h3><div class="play-card-body">${card.lines.map(line=>`<p>${esc(line)}</p>`).join('')}</div></article><button id="card-ok" class="card-ok" type="button">${esc(buttonText)}</button>`);
  document.querySelector('#card-ok')!.addEventListener('click',onClick);
 }

 function showEncounterPreview(card:EncounterCard){
  setPlay(`${renderEncounterCard(card)}<div class="encounter-controls"><button id="encounter-ok" class="card-ok" type="button">OK</button><button id="encounter-cancel" class="card-ok" type="button">Cancel</button></div>`);
  document.querySelector('#encounter-cancel')!.addEventListener('click',clearPlay);
  document.querySelector('#encounter-ok')!.addEventListener('click',()=>void runEncounter(card.id));
 }

 function showActiveEncounter(card:ActiveEncounter){
  setPlay(`${renderActiveEncounterCard(card)}<div class="encounter-controls"><button id="encounter-finish" class="card-ok" type="button">OK</button></div>`);
  document.querySelector('#encounter-finish')!.addEventListener('click',()=>void finishEncounter(card.id));
 }

 function showEncounterError(message:string){
  showGenericCard({title:'Encounter Error',lines:[message]},'OK',clearPlay);
 }

 function showEncounterResults(card:PlayCard){
  showGenericCard(card,'OK',clearPlay);
 }

 async function runEncounter(encounterId:string){
  busy=true;
  updateActionButtons();
  try{
   const result=await apiJson<RunEncounterResponse>(`/api/entities/${encodeURIComponent(player.name)}/actions/run_encounter`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({encounterId})});
   showActiveEncounter(result.encounter);
  }catch(err){
   console.error(err);
   showEncounterError(err instanceof Error?err.message:String(err));
  }finally{
   busy=false;
   updateActionButtons();
  }
 }

 async function finishEncounter(encounterId:string){
  busy=true;
  updateActionButtons();
  try{
   const result=await apiJson<FinishEncounterResponse>(`/api/entities/${encodeURIComponent(player.name)}/actions/finish_encounter`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({encounterId})});
   Object.assign(player,result.updates);
   renderSummary();
   showEncounterResults(result.card);
  }catch(err){
   console.error(err);
   showEncounterError(err instanceof Error?err.message:String(err));
  }finally{
   busy=false;
   updateActionButtons();
  }
 }

 function enterTravelMode(){
  if(busy||playContent.innerHTML.trim().length>0)return;
  route=[player.location];
  map.classList.add('travel-mode');
  tip.style.display='none';
  showTravelCard();
  draw();
 }

 function showTravelCard(){
  setPlay(`<article class="play-card travel-card"><h3>Travel</h3><div class="play-card-body route-body"><p>${esc(route!.join(' - '))}</p></div></article><div class="travel-controls"><button id="travel-go" class="card-ok" type="button">Go</button><button id="travel-cancel" class="card-ok" type="button">Cancel</button></div>`);
  document.querySelector('#travel-cancel')!.addEventListener('click',exitTravelMode);
  document.querySelector('#travel-go')!.addEventListener('click',goTravel);
 }

 function showTravelError(message:string){
  setPlay(`<article class="play-card error-card"><h3>Travel Error</h3><div class="play-card-body route-body"><p>${esc(message)}</p></div></article><button id="card-ok" class="card-ok" type="button">OK</button>`);
  document.querySelector('#card-ok')!.addEventListener('click',clearPlay);
 }

 function exitTravelMode(){
  route=null;
  map.classList.remove('travel-mode');
  clearPlay();
  draw();
 }

 function shortestPath(fromName:string,toName:string){
  const start=store.hexes.get(fromName),target=store.hexes.get(toName);
  if(!start||!target)return [fromName];
  const queue=[start];
  const cameFrom=new Map<string,string|null>([[start.name,null]]);
  const dirs=[[1,0],[1,-1],[0,-1],[-1,0],[-1,1],[0,1]];
  for(let qi=0;qi<queue.length;qi++){
   const current=queue[qi];
   if(current.name===target.name)break;
   for(const [dq,dr] of dirs){
    const next=store.data.hexes.find(h=>h.q===current.q+dq&&h.r===current.r+dr);
    if(next&&!cameFrom.has(next.name)){cameFrom.set(next.name,current.name); queue.push(next);}
   }
  }
  if(!cameFrom.has(target.name))return [fromName];
  const path:string[]=[];
  for(let name:string|null=target.name;name;name=cameFrom.get(name)??null)path.push(name);
  return path.reverse();
 }

 function selectRouteHex(hex:Hex){
  if(!route)return;
  const existing=route.indexOf(hex.name);
  if(existing>=0)route=route.slice(0,existing+1);
  else{
   const last=store.hexes.get(route[route.length-1])!;
   if(isAdjacent(last,hex))route.push(hex.name);
   else route.push(...shortestPath(last.name,hex.name).slice(1));
  }
  showTravelCard();
  draw();
 }

 async function goTravel(){
  if(!route)return;
  const submittedRoute=[...route];
  route=null;
  map.classList.remove('travel-mode');
  busy=true;
  updateActionButtons();
  draw();
  try{
   const result=await apiJson<ActionResponse>(`/api/entities/${encodeURIComponent(player.name)}/actions/travel`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({route:submittedRoute})});
   const oldLocation=player.location;
   Object.assign(player,result.updates);
   if(result.updates.location&&result.updates.location!==oldLocation)moveLocalPlayerToken(oldLocation,result.updates.location);
   renderSummary();
   clearPlay();
   draw();
  }catch(err){
   console.error(err);
   showTravelError(err instanceof Error?err.message:String(err));
  }finally{
   busy=false;
   updateActionButtons();
  }
 }

 function moveLocalPlayerToken(from:string,to:string){
  const fromHex=store.hexes.get(from),toHex=store.hexes.get(to);
  if(!fromHex||!toHex)return;
  fromHex.tokens=fromHex.tokens.filter(id=>id!==player.tokenId);
  if(!toHex.tokens.includes(player.tokenId))toHex.tokens.push(player.tokenId);
  store.tokenHex.set(player.tokenId,toHex);
 }

 function fitInitialZoom(){
  const padding=90;
  const boundsWidth=Math.max(1,mapBounds.maxX-mapBounds.minX+padding*2);
  const boundsHeight=Math.max(1,mapBounds.maxY-mapBounds.minY+padding*2);
  const availableWidth=Math.max(1,mapScroll.clientWidth-24);
  const availableHeight=Math.max(1,mapScroll.clientHeight-tableauEl.offsetHeight-24);
  zoom=Math.max(.05,Math.min(1.6,Math.min(availableWidth/boundsWidth,availableHeight/boundsHeight)));
 }

 function centerOnPlayer(){
  const padding=90;
  const hex=store.hexes.get(player.location);
  if(!hex)return;
  const {x,y}=hexCenter(hex);
  const left=(x-(mapBounds.minX-padding))*zoom;
  const top=(y-(mapBounds.minY-padding))*zoom;
  const viewportWidth=Math.max(1,mapScroll.clientWidth);
  const viewportHeight=Math.max(1,mapScroll.clientHeight-tableauEl.offsetHeight);
  const maxScrollLeft=Math.max(0,mapScroll.scrollWidth-viewportWidth);
  const maxScrollTop=Math.max(0,mapScroll.scrollHeight-viewportHeight);
  mapScroll.scrollLeft=clamp(left-viewportWidth/2,0,maxScrollLeft);
  mapScroll.scrollTop=clamp(top-viewportHeight/2,0,maxScrollTop);
 }

 function draw(){
  document.querySelector('#z')!.textContent=`${Math.round(zoom*100)}%`;
  map.innerHTML='';
  const svg=document.createElementNS(svgNS,'svg');
  const padding=90;
  const width=Math.max(1,mapBounds.maxX-mapBounds.minX+padding*2);
  const height=Math.max(1,mapBounds.maxY-mapBounds.minY+padding*2);
  svg.style.width=`${width*zoom}px`;
  svg.style.height=`${height*zoom}px`;
  svg.setAttribute('viewBox',`${mapBounds.minX-padding} ${mapBounds.minY-padding} ${width} ${height}`);
  const defs=document.createElementNS(svgNS,'defs');
  store.data.terrains.forEach(t=>{defs.innerHTML+=`<pattern id="p-${t.icon}" width="12" height="12" patternUnits="userSpaceOnUse"><image href="/images/terrain/${t.icon}.svg" width="12" height="12"/></pattern>`});
  svg.append(defs);
  for(const hex of store.data.hexes){
   const {x:cx,y:cy}=hexCenter(hex);
   const terr=store.terrains.get(hex.terrain);
   const g=document.createElementNS(svgNS,'g');
   g.classList.add('hex');
   g.dataset.name=hex.name;
   const pts=[0,1,2,3,4,5].map(i=>{const a=Math.PI/180*(60*i-30);return `${cx+size*Math.cos(a)},${cy+size*Math.sin(a)}`}).join(' ');
   g.innerHTML=`<polygon points="${pts}" fill="${terr.color}" stroke="#222"/><polygon points="${pts}" fill="url(#p-${terr.icon})" opacity=".35" stroke="#222"/>`;
   if(zoom>.45)g.innerHTML+=`<text x="${cx}" y="${cy-24}" text-anchor="middle" class="name">${hex.name}</text>`;
   const toks=hex.tokens.map(id=>store.tokens.get(id)!);
   toks.forEach((t,i)=>{const separate=zoom>.38; g.innerHTML+=`<image href="/images/tokens/${t.icon}.svg" x="${cx-18+(separate?(i-(toks.length-1)/2)*24:0)}" y="${cy-18}" width="36" height="36"/>`});
   if(zoom>.55)hex.claims.forEach((c,i)=>{const cl=store.claims.get(c); g.innerHTML+=`<image href="/images/claims/${cl.icon}.svg" x="${cx-24+i*16}" y="${cy+22}" width="14" height="14"/>`});
   if(encounterByLocation.has(hex.name))g.innerHTML+=`<text x="${cx}" y="${cy+10}" text-anchor="middle" class="encounter-star" aria-hidden="true">★</text>`;
   g.onclick=e=>{e.stopPropagation(); route?selectRouteHex(hex):showTip(hex,g.getBoundingClientRect())};
   let timer:any;
   g.onmouseenter=()=>timer=setTimeout(()=>{if(!route)showTip(hex,g.getBoundingClientRect())},700);
   g.onmouseleave=()=>clearTimeout(timer);
   svg.append(g);
  }
  if(route&&route.length>1){
   const overlay=document.createElementNS(svgNS,'g');
   overlay.classList.add('route-overlay');
   for(let i=1;i<route.length;i++){
    const a=store.hexes.get(route[i-1])!,b=store.hexes.get(route[i])!;
    const ac=hexCenter(a),bc=hexCenter(b);
    const line=document.createElementNS(svgNS,'line');
    line.setAttribute('x1',String(ac.x)); line.setAttribute('y1',String(ac.y));
    line.setAttribute('x2',String(bc.x)); line.setAttribute('y2',String(bc.y));
    overlay.append(line);
   }
   svg.append(overlay);
  }
  map.append(svg);
  if(centerPlayerAfterDraw){
   centerPlayerAfterDraw=false;
   requestAnimationFrame(()=>centerOnPlayer());
  }
 }

 function formatClaims(claims:string[]){
  const counts=new Map<string,number>();
  for(const claim of claims)counts.set(claim,(counts.get(claim)??0)+1);
  return [...counts.entries()].map(([name,count])=>count>1?`${name} (x${count})`:name).join(', ');
 }

 function formatTokens(tokens:{entityName:string}[]){
  return tokens.map(token=>token.entityName).join(', ');
 }

 function showTip(hex:Hex,anchor:DOMRect){
  const f=store.fullHex(hex.name)!;
  const claimsText=formatClaims(f.claimObjs.filter((claim): claim is NonNullable<typeof claim> => Boolean(claim)).map(claim=>claim.name));
  const tokenText=formatTokens(f.tokenObjs.filter((token): token is NonNullable<typeof token> => Boolean(token)));
  const encounter=encounterByLocation.get(hex.name);
  const lines:[string,string][]=[['Terrain',esc(f.terrain)],['Region',esc(f.region)]];
  if(claimsText)lines.push(['Claims',esc(claimsText)]);
  if(tokenText)lines.push(['Tokens',esc(tokenText)]);
  if(encounter)lines.push(['Encounter',`<a class="encounter-link" href="#" data-encounter-id="${esc(encounter.id)}">${esc(encounter.title)}</a>`]);
  const details=lines.map(([label,value])=>`<p><b>${label}:</b> ${value}</p>`).join('');
  tip.style.display='block';
  tip.style.visibility='hidden';
  tip.style.left='0px';
  tip.style.top='0px';
  tip.innerHTML=`<button id="close">×</button><h3>${f.name}</h3>${details}<a id="move-here" href="#">Move here</a>`;
  const bounds=tip.getBoundingClientRect();
  const gap=12;
  let x=anchor.right+gap;
  let y=anchor.top;
  if(x+bounds.width>window.innerWidth) x=anchor.left-bounds.width-gap;
  if(y+bounds.height>window.innerHeight) y=window.innerHeight-bounds.height-gap;
  x=Math.max(gap, x);
  y=Math.max(gap, y);
  tip.style.left=`${x}px`;
  tip.style.top=`${y}px`;
  tip.style.visibility='visible';
  document.querySelector('#close')!.addEventListener('click',()=>tip.style.display='none');
  document.querySelector('#move-here')!.addEventListener('click',e=>{e.preventDefault(); e.stopPropagation(); enterTravelMode(); if(route)selectRouteHex(hex);});
  document.querySelector('.encounter-link')?.addEventListener('click',e=>{
   e.preventDefault();
   e.stopPropagation();
   const encounterId=(e.currentTarget as HTMLElement).dataset.encounterId;
   const encounter=encounterId?encounterById.get(encounterId):undefined;
   if(encounter)showEncounterPreview(encounter);
  });
 }

 tableauEl.addEventListener('click',e=>{
  const card=(e.target as HTMLElement).closest('.tableau-encounter') as HTMLElement | null;
  if(!card)return;
  const encounterId=card.dataset.encounterId;
  const encounter=encounterId?encounterById.get(encounterId):undefined;
  if(encounter)showEncounterPreview(encounter);
 });

 document.addEventListener('click',e=>{if(!(e.target as HTMLElement).closest('#tip'))tip.style.display='none'});
 map.addEventListener('scroll',()=>{tip.style.display='none'});
 map.onwheel=e=>{e.preventDefault(); manualZoom=true; zoom=Math.max(.22,Math.min(1.6,zoom+(e.deltaY<0?.08:-.08))); draw()};
 document.querySelector('#plus')!.addEventListener('click',()=>{manualZoom=true; zoom=Math.min(1.6,zoom+.1);draw()});
 document.querySelector('#minus')!.addEventListener('click',()=>{manualZoom=true; zoom=Math.max(.22,zoom-.1);draw()});
 document.querySelector('#fit')!.addEventListener('click',()=>{manualZoom=false; fitInitialZoom(); draw()});
 document.querySelector('#snap')!.addEventListener('click',()=>{manualZoom=true; zoom=1; centerPlayerAfterDraw=true; draw()});
 document.querySelector('#travel')!.addEventListener('click',enterTravelMode);
 document.querySelector('#camp')!.addEventListener('click',async()=>{
  busy=true;
  updateActionButtons();
  try{
   const result=await apiJson<ActionResponse>(`/api/entities/${encodeURIComponent(player.name)}/actions/camp`,{method:'POST'});
   Object.assign(player,result.updates);
   renderSummary();
   if(result.card)showGenericCard(result.card);
  }catch(err){
   console.error(err);
   setPlay(`<p class="action-error">${esc(err instanceof Error?err.message:String(err))}</p>`);
  }finally{
   busy=false;
   updateActionButtons();
  }
 });
 window.addEventListener('resize',()=>{if(!manualZoom){fitInitialZoom(); draw();}});
 renderSummary();
 updateActionButtons();
 fitInitialZoom();
 draw();
}
