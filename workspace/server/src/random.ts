import crypto from 'node:crypto';

export class RNG {
 private state:number;
 constructor(seed:string){this.state=this.hashSeed(seed)||0x1a2b3c4d;}
 next(){
  let t=this.state+=0x6D2B79F5;
  t=Math.imul(t^(t>>>15),t|1);
  t^=t+Math.imul(t^(t>>>7),t|61);
  return ((t^(t>>>14))>>>0)/4294967296;
 }
 int(max:number){return Math.floor(this.next()*max);}
 range(min:number,max:number){return min+this.int(max-min+1);}
 pick<T>(items:T[]){return items[this.int(items.length)];}
 shuffle<T>(items:T[]){
  const copy=[...items];
  for(let i=copy.length-1;i>0;i--){
   const j=this.int(i+1);
   [copy[i],copy[j]]=[copy[j],copy[i]];
  }
  return copy;
 }
 d6(){return this.range(1,6);}
 hashSeed(seed:string):number{
 let h=2166136261;
 for(let i=0;i<seed.length;i++){
  h^=seed.charCodeAt(i);
  h=Math.imul(h,16777619);
 }
 return h>>>0;
}
}
