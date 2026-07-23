import{$ as e,Ai as t,Cr as n,Ei as r,Gt as i,Jr as a,Kn as o,Kr as s,Kt as c,Rr as l,Sr as u,Y as d,Zt as f,_r as p,br as m,en as h,fr as g,hr as _,ln as v,lt as y,ot as b,q as x,qt as S,vr as C,xr as w}from"./discrete-sHBKW-CW.js";import{i as T}from"./Suffix-ClbtaPm4.js";var E={buttonHeightSmall:`14px`,buttonHeightMedium:`18px`,buttonHeightLarge:`22px`,buttonWidthSmall:`14px`,buttonWidthMedium:`18px`,buttonWidthLarge:`22px`,buttonWidthPressedSmall:`20px`,buttonWidthPressedMedium:`24px`,buttonWidthPressedLarge:`28px`,railHeightSmall:`18px`,railHeightMedium:`22px`,railHeightLarge:`26px`,railWidthSmall:`32px`,railWidthMedium:`40px`,railWidthLarge:`48px`};function D(e){let{primaryColor:t,opacityDisabled:n,borderRadius:r,textColor3:i}=e;return Object.assign(Object.assign({},E),{iconColor:i,textColor:`white`,loadingColor:t,opacityDisabled:n,railColor:`rgba(0, 0, 0, .14)`,railColorActive:t,buttonBoxShadow:`0 1px 4px 0 rgba(0, 0, 0, 0.3), inset 0 0 1px 0 rgba(0, 0, 0, 0.05)`,buttonColor:`#FFF`,railBorderRadiusSmall:r,railBorderRadiusMedium:r,railBorderRadiusLarge:r,buttonBorderRadiusSmall:r,buttonBorderRadiusMedium:r,buttonBorderRadiusLarge:r,boxShadowFocus:`0 0 0 2px ${o(t,{alpha:.2})}`})}var O={name:`Switch`,common:x,self:D},k=C(`switch`,`
 height: var(--n-height);
 min-width: var(--n-width);
 vertical-align: middle;
 user-select: none;
 -webkit-user-select: none;
 display: inline-flex;
 outline: none;
 justify-content: center;
 align-items: center;
`,[m(`children-placeholder`,`
 height: var(--n-rail-height);
 display: flex;
 flex-direction: column;
 overflow: hidden;
 pointer-events: none;
 visibility: hidden;
 `),m(`rail-placeholder`,`
 display: flex;
 flex-wrap: none;
 `),m(`button-placeholder`,`
 width: calc(1.75 * var(--n-rail-height));
 height: var(--n-rail-height);
 `),C(`base-loading`,`
 position: absolute;
 top: 50%;
 left: 50%;
 transform: translateX(-50%) translateY(-50%);
 font-size: calc(var(--n-button-width) - 4px);
 color: var(--n-loading-color);
 transition: color .3s var(--n-bezier);
 `,[e({left:`50%`,top:`50%`,originalTransform:`translateX(-50%) translateY(-50%)`})]),m(`checked, unchecked`,`
 transition: color .3s var(--n-bezier);
 color: var(--n-text-color);
 box-sizing: border-box;
 position: absolute;
 white-space: nowrap;
 top: 0;
 bottom: 0;
 display: flex;
 align-items: center;
 line-height: 1;
 `),m(`checked`,`
 right: 0;
 padding-right: calc(1.25 * var(--n-rail-height) - var(--n-offset));
 `),m(`unchecked`,`
 left: 0;
 justify-content: flex-end;
 padding-left: calc(1.25 * var(--n-rail-height) - var(--n-offset));
 `),p(`&:focus`,[m(`rail`,`
 box-shadow: var(--n-box-shadow-focus);
 `)]),w(`round`,[m(`rail`,`border-radius: calc(var(--n-rail-height) / 2);`,[m(`button`,`border-radius: calc(var(--n-button-height) / 2);`)])]),u(`disabled`,[u(`icon`,[w(`rubber-band`,[w(`pressed`,[m(`rail`,[m(`button`,`max-width: var(--n-button-width-pressed);`)])]),m(`rail`,[p(`&:active`,[m(`button`,`max-width: var(--n-button-width-pressed);`)])]),w(`active`,[w(`pressed`,[m(`rail`,[m(`button`,`left: calc(100% - var(--n-offset) - var(--n-button-width-pressed));`)])]),m(`rail`,[p(`&:active`,[m(`button`,`left: calc(100% - var(--n-offset) - var(--n-button-width-pressed));`)])])])])])]),w(`active`,[m(`rail`,[m(`button`,`left: calc(100% - var(--n-button-width) - var(--n-offset))`)])]),m(`rail`,`
 overflow: hidden;
 height: var(--n-rail-height);
 min-width: var(--n-rail-width);
 border-radius: var(--n-rail-border-radius);
 cursor: pointer;
 position: relative;
 transition:
 opacity .3s var(--n-bezier),
 background .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-rail-color);
 `,[m(`button-icon`,`
 color: var(--n-icon-color);
 transition: color .3s var(--n-bezier);
 font-size: calc(var(--n-button-height) - 4px);
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 display: flex;
 justify-content: center;
 align-items: center;
 line-height: 1;
 `,[e()]),m(`button`,`
 align-items: center; 
 top: var(--n-offset);
 left: var(--n-offset);
 height: var(--n-button-height);
 width: var(--n-button-width-pressed);
 max-width: var(--n-button-width);
 border-radius: var(--n-button-border-radius);
 background-color: var(--n-button-color);
 box-shadow: var(--n-button-box-shadow);
 box-sizing: border-box;
 cursor: inherit;
 content: "";
 position: absolute;
 transition:
 background-color .3s var(--n-bezier),
 left .3s var(--n-bezier),
 opacity .3s var(--n-bezier),
 max-width .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 `)]),w(`active`,[m(`rail`,`background-color: var(--n-rail-color-active);`)]),w(`loading`,[m(`rail`,`
 cursor: wait;
 `)]),w(`disabled`,[m(`rail`,`
 cursor: not-allowed;
 opacity: .5;
 `)])]),A=Object.assign(Object.assign({},y.props),{size:String,value:{type:[String,Number,Boolean],default:void 0},loading:Boolean,defaultValue:{type:[String,Number,Boolean],default:!1},disabled:{type:Boolean,default:void 0},round:{type:Boolean,default:!0},"onUpdate:value":[Function,Array],onUpdateValue:[Function,Array],checkedValue:{type:[String,Number,Boolean],default:!0},uncheckedValue:{type:[String,Number,Boolean],default:!1},railStyle:Function,rubberBand:{type:Boolean,default:!0},spinProps:Object,onChange:[Function,Array]}),j,M=s({name:`Switch`,props:A,slots:Object,setup(e){j===void 0&&(j=typeof CSS<`u`?CSS.supports!==void 0&&CSS.supports(`width`,`max(1px)`):!0);let{mergedClsPrefixRef:a,inlineThemeDisabled:o,mergedComponentPropsRef:s}=S(e),u=y(`Switch`,`-switch`,k,O,e,a),d=i(e,{mergedSize(t){return e.size===void 0?t?t.mergedSize.value:s?.value?.Switch?.size||`medium`:e.size}}),{mergedSizeRef:f,mergedDisabledRef:p}=d,m=r(e.defaultValue),h=T(t(e,`value`),m),b=l(()=>h.value===e.checkedValue),x=r(!1),C=r(!1),w=l(()=>{let{railStyle:t}=e;if(t)return t({focused:C.value,checked:b.value})});function E(t){let{"onUpdate:value":n,onChange:r,onUpdateValue:i}=e,{nTriggerFormInput:a,nTriggerFormChange:o}=d;n&&v(n,t),i&&v(i,t),r&&v(r,t),m.value=t,a(),o()}function D(){let{nTriggerFormFocus:e}=d;e()}function A(){let{nTriggerFormBlur:e}=d;e()}function M(){e.loading||p.value||(h.value===e.checkedValue?E(e.uncheckedValue):E(e.checkedValue))}function N(){C.value=!0,D()}function P(){C.value=!1,A(),x.value=!1}function F(t){e.loading||p.value||t.key===` `&&(h.value===e.checkedValue?E(e.uncheckedValue):E(e.checkedValue),x.value=!1)}function I(t){e.loading||p.value||t.key===` `&&(t.preventDefault(),x.value=!0)}let L=l(()=>{let{value:e}=f,{self:{opacityDisabled:t,railColor:r,railColorActive:i,buttonBoxShadow:a,buttonColor:o,boxShadowFocus:s,loadingColor:c,textColor:l,iconColor:d,[n(`buttonHeight`,e)]:p,[n(`buttonWidth`,e)]:m,[n(`buttonWidthPressed`,e)]:h,[n(`railHeight`,e)]:v,[n(`railWidth`,e)]:y,[n(`railBorderRadius`,e)]:b,[n(`buttonBorderRadius`,e)]:x},common:{cubicBezierEaseInOut:S}}=u.value,C,w,T;return j?(C=`calc((${v} - ${p}) / 2)`,w=`max(${v}, ${p})`,T=`max(${y}, calc(${y} + ${p} - ${v}))`):(C=_((g(v)-g(p))/2),w=_(Math.max(g(v),g(p))),T=g(v)>g(p)?y:_(g(y)+g(p)-g(v))),{"--n-bezier":S,"--n-button-border-radius":x,"--n-button-box-shadow":a,"--n-button-color":o,"--n-button-width":m,"--n-button-width-pressed":h,"--n-button-height":p,"--n-height":w,"--n-offset":C,"--n-opacity-disabled":t,"--n-rail-border-radius":b,"--n-rail-color":r,"--n-rail-color-active":i,"--n-rail-height":v,"--n-rail-width":y,"--n-width":T,"--n-box-shadow-focus":s,"--n-loading-color":c,"--n-text-color":l,"--n-icon-color":d}}),R=o?c(`switch`,l(()=>f.value[0]),L,e):void 0;return{handleClick:M,handleBlur:P,handleFocus:N,handleKeyup:F,handleKeydown:I,mergedRailStyle:w,pressed:x,mergedClsPrefix:a,mergedValue:h,checked:b,mergedDisabled:p,cssVars:o?void 0:L,themeClass:R?.themeClass,onRender:R?.onRender}},render(){let{mergedClsPrefix:e,mergedDisabled:t,checked:n,mergedRailStyle:r,onRender:i,$slots:o}=this;i?.();let{checked:s,unchecked:c,icon:l,"checked-icon":u,"unchecked-icon":p}=o,m=!(f(l)&&f(u)&&f(p));return a(`div`,{role:`switch`,"aria-checked":n,class:[`${e}-switch`,this.themeClass,m&&`${e}-switch--icon`,n&&`${e}-switch--active`,t&&`${e}-switch--disabled`,this.round&&`${e}-switch--round`,this.loading&&`${e}-switch--loading`,this.pressed&&`${e}-switch--pressed`,this.rubberBand&&`${e}-switch--rubber-band`],tabindex:this.mergedDisabled?void 0:0,style:this.cssVars,onClick:this.handleClick,onFocus:this.handleFocus,onBlur:this.handleBlur,onKeyup:this.handleKeyup,onKeydown:this.handleKeydown},a(`div`,{class:`${e}-switch__rail`,"aria-hidden":`true`,style:r},h(s,t=>h(c,n=>t||n?a(`div`,{"aria-hidden":!0,class:`${e}-switch__children-placeholder`},a(`div`,{class:`${e}-switch__rail-placeholder`},a(`div`,{class:`${e}-switch__button-placeholder`}),t),a(`div`,{class:`${e}-switch__rail-placeholder`},a(`div`,{class:`${e}-switch__button-placeholder`}),n)):null)),a(`div`,{class:`${e}-switch__button`},h(l,t=>h(u,n=>h(p,r=>a(b,null,{default:()=>this.loading?a(d,Object.assign({key:`loading`,clsPrefix:e,strokeWidth:20},this.spinProps)):this.checked&&(n||t)?a(`div`,{class:`${e}-switch__button-icon`,key:n?`checked-icon`:`icon`},n||t):!this.checked&&(r||t)?a(`div`,{class:`${e}-switch__button-icon`,key:r?`unchecked-icon`:`icon`},r||t):null})))),h(s,t=>t&&a(`div`,{key:`checked`,class:`${e}-switch__checked`},t)),h(c,t=>t&&a(`div`,{key:`unchecked`,class:`${e}-switch__unchecked`},t)))))}});export{A as n,E as r,M as t};