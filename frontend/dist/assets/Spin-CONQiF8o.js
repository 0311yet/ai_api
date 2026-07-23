import{Cr as e,Ei as t,J as n,Jr as r,Kr as i,Kt as a,Or as o,Rr as s,X as c,Y as l,_r as u,hr as d,lt as f,mi as p,q as m,qt as h,vr as g,xr as _}from"./discrete-sHBKW-CW.js";import{f as v}from"./Tag-dUwyirv5.js";function y(e){let{opacityDisabled:t,heightTiny:n,heightSmall:r,heightMedium:i,heightLarge:a,heightHuge:o,primaryColor:s,fontSize:c}=e;return{fontSize:c,textColor:s,sizeTiny:n,sizeSmall:r,sizeMedium:i,sizeLarge:a,sizeHuge:o,color:s,opacitySpinning:t}}var b={name:`Spin`,common:m,self:y},x=u([u(`@keyframes spin-rotate`,`
 from {
 transform: rotate(0);
 }
 to {
 transform: rotate(360deg);
 }
 `),g(`spin-container`,`
 position: relative;
 `,[g(`spin-body`,`
 position: absolute;
 top: 50%;
 left: 50%;
 transform: translateX(-50%) translateY(-50%);
 `,[n()])]),g(`spin-body`,`
 display: inline-flex;
 align-items: center;
 justify-content: center;
 flex-direction: column;
 `),g(`spin`,`
 display: inline-flex;
 height: var(--n-size);
 width: var(--n-size);
 font-size: var(--n-size);
 color: var(--n-color);
 `,[_(`rotate`,`
 animation: spin-rotate 2s linear infinite;
 `)]),g(`spin-description`,`
 display: inline-block;
 font-size: var(--n-font-size);
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 margin-top: 8px;
 `),g(`spin-content`,`
 opacity: 1;
 transition: opacity .3s var(--n-bezier);
 pointer-events: all;
 `,[_(`spinning`,`
 user-select: none;
 -webkit-user-select: none;
 pointer-events: none;
 opacity: var(--n-opacity-spinning);
 `)])]),S={small:20,medium:18,large:16},C=Object.assign(Object.assign(Object.assign({},f.props),{contentClass:String,contentStyle:[Object,String],description:String,size:{type:[String,Number],default:`medium`},show:{type:Boolean,default:!0},rotate:{type:Boolean,default:!0},spinning:{type:Boolean,validator:()=>!0,default:void 0},delay:Number}),c),w=i({name:`Spin`,props:C,slots:Object,setup(n){let{mergedClsPrefixRef:r,inlineThemeDisabled:i}=h(n),o=f(`Spin`,`-spin`,x,b,n,r),c=s(()=>{let{size:t}=n,{common:{cubicBezierEaseInOut:r},self:i}=o.value,{opacitySpinning:a,color:s,textColor:c}=i;return{"--n-bezier":r,"--n-opacity-spinning":a,"--n-size":typeof t==`number`?d(t):i[e(`size`,t)],"--n-color":s,"--n-text-color":c}}),l=i?a(`spin`,s(()=>{let{size:e}=n;return typeof e==`number`?String(e):e[0]}),c,n):void 0,u=v(n,[`spinning`,`show`]),m=t(!1);return p(e=>{let t;if(u.value){let{delay:r}=n;if(r){t=window.setTimeout(()=>{m.value=!0},r),e(()=>{clearTimeout(t)});return}}m.value=u.value}),{mergedClsPrefix:r,active:m,mergedStrokeWidth:s(()=>{let{strokeWidth:e}=n;if(e!==void 0)return e;let{size:t}=n;return S[typeof t==`number`?`medium`:t]}),cssVars:i?void 0:c,themeClass:l?.themeClass,onRender:l?.onRender}},render(){var e;let{$slots:t,mergedClsPrefix:n,description:i}=this,a=t.icon&&this.rotate,s=(i||t.description)&&r(`div`,{class:`${n}-spin-description`},i||t.description?.call(t)),c=t.icon?r(`div`,{class:[`${n}-spin-body`,this.themeClass]},r(`div`,{class:[`${n}-spin`,a&&`${n}-spin--rotate`],style:t.default?``:this.cssVars},t.icon()),s):r(`div`,{class:[`${n}-spin-body`,this.themeClass]},r(l,{clsPrefix:n,style:t.default?``:this.cssVars,stroke:this.stroke,"stroke-width":this.mergedStrokeWidth,radius:this.radius,scale:this.scale,class:`${n}-spin`}),s);return(e=this.onRender)==null||e.call(this),t.default?r(`div`,{class:[`${n}-spin-container`,this.themeClass],style:this.cssVars},r(`div`,{class:[`${n}-spin-content`,this.active&&`${n}-spin-content--spinning`,this.contentClass],style:this.contentStyle},t),r(o,{name:`fade-in-transition`},{default:()=>this.active?c:null})):c}});export{C as n,y as r,w as t};