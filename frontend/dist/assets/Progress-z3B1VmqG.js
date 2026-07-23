import{Cr as e,Dr as t,Jr as n,Kr as r,Kt as i,Rr as a,_r as o,et as s,lt as c,nt as l,q as u,qt as d,rt as f,st as p,tt as m,vr as h,xr as g}from"./discrete-sHBKW-CW.js";import{d as _}from"./Tag-dUwyirv5.js";function v(e){let{infoColor:t,successColor:n,warningColor:r,errorColor:i,textColor2:a,progressRailColor:o,fontSize:s,fontWeight:c}=e;return{fontSize:s,fontSizeCircle:`28px`,fontWeightCircle:c,railColor:o,railHeight:`8px`,iconSizeCircle:`36px`,iconSizeLine:`18px`,iconColor:t,iconColorInfo:t,iconColorSuccess:n,iconColorWarning:r,iconColorError:i,textColorCircle:a,textColorLineInner:`rgb(255, 255, 255)`,textColorLineOuter:a,fillColor:t,fillColorInfo:t,fillColorSuccess:n,fillColorWarning:r,fillColorError:i,lineBgProcessing:`linear-gradient(90deg, rgba(255, 255, 255, .3) 0%, rgba(255, 255, 255, .5) 100%)`}}var y={name:`Progress`,common:u,self:v},b={success:n(m,null),error:n(f,null),warning:n(s,null),info:n(l,null)},x=r({name:`ProgressCircle`,props:{clsPrefix:{type:String,required:!0},status:{type:String,required:!0},strokeWidth:{type:Number,required:!0},fillColor:[String,Object],railColor:String,railStyle:[String,Object],percentage:{type:Number,default:0},offsetDegree:{type:Number,default:0},showIndicator:{type:Boolean,required:!0},indicatorTextColor:String,unit:String,viewBoxWidth:{type:Number,required:!0},gapDegree:{type:Number,required:!0},gapOffsetDegree:{type:Number,default:0}},setup(e,{slots:r}){let i=a(()=>{let n=`gradient`,{fillColor:r}=e;return typeof r==`object`?`${n}-${t(JSON.stringify(r))}`:n});function o(t,n,r,a){let{gapDegree:o,viewBoxWidth:s,strokeWidth:c}=e,l=50+c/2,u=`M ${l},${l} m 0,50
      a 50,50 0 1 1 0,-100
      a 50,50 0 1 1 0,100`,d=Math.PI*2*50;return{pathString:u,pathStyle:{stroke:a===`rail`?r:typeof e.fillColor==`object`?`url(#${i.value})`:r,strokeDasharray:`${Math.min(t,100)/100*(d-o)}px ${s*8}px`,strokeDashoffset:`-${o/2}px`,transformOrigin:n?`center`:void 0,transform:n?`rotate(${n}deg)`:void 0}}}let s=()=>{let t=typeof e.fillColor==`object`,r=t?e.fillColor.stops[0]:``,a=t?e.fillColor.stops[1]:``;return t&&n(`defs`,null,n(`linearGradient`,{id:i.value,x1:`0%`,y1:`100%`,x2:`100%`,y2:`0%`},n(`stop`,{offset:`0%`,"stop-color":r}),n(`stop`,{offset:`100%`,"stop-color":a})))};return()=>{let{fillColor:t,railColor:i,strokeWidth:a,offsetDegree:c,status:l,percentage:u,showIndicator:d,indicatorTextColor:f,unit:m,gapOffsetDegree:h,clsPrefix:g}=e,{pathString:_,pathStyle:v}=o(100,0,i,`rail`),{pathString:y,pathStyle:x}=o(u,c,t,`fill`),S=100+a;return n(`div`,{class:`${g}-progress-content`,role:`none`},n(`div`,{class:`${g}-progress-graph`,"aria-hidden":!0},n(`div`,{class:`${g}-progress-graph-circle`,style:{transform:h?`rotate(${h}deg)`:void 0}},n(`svg`,{viewBox:`0 0 ${S} ${S}`},s(),n(`g`,null,n(`path`,{class:`${g}-progress-graph-circle-rail`,d:_,"stroke-width":a,"stroke-linecap":`round`,fill:`none`,style:v})),n(`g`,null,n(`path`,{class:[`${g}-progress-graph-circle-fill`,u===0&&`${g}-progress-graph-circle-fill--empty`],d:y,"stroke-width":a,"stroke-linecap":`round`,fill:`none`,style:x}))))),d?n(`div`,null,r.default?n(`div`,{class:`${g}-progress-custom-content`,role:`none`},r.default()):l==="default"?n(`div`,{class:`${g}-progress-text`,style:{color:f},role:`none`},n(`span`,{class:`${g}-progress-text__percentage`},u),n(`span`,{class:`${g}-progress-text__unit`},m)):n(`div`,{class:`${g}-progress-icon`,"aria-hidden":!0},n(p,{clsPrefix:g},{default:()=>b[l]}))):null)}}}),S={success:n(m,null),error:n(f,null),warning:n(s,null),info:n(l,null)},C=r({name:`ProgressLine`,props:{clsPrefix:{type:String,required:!0},percentage:{type:Number,default:0},railColor:String,railStyle:[String,Object],fillColor:[String,Object],status:{type:String,required:!0},indicatorPlacement:{type:String,required:!0},indicatorTextColor:String,unit:{type:String,default:`%`},processing:{type:Boolean,required:!0},showIndicator:{type:Boolean,required:!0},height:[String,Number],railBorderRadius:[String,Number],fillBorderRadius:[String,Number]},setup(e,{slots:t}){let r=a(()=>_(e.height)),i=a(()=>typeof e.fillColor==`object`?`linear-gradient(to right, ${e.fillColor?.stops[0]} , ${e.fillColor?.stops[1]})`:e.fillColor),o=a(()=>e.railBorderRadius===void 0?e.height===void 0?``:_(e.height,{c:.5}):_(e.railBorderRadius)),s=a(()=>e.fillBorderRadius===void 0?e.railBorderRadius===void 0?e.height===void 0?``:_(e.height,{c:.5}):_(e.railBorderRadius):_(e.fillBorderRadius));return()=>{let{indicatorPlacement:a,railColor:c,railStyle:l,percentage:u,unit:d,indicatorTextColor:f,status:m,showIndicator:h,processing:g,clsPrefix:_}=e;return n(`div`,{class:`${_}-progress-content`,role:`none`},n(`div`,{class:`${_}-progress-graph`,"aria-hidden":!0},n(`div`,{class:[`${_}-progress-graph-line`,{[`${_}-progress-graph-line--indicator-${a}`]:!0}]},n(`div`,{class:`${_}-progress-graph-line-rail`,style:[{backgroundColor:c,height:r.value,borderRadius:o.value},l]},n(`div`,{class:[`${_}-progress-graph-line-fill`,g&&`${_}-progress-graph-line-fill--processing`],style:{maxWidth:`${e.percentage}%`,background:i.value,height:r.value,lineHeight:r.value,borderRadius:s.value}},a===`inside`?n(`div`,{class:`${_}-progress-graph-line-indicator`,style:{color:f}},t.default?t.default():`${u}${d}`):null)))),h&&a===`outside`?n(`div`,null,t.default?n(`div`,{class:`${_}-progress-custom-content`,style:{color:f},role:`none`},t.default()):m==="default"?n(`div`,{role:`none`,class:`${_}-progress-icon ${_}-progress-icon--as-text`,style:{color:f}},u,d):n(`div`,{class:`${_}-progress-icon`,"aria-hidden":!0},n(p,{clsPrefix:_},{default:()=>S[m]}))):null)}}});function w(e,t,n=100){return`m ${n/2} ${n/2-e} a ${e} ${e} 0 1 1 0 ${2*e} a ${e} ${e} 0 1 1 0 -${2*e}`}var T=r({name:`ProgressMultipleCircle`,props:{clsPrefix:{type:String,required:!0},viewBoxWidth:{type:Number,required:!0},percentage:{type:Array,default:[0]},strokeWidth:{type:Number,required:!0},circleGap:{type:Number,required:!0},showIndicator:{type:Boolean,required:!0},fillColor:{type:Array,default:()=>[]},railColor:{type:Array,default:()=>[]},railStyle:{type:Array,default:()=>[]}},setup(e,{slots:t}){let r=a(()=>e.percentage.map((t,n)=>`${Math.PI*t/100*(e.viewBoxWidth/2-e.strokeWidth/2*(1+2*n)-e.circleGap*n)*2}, ${e.viewBoxWidth*8}`)),i=(t,r)=>{let i=e.fillColor[r],a=typeof i==`object`?i.stops[0]:``,o=typeof i==`object`?i.stops[1]:``;return typeof e.fillColor[r]==`object`&&n(`linearGradient`,{id:`gradient-${r}`,x1:`100%`,y1:`0%`,x2:`0%`,y2:`100%`},n(`stop`,{offset:`0%`,"stop-color":a}),n(`stop`,{offset:`100%`,"stop-color":o}))};return()=>{let{viewBoxWidth:a,strokeWidth:o,circleGap:s,showIndicator:c,fillColor:l,railColor:u,railStyle:d,percentage:f,clsPrefix:p}=e;return n(`div`,{class:`${p}-progress-content`,role:`none`},n(`div`,{class:`${p}-progress-graph`,"aria-hidden":!0},n(`div`,{class:`${p}-progress-graph-circle`},n(`svg`,{viewBox:`0 0 ${a} ${a}`},n(`defs`,null,f.map((e,t)=>i(e,t))),f.map((e,t)=>n(`g`,{key:t},n(`path`,{class:`${p}-progress-graph-circle-rail`,d:w(a/2-o/2*(1+2*t)-s*t,o,a),"stroke-width":o,"stroke-linecap":`round`,fill:`none`,style:[{strokeDashoffset:0,stroke:u[t]},d[t]]}),n(`path`,{class:[`${p}-progress-graph-circle-fill`,e===0&&`${p}-progress-graph-circle-fill--empty`],d:w(a/2-o/2*(1+2*t)-s*t,o,a),"stroke-width":o,"stroke-linecap":`round`,fill:`none`,style:{strokeDasharray:r.value[t],strokeDashoffset:0,stroke:typeof l[t]==`object`?`url(#gradient-${t})`:l[t]}})))))),c&&t.default?n(`div`,null,n(`div`,{class:`${p}-progress-text`},t.default())):null)}}}),E=o([h(`progress`,{display:`inline-block`},[h(`progress-icon`,`
 color: var(--n-icon-color);
 transition: color .3s var(--n-bezier);
 `),g(`line`,`
 width: 100%;
 display: block;
 `,[h(`progress-content`,`
 display: flex;
 align-items: center;
 `,[h(`progress-graph`,{flex:1})]),h(`progress-custom-content`,{marginLeft:`14px`}),h(`progress-icon`,`
 width: 30px;
 padding-left: 14px;
 height: var(--n-icon-size-line);
 line-height: var(--n-icon-size-line);
 font-size: var(--n-icon-size-line);
 `,[g(`as-text`,`
 color: var(--n-text-color-line-outer);
 text-align: center;
 width: 40px;
 font-size: var(--n-font-size);
 padding-left: 4px;
 transition: color .3s var(--n-bezier);
 `)])]),g(`circle, dashboard`,{width:`120px`},[h(`progress-custom-content`,`
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 justify-content: center;
 `),h(`progress-text`,`
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 color: inherit;
 font-size: var(--n-font-size-circle);
 color: var(--n-text-color-circle);
 font-weight: var(--n-font-weight-circle);
 transition: color .3s var(--n-bezier);
 white-space: nowrap;
 `),h(`progress-icon`,`
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 color: var(--n-icon-color);
 font-size: var(--n-icon-size-circle);
 `)]),g(`multiple-circle`,`
 width: 200px;
 color: inherit;
 `,[h(`progress-text`,`
 font-weight: var(--n-font-weight-circle);
 color: var(--n-text-color-circle);
 position: absolute;
 left: 50%;
 top: 50%;
 transform: translateX(-50%) translateY(-50%);
 display: flex;
 align-items: center;
 justify-content: center;
 transition: color .3s var(--n-bezier);
 `)]),h(`progress-content`,{position:`relative`}),h(`progress-graph`,{position:`relative`},[h(`progress-graph-circle`,[o(`svg`,{verticalAlign:`bottom`}),h(`progress-graph-circle-fill`,`
 stroke: var(--n-fill-color);
 transition:
 opacity .3s var(--n-bezier),
 stroke .3s var(--n-bezier),
 stroke-dasharray .3s var(--n-bezier);
 `,[g(`empty`,{opacity:0})]),h(`progress-graph-circle-rail`,`
 transition: stroke .3s var(--n-bezier);
 overflow: hidden;
 stroke: var(--n-rail-color);
 `)]),h(`progress-graph-line`,[g(`indicator-inside`,[h(`progress-graph-line-rail`,`
 height: 16px;
 line-height: 16px;
 border-radius: 10px;
 `,[h(`progress-graph-line-fill`,`
 height: inherit;
 border-radius: 10px;
 `),h(`progress-graph-line-indicator`,`
 background: #0000;
 white-space: nowrap;
 text-align: right;
 margin-left: 14px;
 margin-right: 14px;
 height: inherit;
 font-size: 12px;
 color: var(--n-text-color-line-inner);
 transition: color .3s var(--n-bezier);
 `)])]),g(`indicator-inside-label`,`
 height: 16px;
 display: flex;
 align-items: center;
 `,[h(`progress-graph-line-rail`,`
 flex: 1;
 transition: background-color .3s var(--n-bezier);
 `),h(`progress-graph-line-indicator`,`
 background: var(--n-fill-color);
 font-size: 12px;
 transform: translateZ(0);
 display: flex;
 vertical-align: middle;
 height: 16px;
 line-height: 16px;
 padding: 0 10px;
 border-radius: 10px;
 position: absolute;
 white-space: nowrap;
 color: var(--n-text-color-line-inner);
 transition:
 right .2s var(--n-bezier),
 color .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `)]),h(`progress-graph-line-rail`,`
 position: relative;
 overflow: hidden;
 height: var(--n-rail-height);
 border-radius: 5px;
 background-color: var(--n-rail-color);
 transition: background-color .3s var(--n-bezier);
 `,[h(`progress-graph-line-fill`,`
 background: var(--n-fill-color);
 position: relative;
 border-radius: 5px;
 height: inherit;
 width: 100%;
 max-width: 0%;
 transition:
 background-color .3s var(--n-bezier),
 max-width .2s var(--n-bezier);
 `,[g(`processing`,[o(`&::after`,`
 content: "";
 background-image: var(--n-line-bg-processing);
 animation: progress-processing-animation 2s var(--n-bezier) infinite;
 `)])])])])])]),o(`@keyframes progress-processing-animation`,`
 0% {
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 100%;
 opacity: 1;
 }
 66% {
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 0;
 opacity: 0;
 }
 100% {
 position: absolute;
 left: 0;
 top: 0;
 bottom: 0;
 right: 0;
 opacity: 0;
 }
 `)]),D=Object.assign(Object.assign({},c.props),{processing:Boolean,type:{type:String,default:`line`},gapDegree:Number,gapOffsetDegree:Number,status:{type:String,default:`default`},railColor:[String,Array],railStyle:[String,Array],color:[String,Array,Object],viewBoxWidth:{type:Number,default:100},strokeWidth:{type:Number,default:7},percentage:[Number,Array],unit:{type:String,default:`%`},showIndicator:{type:Boolean,default:!0},indicatorPosition:{type:String,default:`outside`},indicatorPlacement:{type:String,default:`outside`},indicatorTextColor:String,circleGap:{type:Number,default:1},height:Number,borderRadius:[String,Number],fillBorderRadius:[String,Number],offsetDegree:Number}),O=r({name:`Progress`,props:D,setup(t){let n=a(()=>t.indicatorPlacement||t.indicatorPosition),r=a(()=>{if(t.gapDegree||t.gapDegree===0)return t.gapDegree;if(t.type===`dashboard`)return 75}),{mergedClsPrefixRef:o,inlineThemeDisabled:s}=d(t),l=c(`Progress`,`-progress`,E,y,t,o),u=a(()=>{let{status:n}=t,{common:{cubicBezierEaseInOut:r},self:{fontSize:i,fontSizeCircle:a,railColor:o,railHeight:s,iconSizeCircle:c,iconSizeLine:u,textColorCircle:d,textColorLineInner:f,textColorLineOuter:p,lineBgProcessing:m,fontWeightCircle:h,[e(`iconColor`,n)]:g,[e(`fillColor`,n)]:_}}=l.value;return{"--n-bezier":r,"--n-fill-color":_,"--n-font-size":i,"--n-font-size-circle":a,"--n-font-weight-circle":h,"--n-icon-color":g,"--n-icon-size-circle":c,"--n-icon-size-line":u,"--n-line-bg-processing":m,"--n-rail-color":o,"--n-rail-height":s,"--n-text-color-circle":d,"--n-text-color-line-inner":f,"--n-text-color-line-outer":p}}),f=s?i(`progress`,a(()=>t.status[0]),u,t):void 0;return{mergedClsPrefix:o,mergedIndicatorPlacement:n,gapDeg:r,cssVars:s?void 0:u,themeClass:f?.themeClass,onRender:f?.onRender}},render(){let{type:e,cssVars:t,indicatorTextColor:r,showIndicator:i,status:a,railColor:o,railStyle:s,color:c,percentage:l,viewBoxWidth:u,strokeWidth:d,mergedIndicatorPlacement:f,unit:p,borderRadius:m,fillBorderRadius:h,height:g,processing:_,circleGap:v,mergedClsPrefix:y,gapDeg:b,gapOffsetDegree:S,themeClass:w,$slots:E,onRender:D}=this;return D?.(),n(`div`,{class:[w,`${y}-progress`,`${y}-progress--${e}`,`${y}-progress--${a}`],style:t,"aria-valuemax":100,"aria-valuemin":0,"aria-valuenow":l,role:e===`circle`||e===`line`||e===`dashboard`?`progressbar`:`none`},e===`circle`||e===`dashboard`?n(x,{clsPrefix:y,status:a,showIndicator:i,indicatorTextColor:r,railColor:o,fillColor:c,railStyle:s,offsetDegree:this.offsetDegree,percentage:l,viewBoxWidth:u,strokeWidth:d,gapDegree:b===void 0?e===`dashboard`?75:0:b,gapOffsetDegree:S,unit:p},E):e===`line`?n(C,{clsPrefix:y,status:a,showIndicator:i,indicatorTextColor:r,railColor:o,fillColor:c,railStyle:s,percentage:l,processing:_,indicatorPlacement:f,unit:p,fillBorderRadius:h,railBorderRadius:m,height:g},E):e===`multiple-circle`?n(T,{clsPrefix:y,strokeWidth:d,railColor:o,fillColor:c,railStyle:s,viewBoxWidth:u,percentage:l,showIndicator:i,circleGap:v},E):null)}});export{v as i,D as n,y as r,O as t};