/* esm.sh - @pixiv/three-vrm@2.1.3 */
import*as o from"/vendor/esm/three@0.164.1__target-es2022.js";import{BufferAttribute as vt}from"/vendor/esm/three@0.164.1__target-es2022.js";var me=class extends o.Object3D{get overrideBlinkAmount(){return this.overrideBlink==="block"?0<this.weight?1:0:this.overrideBlink==="blend"?this.weight:0}get overrideLookAtAmount(){return this.overrideLookAt==="block"?0<this.weight?1:0:this.overrideLookAt==="blend"?this.weight:0}get overrideMouthAmount(){return this.overrideMouth==="block"?0<this.weight?1:0:this.overrideMouth==="blend"?this.weight:0}constructor(e){super(),this.weight=0,this.isBinary=!1,this.overrideBlink="none",this.overrideLookAt="none",this.overrideMouth="none",this._binds=[],this.name=`VRMExpression_${e}`,this.expressionName=e,this.type="VRMExpression",this.visible=!1}addBind(e){this._binds.push(e)}applyWeight(e){var t;let n=this.isBinary?this.weight<=.5?0:1:this.weight;n*=(t=e?.multiplier)!==null&&t!==void 0?t:1,this._binds.forEach(i=>i.applyWeight(n))}clearAppliedWeight(){this._binds.forEach(e=>e.clearAppliedWeight())}};function w(l,e,t,n){function i(r){return r instanceof t?r:new t(function(s){s(r)})}return new(t||(t=Promise))(function(r,s){function a(c){try{d(n.next(c))}catch(h){s(h)}}function u(c){try{d(n.throw(c))}catch(h){s(h)}}function d(c){c.done?r(c.value):i(c.value).then(a,u)}d((n=n.apply(l,e||[])).next())})}function En(l,e,t){var n,i;let r=l.parser.json,s=(n=r.nodes)===null||n===void 0?void 0:n[e];if(s==null)return console.warn(`extractPrimitivesInternal: Attempt to use nodes[${e}] of glTF but the node doesn't exist`),null;let a=s.mesh;if(a==null)return null;let u=(i=r.meshes)===null||i===void 0?void 0:i[a];if(u==null)return console.warn(`extractPrimitivesInternal: Attempt to use meshes[${a}] of glTF but the mesh doesn't exist`),null;let d=u.primitives.length,c=[];return t.traverse(h=>{c.length<d&&h.isMesh&&c.push(h)}),c}function Jt(l,e){return w(this,void 0,void 0,function*(){let t=yield l.parser.getDependency("node",e);return En(l,e,t)})}function Kt(l){return w(this,void 0,void 0,function*(){let e=yield l.parser.getDependencies("node"),t=new Map;return e.forEach((n,i)=>{let r=En(l,i,n);r!=null&&t.set(i,r)}),t})}function en(l,e){var t,n;let i=parseInt(o.REVISION,10),r=null;if(i>=133)r=(n=(t=l.associations.get(e))===null||t===void 0?void 0:t.materials)!==null&&n!==void 0?n:null;else{let a=l.associations.get(e);a?.type==="materials"&&(r=a.index)}return r}var yt={Aa:"aa",Ih:"ih",Ou:"ou",Ee:"ee",Oh:"oh",Blink:"blink",Happy:"happy",Angry:"angry",Sad:"sad",Relaxed:"relaxed",LookUp:"lookUp",Surprised:"surprised",LookDown:"lookDown",LookLeft:"lookLeft",LookRight:"lookRight",BlinkLeft:"blinkLeft",BlinkRight:"blinkRight",Neutral:"neutral"};function Tn(l){return Math.max(Math.min(l,1),0)}var ve=class l{get expressions(){return this._expressions.concat()}get expressionMap(){return Object.assign({},this._expressionMap)}get presetExpressionMap(){let e={},t=new Set(Object.values(yt));return Object.entries(this._expressionMap).forEach(([n,i])=>{t.has(n)&&(e[n]=i)}),e}get customExpressionMap(){let e={},t=new Set(Object.values(yt));return Object.entries(this._expressionMap).forEach(([n,i])=>{t.has(n)||(e[n]=i)}),e}constructor(){this.blinkExpressionNames=["blink","blinkLeft","blinkRight"],this.lookAtExpressionNames=["lookLeft","lookRight","lookUp","lookDown"],this.mouthExpressionNames=["aa","ee","ih","oh","ou"],this._expressions=[],this._expressionMap={}}copy(e){return this._expressions.concat().forEach(n=>{this.unregisterExpression(n)}),e._expressions.forEach(n=>{this.registerExpression(n)}),this.blinkExpressionNames=e.blinkExpressionNames.concat(),this.lookAtExpressionNames=e.lookAtExpressionNames.concat(),this.mouthExpressionNames=e.mouthExpressionNames.concat(),this}clone(){return new l().copy(this)}getExpression(e){var t;return(t=this._expressionMap[e])!==null&&t!==void 0?t:null}registerExpression(e){this._expressions.push(e),this._expressionMap[e.expressionName]=e}unregisterExpression(e){let t=this._expressions.indexOf(e);t===-1&&console.warn("VRMExpressionManager: The specified expressions is not registered"),this._expressions.splice(t,1),delete this._expressionMap[e.expressionName]}getValue(e){var t;let n=this.getExpression(e);return(t=n?.weight)!==null&&t!==void 0?t:null}setValue(e,t){let n=this.getExpression(e);n&&(n.weight=Tn(t))}getExpressionTrackName(e){let t=this.getExpression(e);return t?`${t.name}.weight`:null}update(){let e=this._calculateWeightMultipliers();this._expressions.forEach(t=>{t.clearAppliedWeight()}),this._expressions.forEach(t=>{let n=1,i=t.expressionName;this.blinkExpressionNames.indexOf(i)!==-1&&(n*=e.blink),this.lookAtExpressionNames.indexOf(i)!==-1&&(n*=e.lookAt),this.mouthExpressionNames.indexOf(i)!==-1&&(n*=e.mouth),t.applyWeight({multiplier:n})})}_calculateWeightMultipliers(){let e=1,t=1,n=1;return this._expressions.forEach(i=>{e-=i.overrideBlinkAmount,t-=i.overrideLookAtAmount,n-=i.overrideMouthAmount}),e=Math.max(0,e),t=Math.max(0,t),n=Math.max(0,n),{blink:e,lookAt:t,mouth:n}}},G={Color:"color",EmissionColor:"emissionColor",ShadeColor:"shadeColor",MatcapColor:"matcapColor",RimColor:"rimColor",OutlineColor:"outlineColor"},ei={_Color:G.Color,_EmissionColor:G.EmissionColor,_ShadeColor:G.ShadeColor,_RimColor:G.RimColor,_OutlineColor:G.OutlineColor},ti=new o.Color,te=class l{constructor({material:e,type:t,targetValue:n,targetAlpha:i}){this.material=e,this.type=t,this.targetValue=n,this.targetAlpha=i??1;let r=this._initColorBindState(),s=this._initAlphaBindState();this._state={color:r,alpha:s}}applyWeight(e){let{color:t,alpha:n}=this._state;if(t!=null){let{propertyName:i,deltaValue:r}=t,s=this.material[i];s?.add(ti.copy(r).multiplyScalar(e))}if(n!=null){let{propertyName:i,deltaValue:r}=n;this.material[i]!=null&&(this.material[i]+=r*e)}}clearAppliedWeight(){let{color:e,alpha:t}=this._state;if(e!=null){let{propertyName:n,initialValue:i}=e,r=this.material[n];r?.copy(i)}if(t!=null){let{propertyName:n,initialValue:i}=t;this.material[n]!=null&&(this.material[n]=i)}}_initColorBindState(){var e,t,n;let{material:i,type:r,targetValue:s}=this,a=this._getPropertyNameMap(),u=(t=(e=a?.[r])===null||e===void 0?void 0:e[0])!==null&&t!==void 0?t:null;if(u==null)return console.warn(`Tried to add a material color bind to the material ${(n=i.name)!==null&&n!==void 0?n:"(no name)"}, the type ${r} but the material or the type is not supported.`),null;let c=i[u].clone(),h=new o.Color(s.r-c.r,s.g-c.g,s.b-c.b);return{propertyName:u,initialValue:c,deltaValue:h}}_initAlphaBindState(){var e,t,n;let{material:i,type:r,targetAlpha:s}=this,a=this._getPropertyNameMap(),u=(t=(e=a?.[r])===null||e===void 0?void 0:e[1])!==null&&t!==void 0?t:null;if(u==null&&s!==1)return console.warn(`Tried to add a material alpha bind to the material ${(n=i.name)!==null&&n!==void 0?n:"(no name)"}, the type ${r} but the material or the type does not support alpha.`),null;if(u==null)return null;let d=i[u],c=s-d;return{propertyName:u,initialValue:d,deltaValue:c}}_getPropertyNameMap(){var e,t;return(t=(e=Object.entries(l._propertyNameMapMap).find(([n])=>this.material[n]===!0))===null||e===void 0?void 0:e[1])!==null&&t!==void 0?t:null}};te._propertyNameMapMap={isMeshStandardMaterial:{color:["color","opacity"],emissionColor:["emissive",null]},isMeshBasicMaterial:{color:["color","opacity"]},isMToonMaterial:{color:["color","opacity"],emissionColor:["emissive",null],outlineColor:["outlineColorFactor",null],matcapColor:["matcapFactor",null],rimColor:["parametricRimColorFactor",null],shadeColor:["shadeColorFactor",null]}};var _e=class{constructor({primitives:e,index:t,weight:n}){this.primitives=e,this.index=t,this.weight=n}applyWeight(e){this.primitives.forEach(t=>{var n;((n=t.morphTargetInfluences)===null||n===void 0?void 0:n[this.index])!=null&&(t.morphTargetInfluences[this.index]+=this.weight*e)})}clearAppliedWeight(){this.primitives.forEach(e=>{var t;((t=e.morphTargetInfluences)===null||t===void 0?void 0:t[this.index])!=null&&(e.morphTargetInfluences[this.index]=0)})}},tn=new o.Vector2,ne=class l{constructor({material:e,scale:t,offset:n}){var i,r;this.material=e,this.scale=t,this.offset=n;let s=(i=Object.entries(l._propertyNamesMap).find(([a])=>e[a]===!0))===null||i===void 0?void 0:i[1];s==null?(console.warn(`Tried to add a texture transform bind to the material ${(r=e.name)!==null&&r!==void 0?r:"(no name)"} but the material is not supported.`),this._properties=[]):(this._properties=[],s.forEach(a=>{var u;let d=(u=e[a])===null||u===void 0?void 0:u.clone();if(!d)return null;e[a]=d;let c=d.offset.clone(),h=d.repeat.clone(),p=n.clone().sub(c),f=t.clone().sub(h);this._properties.push({name:a,initialOffset:c,deltaOffset:p,initialScale:h,deltaScale:f})}))}applyWeight(e){this._properties.forEach(t=>{let n=this.material[t.name];n!==void 0&&(n.offset.add(tn.copy(t.deltaOffset).multiplyScalar(e)),n.repeat.add(tn.copy(t.deltaScale).multiplyScalar(e)))})}clearAppliedWeight(){this._properties.forEach(e=>{let t=this.material[e.name];t!==void 0&&(t.offset.copy(e.initialOffset),t.repeat.copy(e.initialScale))})}};ne._propertyNamesMap={isMeshStandardMaterial:["map","emissiveMap","bumpMap","normalMap","displacementMap","roughnessMap","metalnessMap","alphaMap"],isMeshBasicMaterial:["map","specularMap","alphaMap"],isMToonMaterial:["map","normalMap","emissiveMap","shadeMultiplyTexture","rimMultiplyTexture","outlineWidthMultiplyTexture","uvAnimationMaskTexture"]};var ni=new Set(["1.0","1.0-beta"]),ie=class l{get name(){return"VRMExpressionLoaderPlugin"}constructor(e){this.parser=e}afterRoot(e){return w(this,void 0,void 0,function*(){e.userData.vrmExpressionManager=yield this._import(e)})}_import(e){return w(this,void 0,void 0,function*(){let t=yield this._v1Import(e);if(t)return t;let n=yield this._v0Import(e);return n||null})}_v1Import(e){var t,n;return w(this,void 0,void 0,function*(){let i=this.parser.json;if(!(((t=i.extensionsUsed)===null||t===void 0?void 0:t.indexOf("VRMC_vrm"))!==-1))return null;let s=(n=i.extensions)===null||n===void 0?void 0:n.VRMC_vrm;if(!s)return null;let a=s.specVersion;if(!ni.has(a))return console.warn(`VRMExpressionLoaderPlugin: Unknown VRMC_vrm specVersion "${a}"`),null;let u=s.expressions;if(!u)return null;let d=new Set(Object.values(yt)),c=new Map;u.preset!=null&&Object.entries(u.preset).forEach(([p,f])=>{if(f!=null){if(!d.has(p)){console.warn(`VRMExpressionLoaderPlugin: Unknown preset name "${p}" detected. Ignoring the expression`);return}c.set(p,f)}}),u.custom!=null&&Object.entries(u.custom).forEach(([p,f])=>{if(d.has(p)){console.warn(`VRMExpressionLoaderPlugin: Custom expression cannot have preset name "${p}". Ignoring the expression`);return}c.set(p,f)});let h=new ve;return yield Promise.all(Array.from(c.entries()).map(([p,f])=>w(this,void 0,void 0,function*(){var g,m,_,v,M,x,E;let T=new me(p);if(e.scene.add(T),T.isBinary=(g=f.isBinary)!==null&&g!==void 0?g:!1,T.overrideBlink=(m=f.overrideBlink)!==null&&m!==void 0?m:"none",T.overrideLookAt=(_=f.overrideLookAt)!==null&&_!==void 0?_:"none",T.overrideMouth=(v=f.overrideMouth)!==null&&v!==void 0?v:"none",(M=f.morphTargetBinds)===null||M===void 0||M.forEach(y=>w(this,void 0,void 0,function*(){var R;if(y.node===void 0||y.index===void 0)return;let P=yield Jt(e,y.node),S=y.index;if(!P.every(A=>Array.isArray(A.morphTargetInfluences)&&S<A.morphTargetInfluences.length)){console.warn(`VRMExpressionLoaderPlugin: ${f.name} attempts to index morph #${S} but not found.`);return}T.addBind(new _e({primitives:P,index:S,weight:(R=y.weight)!==null&&R!==void 0?R:1}))})),f.materialColorBinds||f.textureTransformBinds){let y=[];e.scene.traverse(R=>{let P=R.material;P&&y.push(P)}),(x=f.materialColorBinds)===null||x===void 0||x.forEach(R=>w(this,void 0,void 0,function*(){y.filter(S=>{let A=en(this.parser,S);return R.material===A}).forEach(S=>{T.addBind(new te({material:S,type:R.type,targetValue:new o.Color().fromArray(R.targetValue),targetAlpha:R.targetValue[3]}))})})),(E=f.textureTransformBinds)===null||E===void 0||E.forEach(R=>w(this,void 0,void 0,function*(){y.filter(S=>{let A=en(this.parser,S);return R.material===A}).forEach(S=>{var A,L;T.addBind(new ne({material:S,offset:new o.Vector2().fromArray((A=R.offset)!==null&&A!==void 0?A:[0,0]),scale:new o.Vector2().fromArray((L=R.scale)!==null&&L!==void 0?L:[1,1])}))})}))}h.registerExpression(T)}))),h})}_v0Import(e){var t;return w(this,void 0,void 0,function*(){let n=this.parser.json,i=(t=n.extensions)===null||t===void 0?void 0:t.VRM;if(!i)return null;let r=i.blendShapeMaster;if(!r)return null;let s=new ve,a=r.blendShapeGroups;if(!a)return s;let u=new Set;return yield Promise.all(a.map(d=>w(this,void 0,void 0,function*(){var c;let h=d.presetName,p=h!=null&&l.v0v1PresetNameMap[h]||null,f=p??d.name;if(f==null){console.warn("VRMExpressionLoaderPlugin: One of custom expressions has no name. Ignoring the expression");return}if(u.has(f)){console.warn(`VRMExpressionLoaderPlugin: An expression preset ${h} has duplicated entries. Ignoring the expression`);return}u.add(f);let g=new me(f);e.scene.add(g),g.isBinary=(c=d.isBinary)!==null&&c!==void 0?c:!1,d.binds&&d.binds.forEach(_=>w(this,void 0,void 0,function*(){var v;if(_.mesh===void 0||_.index===void 0)return;let M=[];(v=n.nodes)===null||v===void 0||v.forEach((E,T)=>{E.mesh===_.mesh&&M.push(T)});let x=_.index;yield Promise.all(M.map(E=>w(this,void 0,void 0,function*(){var T;let y=yield Jt(e,E);if(!y.every(R=>Array.isArray(R.morphTargetInfluences)&&x<R.morphTargetInfluences.length)){console.warn(`VRMExpressionLoaderPlugin: ${d.name} attempts to index ${x}th morph but not found.`);return}g.addBind(new _e({primitives:y,index:x,weight:.01*((T=_.weight)!==null&&T!==void 0?T:100)}))})))}));let m=d.materialValues;m&&m.length!==0&&m.forEach(_=>{if(_.materialName===void 0||_.propertyName===void 0||_.targetValue===void 0)return;let v=[];e.scene.traverse(x=>{if(x.material){let E=x.material;Array.isArray(E)?v.push(...E.filter(T=>(T.name===_.materialName||T.name===_.materialName+" (Outline)")&&v.indexOf(T)===-1)):E.name===_.materialName&&v.indexOf(E)===-1&&v.push(E)}});let M=_.propertyName;v.forEach(x=>{if(M==="_MainTex_ST"){let T=new o.Vector2(_.targetValue[0],_.targetValue[1]),y=new o.Vector2(_.targetValue[2],_.targetValue[3]);y.y=1-y.y-T.y,g.addBind(new ne({material:x,scale:T,offset:y}));return}let E=ei[M];if(E){g.addBind(new te({material:x,type:E,targetValue:new o.Color().fromArray(_.targetValue),targetAlpha:_.targetValue[3]}));return}console.warn(M+" is not supported")})}),s.registerExpression(g)}))),s})}};ie.v0v1PresetNameMap={a:"aa",e:"ee",i:"ih",o:"oh",u:"ou",blink:"blink",joy:"happy",angry:"angry",sorrow:"sad",fun:"relaxed",lookup:"lookUp",lookdown:"lookDown",lookleft:"lookLeft",lookright:"lookRight",blink_l:"blinkLeft",blink_r:"blinkRight",neutral:"neutral"};var cr={None:"none",Block:"block",Blend:"blend"},q=class l{constructor(e,t){this._firstPersonOnlyLayer=l.DEFAULT_FIRSTPERSON_ONLY_LAYER,this._thirdPersonOnlyLayer=l.DEFAULT_THIRDPERSON_ONLY_LAYER,this._initializedLayers=!1,this.humanoid=e,this.meshAnnotations=t}copy(e){if(this.humanoid!==e.humanoid)throw new Error("VRMFirstPerson: humanoid must be same in order to copy");return this.meshAnnotations=e.meshAnnotations.map(t=>({meshes:t.meshes.concat(),type:t.type})),this}clone(){return new l(this.humanoid,this.meshAnnotations).copy(this)}get firstPersonOnlyLayer(){return this._firstPersonOnlyLayer}get thirdPersonOnlyLayer(){return this._thirdPersonOnlyLayer}setup({firstPersonOnlyLayer:e=l.DEFAULT_FIRSTPERSON_ONLY_LAYER,thirdPersonOnlyLayer:t=l.DEFAULT_THIRDPERSON_ONLY_LAYER}={}){this._initializedLayers||(this._firstPersonOnlyLayer=e,this._thirdPersonOnlyLayer=t,this.meshAnnotations.forEach(n=>{n.meshes.forEach(i=>{n.type==="firstPersonOnly"?(i.layers.set(this._firstPersonOnlyLayer),i.traverse(r=>r.layers.set(this._firstPersonOnlyLayer))):n.type==="thirdPersonOnly"?(i.layers.set(this._thirdPersonOnlyLayer),i.traverse(r=>r.layers.set(this._thirdPersonOnlyLayer))):n.type==="auto"&&this._createHeadlessModel(i)})}),this._initializedLayers=!0)}_excludeTriangles(e,t,n,i){let r=0;if(t!=null&&t.length>0)for(let s=0;s<e.length;s+=3){let a=e[s],u=e[s+1],d=e[s+2],c=t[a],h=n[a];if(c[0]>0&&i.includes(h[0])||c[1]>0&&i.includes(h[1])||c[2]>0&&i.includes(h[2])||c[3]>0&&i.includes(h[3]))continue;let p=t[u],f=n[u];if(p[0]>0&&i.includes(f[0])||p[1]>0&&i.includes(f[1])||p[2]>0&&i.includes(f[2])||p[3]>0&&i.includes(f[3]))continue;let g=t[d],m=n[d];g[0]>0&&i.includes(m[0])||g[1]>0&&i.includes(m[1])||g[2]>0&&i.includes(m[2])||g[3]>0&&i.includes(m[3])||(e[r++]=a,e[r++]=u,e[r++]=d)}return r}_createErasedMesh(e,t){let n=new o.SkinnedMesh(e.geometry.clone(),e.material);n.name=`${e.name}(erase)`,n.frustumCulled=e.frustumCulled,n.layers.set(this._firstPersonOnlyLayer);let i=n.geometry,r=i.getAttribute("skinIndex"),s=r instanceof o.GLBufferAttribute?[]:r.array,a=[];for(let m=0;m<s.length;m+=4)a.push([s[m],s[m+1],s[m+2],s[m+3]]);let u=i.getAttribute("skinWeight"),d=u instanceof o.GLBufferAttribute?[]:u.array,c=[];for(let m=0;m<d.length;m+=4)c.push([d[m],d[m+1],d[m+2],d[m+3]]);let h=i.getIndex();if(!h)throw new Error("The geometry doesn't have an index buffer");let p=Array.from(h.array),f=this._excludeTriangles(p,c,a,t),g=[];for(let m=0;m<f;m++)g[m]=p[m];return i.setIndex(g),e.onBeforeRender&&(n.onBeforeRender=e.onBeforeRender),n.bind(new o.Skeleton(e.skeleton.bones,e.skeleton.boneInverses),new o.Matrix4),n}_createHeadlessModelForSkinnedMesh(e,t){let n=[];if(t.skeleton.bones.forEach((r,s)=>{this._isEraseTarget(r)&&n.push(s)}),!n.length){t.layers.enable(this._thirdPersonOnlyLayer),t.layers.enable(this._firstPersonOnlyLayer);return}t.layers.set(this._thirdPersonOnlyLayer);let i=this._createErasedMesh(t,n);e.add(i)}_createHeadlessModel(e){if(e.type==="Group")if(e.layers.set(this._thirdPersonOnlyLayer),this._isEraseTarget(e))e.traverse(t=>t.layers.set(this._thirdPersonOnlyLayer));else{let t=new o.Group;t.name=`_headless_${e.name}`,t.layers.set(this._firstPersonOnlyLayer),e.parent.add(t),e.children.filter(n=>n.type==="SkinnedMesh").forEach(n=>{let i=n;this._createHeadlessModelForSkinnedMesh(t,i)})}else if(e.type==="SkinnedMesh"){let t=e;this._createHeadlessModelForSkinnedMesh(e.parent,t)}else this._isEraseTarget(e)&&(e.layers.set(this._thirdPersonOnlyLayer),e.traverse(t=>t.layers.set(this._thirdPersonOnlyLayer)))}_isEraseTarget(e){return e===this.humanoid.getRawBoneNode("head")?!0:e.parent?this._isEraseTarget(e.parent):!1}};q.DEFAULT_FIRSTPERSON_ONLY_LAYER=9;q.DEFAULT_THIRDPERSON_ONLY_LAYER=10;var ii=new Set(["1.0","1.0-beta"]),ge=class{get name(){return"VRMFirstPersonLoaderPlugin"}constructor(e){this.parser=e}afterRoot(e){return w(this,void 0,void 0,function*(){let t=e.userData.vrmHumanoid;if(t!==null){if(t===void 0)throw new Error("VRMFirstPersonLoaderPlugin: vrmHumanoid is undefined. VRMHumanoidLoaderPlugin have to be used first");e.userData.vrmFirstPerson=yield this._import(e,t)}})}_import(e,t){return w(this,void 0,void 0,function*(){if(t==null)return null;let n=yield this._v1Import(e,t);if(n)return n;let i=yield this._v0Import(e,t);return i||null})}_v1Import(e,t){var n,i;return w(this,void 0,void 0,function*(){let r=this.parser.json;if(!(((n=r.extensionsUsed)===null||n===void 0?void 0:n.indexOf("VRMC_vrm"))!==-1))return null;let a=(i=r.extensions)===null||i===void 0?void 0:i.VRMC_vrm;if(!a)return null;let u=a.specVersion;if(!ii.has(u))return console.warn(`VRMFirstPersonLoaderPlugin: Unknown VRMC_vrm specVersion "${u}"`),null;let d=a.firstPerson;if(!d)return null;let c=[],h=yield Kt(e);return Array.from(h.entries()).forEach(([p,f])=>{var g;let m=d.meshAnnotations?d.meshAnnotations.find(_=>_.node===p):void 0;c.push({meshes:f,type:(g=m?.type)!==null&&g!==void 0?g:"both"})}),new q(t,c)})}_v0Import(e,t){var n;return w(this,void 0,void 0,function*(){let i=this.parser.json,r=(n=i.extensions)===null||n===void 0?void 0:n.VRM;if(!r)return null;let s=r.firstPerson;if(!s)return null;let a=[],u=yield Kt(e);return Array.from(u.entries()).forEach(([d,c])=>{let h=i.nodes[d],p=s.meshAnnotations?s.meshAnnotations.find(f=>f.mesh===h.mesh):void 0;a.push({meshes:c,type:this._convertV0FlagToV1Type(p?.firstPersonFlag)})}),new q(t,a)})}_convertV0FlagToV1Type(e){return e==="FirstPersonOnly"?"firstPersonOnly":e==="ThirdPersonOnly"?"thirdPersonOnly":e==="Auto"?"auto":"both"}},hr={Auto:"auto",Both:"both",ThirdPersonOnly:"thirdPersonOnly",FirstPersonOnly:"firstPersonOnly"},nn=new o.Vector3,rn=new o.Vector3,ri=new o.Quaternion,Ee=class extends o.Group{constructor(e){super(),this.vrmHumanoid=e,this._boneAxesMap=new Map,Object.values(e.humanBones).forEach(t=>{let n=new o.AxesHelper(1);n.matrixAutoUpdate=!1,n.material.depthTest=!1,n.material.depthWrite=!1,this.add(n),this._boneAxesMap.set(t,n)})}dispose(){Array.from(this._boneAxesMap.values()).forEach(e=>{e.geometry.dispose(),e.material.dispose()})}updateMatrixWorld(e){Array.from(this._boneAxesMap.entries()).forEach(([t,n])=>{t.node.updateWorldMatrix(!0,!1),t.node.matrixWorld.decompose(nn,ri,rn);let i=nn.set(.1,.1,.1).divide(rn);n.matrix.copy(t.node.matrixWorld).scale(i)}),super.updateMatrixWorld(e)}},_t=["hips","spine","chest","upperChest","neck","head","leftEye","rightEye","jaw","leftUpperLeg","leftLowerLeg","leftFoot","leftToes","rightUpperLeg","rightLowerLeg","rightFoot","rightToes","leftShoulder","leftUpperArm","leftLowerArm","leftHand","rightShoulder","rightUpperArm","rightLowerArm","rightHand","leftThumbMetacarpal","leftThumbProximal","leftThumbDistal","leftIndexProximal","leftIndexIntermediate","leftIndexDistal","leftMiddleProximal","leftMiddleIntermediate","leftMiddleDistal","leftRingProximal","leftRingIntermediate","leftRingDistal","leftLittleProximal","leftLittleIntermediate","leftLittleDistal","rightThumbMetacarpal","rightThumbProximal","rightThumbDistal","rightIndexProximal","rightIndexIntermediate","rightIndexDistal","rightMiddleProximal","rightMiddleIntermediate","rightMiddleDistal","rightRingProximal","rightRingIntermediate","rightRingDistal","rightLittleProximal","rightLittleIntermediate","rightLittleDistal"],fr={Hips:"hips",Spine:"spine",Chest:"chest",UpperChest:"upperChest",Neck:"neck",Head:"head",LeftEye:"leftEye",RightEye:"rightEye",Jaw:"jaw",LeftUpperLeg:"leftUpperLeg",LeftLowerLeg:"leftLowerLeg",LeftFoot:"leftFoot",LeftToes:"leftToes",RightUpperLeg:"rightUpperLeg",RightLowerLeg:"rightLowerLeg",RightFoot:"rightFoot",RightToes:"rightToes",LeftShoulder:"leftShoulder",LeftUpperArm:"leftUpperArm",LeftLowerArm:"leftLowerArm",LeftHand:"leftHand",RightShoulder:"rightShoulder",RightUpperArm:"rightUpperArm",RightLowerArm:"rightLowerArm",RightHand:"rightHand",LeftThumbMetacarpal:"leftThumbMetacarpal",LeftThumbProximal:"leftThumbProximal",LeftThumbDistal:"leftThumbDistal",LeftIndexProximal:"leftIndexProximal",LeftIndexIntermediate:"leftIndexIntermediate",LeftIndexDistal:"leftIndexDistal",LeftMiddleProximal:"leftMiddleProximal",LeftMiddleIntermediate:"leftMiddleIntermediate",LeftMiddleDistal:"leftMiddleDistal",LeftRingProximal:"leftRingProximal",LeftRingIntermediate:"leftRingIntermediate",LeftRingDistal:"leftRingDistal",LeftLittleProximal:"leftLittleProximal",LeftLittleIntermediate:"leftLittleIntermediate",LeftLittleDistal:"leftLittleDistal",RightThumbMetacarpal:"rightThumbMetacarpal",RightThumbProximal:"rightThumbProximal",RightThumbDistal:"rightThumbDistal",RightIndexProximal:"rightIndexProximal",RightIndexIntermediate:"rightIndexIntermediate",RightIndexDistal:"rightIndexDistal",RightMiddleProximal:"rightMiddleProximal",RightMiddleIntermediate:"rightMiddleIntermediate",RightMiddleDistal:"rightMiddleDistal",RightRingProximal:"rightRingProximal",RightRingIntermediate:"rightRingIntermediate",RightRingDistal:"rightRingDistal",RightLittleProximal:"rightLittleProximal",RightLittleIntermediate:"rightLittleIntermediate",RightLittleDistal:"rightLittleDistal"},oi={hips:null,spine:"hips",chest:"spine",upperChest:"chest",neck:"upperChest",head:"neck",leftEye:"head",rightEye:"head",jaw:"head",leftUpperLeg:"hips",leftLowerLeg:"leftUpperLeg",leftFoot:"leftLowerLeg",leftToes:"leftFoot",rightUpperLeg:"hips",rightLowerLeg:"rightUpperLeg",rightFoot:"rightLowerLeg",rightToes:"rightFoot",leftShoulder:"upperChest",leftUpperArm:"leftShoulder",leftLowerArm:"leftUpperArm",leftHand:"leftLowerArm",rightShoulder:"upperChest",rightUpperArm:"rightShoulder",rightLowerArm:"rightUpperArm",rightHand:"rightLowerArm",leftThumbMetacarpal:"leftHand",leftThumbProximal:"leftThumbMetacarpal",leftThumbDistal:"leftThumbProximal",leftIndexProximal:"leftHand",leftIndexIntermediate:"leftIndexProximal",leftIndexDistal:"leftIndexIntermediate",leftMiddleProximal:"leftHand",leftMiddleIntermediate:"leftMiddleProximal",leftMiddleDistal:"leftMiddleIntermediate",leftRingProximal:"leftHand",leftRingIntermediate:"leftRingProximal",leftRingDistal:"leftRingIntermediate",leftLittleProximal:"leftHand",leftLittleIntermediate:"leftLittleProximal",leftLittleDistal:"leftLittleIntermediate",rightThumbMetacarpal:"rightHand",rightThumbProximal:"rightThumbMetacarpal",rightThumbDistal:"rightThumbProximal",rightIndexProximal:"rightHand",rightIndexIntermediate:"rightIndexProximal",rightIndexDistal:"rightIndexIntermediate",rightMiddleProximal:"rightHand",rightMiddleIntermediate:"rightMiddleProximal",rightMiddleDistal:"rightMiddleIntermediate",rightRingProximal:"rightHand",rightRingIntermediate:"rightRingProximal",rightRingDistal:"rightRingIntermediate",rightLittleProximal:"rightHand",rightLittleIntermediate:"rightLittleProximal",rightLittleDistal:"rightLittleIntermediate"};function Mn(l){return l.invert?l.invert():l.inverse(),l}var V=new o.Vector3,D=new o.Quaternion,re=class{constructor(e){this.humanBones=e,this.restPose=this.getAbsolutePose()}getAbsolutePose(){let e={};return Object.keys(this.humanBones).forEach(t=>{let n=t,i=this.getBoneNode(n);i&&(V.copy(i.position),D.copy(i.quaternion),e[n]={position:V.toArray(),rotation:D.toArray()})}),e}getPose(){let e={};return Object.keys(this.humanBones).forEach(t=>{let n=t,i=this.getBoneNode(n);if(!i)return;V.set(0,0,0),D.identity();let r=this.restPose[n];r?.position&&V.fromArray(r.position).negate(),r?.rotation&&Mn(D.fromArray(r.rotation)),V.add(i.position),D.premultiply(i.quaternion),e[n]={position:V.toArray(),rotation:D.toArray()}}),e}setPose(e){Object.entries(e).forEach(([t,n])=>{let i=t,r=this.getBoneNode(i);if(!r)return;let s=this.restPose[i];s&&(n?.position&&(r.position.fromArray(n.position),s.position&&r.position.add(V.fromArray(s.position))),n?.rotation&&(r.quaternion.fromArray(n.rotation),s.rotation&&r.quaternion.multiply(D.fromArray(s.rotation))))})}resetPose(){Object.entries(this.restPose).forEach(([e,t])=>{let n=this.getBoneNode(e);n&&(t?.position&&n.position.fromArray(t.position),t?.rotation&&n.quaternion.fromArray(t.rotation))})}getBone(e){var t;return(t=this.humanBones[e])!==null&&t!==void 0?t:void 0}getBoneNode(e){var t,n;return(n=(t=this.humanBones[e])===null||t===void 0?void 0:t.node)!==null&&n!==void 0?n:null}},gt=new o.Vector3,si=new o.Quaternion,ai=new o.Vector3,Te=class l extends re{static _setupTransforms(e){let t=new o.Object3D;t.name="VRMHumanoidRig";let n={},i={},r={};_t.forEach(a=>{var u;let d=e.getBoneNode(a);if(d){let c=new o.Vector3,h=new o.Quaternion;d.updateWorldMatrix(!0,!1),d.matrixWorld.decompose(c,h,gt),n[a]=c,i[a]=d.quaternion.clone();let p=new o.Quaternion;(u=d.parent)===null||u===void 0||u.matrixWorld.decompose(gt,p,gt),r[a]=p}});let s={};return _t.forEach(a=>{var u;let d=e.getBoneNode(a);if(d){let c=n[a],h=a,p;for(;p==null&&(h=oi[h],h!=null);)p=n[h];let f=new o.Object3D;f.name="Normalized_"+d.name,(h?(u=s[h])===null||u===void 0?void 0:u.node:t).add(f),f.position.copy(c),p&&f.position.sub(p),s[a]={node:f}}}),{rigBones:s,root:t,parentWorldRotations:r,boneRotations:i}}constructor(e){let{rigBones:t,root:n,parentWorldRotations:i,boneRotations:r}=l._setupTransforms(e);super(t),this.original=e,this.root=n,this._parentWorldRotations=i,this._boneRotations=r}update(){_t.forEach(e=>{let t=this.original.getBoneNode(e);if(t!=null){let n=this.getBoneNode(e),i=this._parentWorldRotations[e],r=si.copy(i).invert(),s=this._boneRotations[e];if(t.quaternion.copy(n.quaternion).multiply(i).premultiply(r).multiply(s),e==="hips"){let a=n.getWorldPosition(ai);t.parent.updateWorldMatrix(!0,!1);let u=t.parent.matrixWorld,d=a.applyMatrix4(u.invert());t.position.copy(d)}}})}},Me=class l{get restPose(){return console.warn("VRMHumanoid: restPose is deprecated. Use either rawRestPose or normalizedRestPose instead."),this.rawRestPose}get rawRestPose(){return this._rawHumanBones.restPose}get normalizedRestPose(){return this._normalizedHumanBones.restPose}get humanBones(){return this._rawHumanBones.humanBones}get rawHumanBones(){return this._rawHumanBones.humanBones}get normalizedHumanBones(){return this._normalizedHumanBones.humanBones}get normalizedHumanBonesRoot(){return this._normalizedHumanBones.root}constructor(e,t){var n;this.autoUpdateHumanBones=(n=t?.autoUpdateHumanBones)!==null&&n!==void 0?n:!0,this._rawHumanBones=new re(e),this._normalizedHumanBones=new Te(this._rawHumanBones)}copy(e){return this.autoUpdateHumanBones=e.autoUpdateHumanBones,this._rawHumanBones=new re(e.humanBones),this._normalizedHumanBones=new Te(this._rawHumanBones),this}clone(){return new l(this.humanBones,{autoUpdateHumanBones:this.autoUpdateHumanBones}).copy(this)}getAbsolutePose(){return console.warn("VRMHumanoid: getAbsolutePose() is deprecated. Use either getRawAbsolutePose() or getNormalizedAbsolutePose() instead."),this.getRawAbsolutePose()}getRawAbsolutePose(){return this._rawHumanBones.getAbsolutePose()}getNormalizedAbsolutePose(){return this._normalizedHumanBones.getAbsolutePose()}getPose(){return console.warn("VRMHumanoid: getPose() is deprecated. Use either getRawPose() or getNormalizedPose() instead."),this.getRawPose()}getRawPose(){return this._rawHumanBones.getPose()}getNormalizedPose(){return this._normalizedHumanBones.getPose()}setPose(e){return console.warn("VRMHumanoid: setPose() is deprecated. Use either setRawPose() or setNormalizedPose() instead."),this.setRawPose(e)}setRawPose(e){return this._rawHumanBones.setPose(e)}setNormalizedPose(e){return this._normalizedHumanBones.setPose(e)}resetPose(){return console.warn("VRMHumanoid: resetPose() is deprecated. Use either resetRawPose() or resetNormalizedPose() instead."),this.resetRawPose()}resetRawPose(){return this._rawHumanBones.resetPose()}resetNormalizedPose(){return this._normalizedHumanBones.resetPose()}getBone(e){return console.warn("VRMHumanoid: getBone() is deprecated. Use either getRawBone() or getNormalizedBone() instead."),this.getRawBone(e)}getRawBone(e){return this._rawHumanBones.getBone(e)}getNormalizedBone(e){return this._normalizedHumanBones.getBone(e)}getBoneNode(e){return console.warn("VRMHumanoid: getBoneNode() is deprecated. Use either getRawBoneNode() or getNormalizedBoneNode() instead."),this.getRawBoneNode(e)}getRawBoneNode(e){return this._rawHumanBones.getBoneNode(e)}getNormalizedBoneNode(e){return this._normalizedHumanBones.getBoneNode(e)}update(){this.autoUpdateHumanBones&&this._normalizedHumanBones.update()}},li={Hips:"hips",Spine:"spine",Head:"head",LeftUpperLeg:"leftUpperLeg",LeftLowerLeg:"leftLowerLeg",LeftFoot:"leftFoot",RightUpperLeg:"rightUpperLeg",RightLowerLeg:"rightLowerLeg",RightFoot:"rightFoot",LeftUpperArm:"leftUpperArm",LeftLowerArm:"leftLowerArm",LeftHand:"leftHand",RightUpperArm:"rightUpperArm",RightLowerArm:"rightLowerArm",RightHand:"rightHand"},ui=new Set(["1.0","1.0-beta"]),on={leftThumbProximal:"leftThumbMetacarpal",leftThumbIntermediate:"leftThumbProximal",rightThumbProximal:"rightThumbMetacarpal",rightThumbIntermediate:"rightThumbProximal"},Re=class{get name(){return"VRMHumanoidLoaderPlugin"}constructor(e,t){this.parser=e,this.helperRoot=t?.helperRoot,this.autoUpdateHumanBones=t?.autoUpdateHumanBones}afterRoot(e){return w(this,void 0,void 0,function*(){e.userData.vrmHumanoid=yield this._import(e)})}_import(e){return w(this,void 0,void 0,function*(){let t=yield this._v1Import(e);if(t)return t;let n=yield this._v0Import(e);return n||null})}_v1Import(e){var t,n;return w(this,void 0,void 0,function*(){let i=this.parser.json;if(!(((t=i.extensionsUsed)===null||t===void 0?void 0:t.indexOf("VRMC_vrm"))!==-1))return null;let s=(n=i.extensions)===null||n===void 0?void 0:n.VRMC_vrm;if(!s)return null;let a=s.specVersion;if(!ui.has(a))return console.warn(`VRMHumanoidLoaderPlugin: Unknown VRMC_vrm specVersion "${a}"`),null;let u=s.humanoid;if(!u)return null;let d=u.humanBones.leftThumbIntermediate!=null||u.humanBones.rightThumbIntermediate!=null,c={};u.humanBones!=null&&(yield Promise.all(Object.entries(u.humanBones).map(([p,f])=>w(this,void 0,void 0,function*(){let g=p,m=f.node;if(d){let v=on[g];v!=null&&(g=v)}let _=yield this.parser.getDependency("node",m);if(_==null){console.warn(`A glTF node bound to the humanoid bone ${g} (index = ${m}) does not exist`);return}c[g]={node:_}}))));let h=new Me(this._ensureRequiredBonesExist(c),{autoUpdateHumanBones:this.autoUpdateHumanBones});if(e.scene.add(h.normalizedHumanBonesRoot),this.helperRoot){let p=new Ee(h);this.helperRoot.add(p),p.renderOrder=this.helperRoot.renderOrder}return h})}_v0Import(e){var t;return w(this,void 0,void 0,function*(){let i=(t=this.parser.json.extensions)===null||t===void 0?void 0:t.VRM;if(!i)return null;let r=i.humanoid;if(!r)return null;let s={};r.humanBones!=null&&(yield Promise.all(r.humanBones.map(u=>w(this,void 0,void 0,function*(){let d=u.bone,c=u.node;if(d==null||c==null)return;let h=yield this.parser.getDependency("node",c);if(h==null){console.warn(`A glTF node bound to the humanoid bone ${d} (index = ${c}) does not exist`);return}let p=on[d],f=p??d;if(s[f]!=null){console.warn(`Multiple bone entries for ${f} detected (index = ${c}), ignoring duplicated entries.`);return}s[f]={node:h}}))));let a=new Me(this._ensureRequiredBonesExist(s),{autoUpdateHumanBones:this.autoUpdateHumanBones});if(e.scene.add(a.normalizedHumanBonesRoot),this.helperRoot){let u=new Ee(a);this.helperRoot.add(u),u.renderOrder=this.helperRoot.renderOrder}return a})}_ensureRequiredBonesExist(e){let t=Object.values(li).filter(n=>e[n]==null);if(t.length>0)throw new Error(`VRMHumanoidLoaderPlugin: These humanoid bones are required but not exist: ${t.join(", ")}`);return e}},xe=class extends o.BufferGeometry{constructor(){super(),this._currentTheta=0,this._currentRadius=0,this.theta=0,this.radius=0,this._currentTheta=0,this._currentRadius=0,this._attrPos=new o.BufferAttribute(new Float32Array(65*3),3),this.setAttribute("position",this._attrPos),this._attrIndex=new o.BufferAttribute(new Uint16Array(3*63),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let e=!1;this._currentTheta!==this.theta&&(this._currentTheta=this.theta,e=!0),this._currentRadius!==this.radius&&(this._currentRadius=this.radius,e=!0),e&&this._buildPosition()}_buildPosition(){this._attrPos.setXYZ(0,0,0,0);for(let e=0;e<64;e++){let t=e/63*this._currentTheta;this._attrPos.setXYZ(e+1,this._currentRadius*Math.sin(t),0,this._currentRadius*Math.cos(t))}this._attrPos.needsUpdate=!0}_buildIndex(){for(let e=0;e<63;e++)this._attrIndex.setXYZ(e*3,0,e+1,e+2);this._attrIndex.needsUpdate=!0}},wt=class extends o.BufferGeometry{constructor(){super(),this.radius=0,this._currentRadius=0,this.tail=new o.Vector3,this._currentTail=new o.Vector3,this._attrPos=new o.BufferAttribute(new Float32Array(294),3),this.setAttribute("position",this._attrPos),this._attrIndex=new o.BufferAttribute(new Uint16Array(194),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let e=!1;this._currentRadius!==this.radius&&(this._currentRadius=this.radius,e=!0),this._currentTail.equals(this.tail)||(this._currentTail.copy(this.tail),e=!0),e&&this._buildPosition()}_buildPosition(){for(let e=0;e<32;e++){let t=e/16*Math.PI;this._attrPos.setXYZ(e,Math.cos(t),Math.sin(t),0),this._attrPos.setXYZ(32+e,0,Math.cos(t),Math.sin(t)),this._attrPos.setXYZ(64+e,Math.sin(t),0,Math.cos(t))}this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.setXYZ(96,0,0,0),this._attrPos.setXYZ(97,this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let e=0;e<32;e++){let t=(e+1)%32;this._attrIndex.setXY(e*2,e,t),this._attrIndex.setXY(64+e*2,32+e,32+t),this._attrIndex.setXY(128+e*2,64+e,64+t)}this._attrIndex.setXY(192,96,97),this._attrIndex.needsUpdate=!0}},de=new o.Quaternion,sn=new o.Quaternion,Y=new o.Vector3,an=new o.Vector3,ln=Math.sqrt(2)/2,di=new o.Quaternion(0,0,-ln,ln),ci=new o.Vector3(0,1,0),St=class extends o.Group{constructor(e){super(),this.matrixAutoUpdate=!1,this.vrmLookAt=e;{let t=new xe;t.radius=.5;let n=new o.MeshBasicMaterial({color:65280,transparent:!0,opacity:.5,side:o.DoubleSide,depthTest:!1,depthWrite:!1});this._meshPitch=new o.Mesh(t,n),this.add(this._meshPitch)}{let t=new xe;t.radius=.5;let n=new o.MeshBasicMaterial({color:16711680,transparent:!0,opacity:.5,side:o.DoubleSide,depthTest:!1,depthWrite:!1});this._meshYaw=new o.Mesh(t,n),this.add(this._meshYaw)}{let t=new wt;t.radius=.1;let n=new o.LineBasicMaterial({color:16777215,depthTest:!1,depthWrite:!1});this._lineTarget=new o.LineSegments(t,n),this._lineTarget.frustumCulled=!1,this.add(this._lineTarget)}}dispose(){this._meshYaw.geometry.dispose(),this._meshYaw.material.dispose(),this._meshPitch.geometry.dispose(),this._meshPitch.material.dispose(),this._lineTarget.geometry.dispose(),this._lineTarget.material.dispose()}updateMatrixWorld(e){let t=o.MathUtils.DEG2RAD*this.vrmLookAt.yaw;this._meshYaw.geometry.theta=t,this._meshYaw.geometry.update();let n=o.MathUtils.DEG2RAD*this.vrmLookAt.pitch;this._meshPitch.geometry.theta=n,this._meshPitch.geometry.update(),this.vrmLookAt.getLookAtWorldPosition(Y),this.vrmLookAt.getLookAtWorldQuaternion(de),de.multiply(this.vrmLookAt.getFaceFrontQuaternion(sn)),this._meshYaw.position.copy(Y),this._meshYaw.quaternion.copy(de),this._meshPitch.position.copy(Y),this._meshPitch.quaternion.copy(de),this._meshPitch.quaternion.multiply(sn.setFromAxisAngle(ci,t)),this._meshPitch.quaternion.multiply(di);let{target:i,autoUpdate:r}=this.vrmLookAt;i!=null&&r&&(i.getWorldPosition(an).sub(Y),this._lineTarget.geometry.tail.copy(an),this._lineTarget.geometry.update(),this._lineTarget.position.copy(Y)),super.updateMatrixWorld(e)}},hi=new o.Vector3,fi=new o.Vector3;function At(l,e){return l.matrixWorld.decompose(hi,e,fi),e}function pe(l){return[Math.atan2(-l.z,l.x),Math.atan2(l.y,Math.sqrt(l.x*l.x+l.z*l.z))]}function un(l){let e=Math.round(l/2/Math.PI);return l-2*Math.PI*e}var dn=new o.Vector3(0,0,1),pi=new o.Vector3,mi=new o.Vector3,vi=new o.Vector3,_i=new o.Quaternion,Et=new o.Quaternion,cn=new o.Quaternion,gi=new o.Quaternion,Tt=new o.Euler,ye=class l{get yaw(){return this._yaw}set yaw(e){this._yaw=e,this._needsUpdate=!0}get pitch(){return this._pitch}set pitch(e){this._pitch=e,this._needsUpdate=!0}get euler(){return console.warn("VRMLookAt: euler is deprecated. use getEuler() instead."),this.getEuler(new o.Euler)}constructor(e,t){this.offsetFromHeadBone=new o.Vector3,this.autoUpdate=!0,this.faceFront=new o.Vector3(0,0,1),this.humanoid=e,this.applier=t,this._yaw=0,this._pitch=0,this._needsUpdate=!0,this._restHeadWorldQuaternion=this.getLookAtWorldQuaternion(new o.Quaternion)}getEuler(e){return e.set(o.MathUtils.DEG2RAD*this._pitch,o.MathUtils.DEG2RAD*this._yaw,0,"YXZ")}copy(e){if(this.humanoid!==e.humanoid)throw new Error("VRMLookAt: humanoid must be same in order to copy");return this.offsetFromHeadBone.copy(e.offsetFromHeadBone),this.applier=e.applier,this.autoUpdate=e.autoUpdate,this.target=e.target,this.faceFront.copy(e.faceFront),this}clone(){return new l(this.humanoid,this.applier).copy(this)}reset(){this._yaw=0,this._pitch=0,this._needsUpdate=!0}getLookAtWorldPosition(e){let t=this.humanoid.getRawBoneNode("head");return e.copy(this.offsetFromHeadBone).applyMatrix4(t.matrixWorld)}getLookAtWorldQuaternion(e){let t=this.humanoid.getRawBoneNode("head");return At(t,e)}getFaceFrontQuaternion(e){if(this.faceFront.distanceToSquared(dn)<.01)return e.copy(this._restHeadWorldQuaternion).invert();let[t,n]=pe(this.faceFront);return Tt.set(0,.5*Math.PI+t,n,"YZX"),e.setFromEuler(Tt).premultiply(gi.copy(this._restHeadWorldQuaternion).invert())}getLookAtWorldDirection(e){return this.getLookAtWorldQuaternion(Et),this.getFaceFrontQuaternion(cn),e.copy(dn).applyQuaternion(Et).applyQuaternion(cn).applyEuler(this.getEuler(Tt))}lookAt(e){let t=_i.copy(this._restHeadWorldQuaternion).multiply(Mn(this.getLookAtWorldQuaternion(Et))),n=this.getLookAtWorldPosition(mi),i=vi.copy(e).sub(n).applyQuaternion(t).normalize(),[r,s]=pe(this.faceFront),[a,u]=pe(i),d=un(a-r),c=un(s-u);this._yaw=o.MathUtils.RAD2DEG*d,this._pitch=o.MathUtils.RAD2DEG*c,this._needsUpdate=!0}update(e){this.target!=null&&this.autoUpdate&&this.lookAt(this.target.getWorldPosition(pi)),this._needsUpdate&&(this._needsUpdate=!1,this.applier.applyYawPitch(this._yaw,this._pitch))}};ye.EULER_ORDER="YXZ";var Ei=new o.Vector3(0,0,1),H=new o.Quaternion,k=new o.Quaternion,I=new o.Euler(0,0,0,"YXZ"),Q=class{constructor(e,t,n,i,r){this.humanoid=e,this.rangeMapHorizontalInner=t,this.rangeMapHorizontalOuter=n,this.rangeMapVerticalDown=i,this.rangeMapVerticalUp=r,this.faceFront=new o.Vector3(0,0,1),this._restQuatLeftEye=new o.Quaternion,this._restQuatRightEye=new o.Quaternion,this._restLeftEyeParentWorldQuat=new o.Quaternion,this._restRightEyeParentWorldQuat=new o.Quaternion;let s=this.humanoid.getRawBoneNode("leftEye"),a=this.humanoid.getRawBoneNode("rightEye");s&&(this._restQuatLeftEye.copy(s.quaternion),At(s.parent,this._restLeftEyeParentWorldQuat)),a&&(this._restQuatRightEye.copy(a.quaternion),At(a.parent,this._restRightEyeParentWorldQuat))}applyYawPitch(e,t){let n=this.humanoid.getRawBoneNode("leftEye"),i=this.humanoid.getRawBoneNode("rightEye"),r=this.humanoid.getNormalizedBoneNode("leftEye"),s=this.humanoid.getNormalizedBoneNode("rightEye");n&&(t<0?I.x=-o.MathUtils.DEG2RAD*this.rangeMapVerticalDown.map(-t):I.x=o.MathUtils.DEG2RAD*this.rangeMapVerticalUp.map(t),e<0?I.y=-o.MathUtils.DEG2RAD*this.rangeMapHorizontalInner.map(-e):I.y=o.MathUtils.DEG2RAD*this.rangeMapHorizontalOuter.map(e),H.setFromEuler(I),this._getWorldFaceFrontQuat(k),r.quaternion.copy(k).multiply(H).multiply(k.invert()),H.copy(this._restLeftEyeParentWorldQuat),n.quaternion.copy(r.quaternion).multiply(H).premultiply(H.invert()).multiply(this._restQuatLeftEye)),i&&(t<0?I.x=-o.MathUtils.DEG2RAD*this.rangeMapVerticalDown.map(-t):I.x=o.MathUtils.DEG2RAD*this.rangeMapVerticalUp.map(t),e<0?I.y=-o.MathUtils.DEG2RAD*this.rangeMapHorizontalOuter.map(-e):I.y=o.MathUtils.DEG2RAD*this.rangeMapHorizontalInner.map(e),H.setFromEuler(I),this._getWorldFaceFrontQuat(k),s.quaternion.copy(k).multiply(H).multiply(k.invert()),H.copy(this._restRightEyeParentWorldQuat),i.quaternion.copy(s.quaternion).multiply(H).premultiply(H.invert()).multiply(this._restQuatRightEye))}lookAt(e){console.warn("VRMLookAtBoneApplier: lookAt() is deprecated. use apply() instead.");let t=o.MathUtils.RAD2DEG*e.y,n=o.MathUtils.RAD2DEG*e.x;this.applyYawPitch(t,n)}_getWorldFaceFrontQuat(e){if(this.faceFront.distanceToSquared(Ei)<.01)return e.identity();let[t,n]=pe(this.faceFront);return I.set(0,.5*Math.PI+t,n,"YZX"),e.setFromEuler(I)}};Q.type="bone";var oe=class{constructor(e,t,n,i,r){this.expressions=e,this.rangeMapHorizontalInner=t,this.rangeMapHorizontalOuter=n,this.rangeMapVerticalDown=i,this.rangeMapVerticalUp=r}applyYawPitch(e,t){t<0?(this.expressions.setValue("lookDown",0),this.expressions.setValue("lookUp",this.rangeMapVerticalUp.map(-t))):(this.expressions.setValue("lookUp",0),this.expressions.setValue("lookDown",this.rangeMapVerticalDown.map(t))),e<0?(this.expressions.setValue("lookLeft",0),this.expressions.setValue("lookRight",this.rangeMapHorizontalOuter.map(-e))):(this.expressions.setValue("lookRight",0),this.expressions.setValue("lookLeft",this.rangeMapHorizontalOuter.map(e)))}lookAt(e){console.warn("VRMLookAtBoneApplier: lookAt() is deprecated. use apply() instead.");let t=o.MathUtils.RAD2DEG*e.y,n=o.MathUtils.RAD2DEG*e.x;this.applyYawPitch(t,n)}};oe.type="expression";var we=class{constructor(e,t){this.inputMaxValue=e,this.outputScale=t}map(e){return this.outputScale*Tn(e/this.inputMaxValue)}},Ti=new Set(["1.0","1.0-beta"]),ce=.01,Se=class{get name(){return"VRMLookAtLoaderPlugin"}constructor(e,t){this.parser=e,this.helperRoot=t?.helperRoot}afterRoot(e){return w(this,void 0,void 0,function*(){let t=e.userData.vrmHumanoid;if(t===null)return;if(t===void 0)throw new Error("VRMLookAtLoaderPlugin: vrmHumanoid is undefined. VRMHumanoidLoaderPlugin have to be used first");let n=e.userData.vrmExpressionManager;if(n!==null){if(n===void 0)throw new Error("VRMLookAtLoaderPlugin: vrmExpressionManager is undefined. VRMExpressionLoaderPlugin have to be used first");e.userData.vrmLookAt=yield this._import(e,t,n)}})}_import(e,t,n){return w(this,void 0,void 0,function*(){if(t==null||n==null)return null;let i=yield this._v1Import(e,t,n);if(i)return i;let r=yield this._v0Import(e,t,n);return r||null})}_v1Import(e,t,n){var i,r,s;return w(this,void 0,void 0,function*(){let a=this.parser.json;if(!(((i=a.extensionsUsed)===null||i===void 0?void 0:i.indexOf("VRMC_vrm"))!==-1))return null;let d=(r=a.extensions)===null||r===void 0?void 0:r.VRMC_vrm;if(!d)return null;let c=d.specVersion;if(!Ti.has(c))return console.warn(`VRMLookAtLoaderPlugin: Unknown VRMC_vrm specVersion "${c}"`),null;let h=d.lookAt;if(!h)return null;let p=h.type==="expression"?1:10,f=this._v1ImportRangeMap(h.rangeMapHorizontalInner,p),g=this._v1ImportRangeMap(h.rangeMapHorizontalOuter,p),m=this._v1ImportRangeMap(h.rangeMapVerticalDown,p),_=this._v1ImportRangeMap(h.rangeMapVerticalUp,p),v;h.type==="expression"?v=new oe(n,f,g,m,_):v=new Q(t,f,g,m,_);let M=this._importLookAt(t,v);return M.offsetFromHeadBone.fromArray((s=h.offsetFromHeadBone)!==null&&s!==void 0?s:[0,.06,0]),M})}_v1ImportRangeMap(e,t){var n,i;let r=(n=e?.inputMaxValue)!==null&&n!==void 0?n:90,s=(i=e?.outputScale)!==null&&i!==void 0?i:t;return r<ce&&(console.warn("VRMLookAtLoaderPlugin: inputMaxValue of a range map is too small. Consider reviewing the range map!"),r=ce),new we(r,s)}_v0Import(e,t,n){var i,r,s,a;return w(this,void 0,void 0,function*(){let d=(i=this.parser.json.extensions)===null||i===void 0?void 0:i.VRM;if(!d)return null;let c=d.firstPerson;if(!c)return null;let h=c.lookAtTypeName==="BlendShape"?1:10,p=this._v0ImportDegreeMap(c.lookAtHorizontalInner,h),f=this._v0ImportDegreeMap(c.lookAtHorizontalOuter,h),g=this._v0ImportDegreeMap(c.lookAtVerticalDown,h),m=this._v0ImportDegreeMap(c.lookAtVerticalUp,h),_;c.lookAtTypeName==="BlendShape"?_=new oe(n,p,f,g,m):_=new Q(t,p,f,g,m);let v=this._importLookAt(t,_);return c.firstPersonBoneOffset?v.offsetFromHeadBone.set((r=c.firstPersonBoneOffset.x)!==null&&r!==void 0?r:0,(s=c.firstPersonBoneOffset.y)!==null&&s!==void 0?s:.06,-((a=c.firstPersonBoneOffset.z)!==null&&a!==void 0?a:0)):v.offsetFromHeadBone.set(0,.06,0),v.faceFront.set(0,0,-1),_ instanceof Q&&_.faceFront.set(0,0,-1),v})}_v0ImportDegreeMap(e,t){var n,i;let r=e?.curve;JSON.stringify(r)!=="[0,0,0,1,1,1,1,0]"&&console.warn("Curves of LookAtDegreeMap defined in VRM 0.0 are not supported");let s=(n=e?.xRange)!==null&&n!==void 0?n:90,a=(i=e?.yRange)!==null&&i!==void 0?i:t;return s<ce&&(console.warn("VRMLookAtLoaderPlugin: xRange of a degree map is too small. Consider reviewing the degree map!"),s=ce),new we(s,a)}_importLookAt(e,t){let n=new ye(e,t);if(this.helperRoot){let i=new St(n);this.helperRoot.add(i),i.renderOrder=this.helperRoot.renderOrder}return n}},pr={Bone:"bone",Expression:"expression"};function Mi(l,e){return typeof l!="string"||l===""?"":(/^https?:\/\//i.test(e)&&/^\//.test(l)&&(e=e.replace(/(^https?:\/\/[^/]+).*/i,"$1")),/^(https?:)?\/\//i.test(l)||/^data:.*,.*$/i.test(l)||/^blob:.*$/i.test(l)?l:e+l)}var Ri=new Set(["1.0","1.0-beta"]),Ae=class{get name(){return"VRMMetaLoaderPlugin"}constructor(e,t){var n,i,r;this.parser=e,this.needThumbnailImage=(n=t?.needThumbnailImage)!==null&&n!==void 0?n:!0,this.acceptLicenseUrls=(i=t?.acceptLicenseUrls)!==null&&i!==void 0?i:["https://vrm.dev/licenses/1.0/"],this.acceptV0Meta=(r=t?.acceptV0Meta)!==null&&r!==void 0?r:!0}afterRoot(e){return w(this,void 0,void 0,function*(){e.userData.vrmMeta=yield this._import(e)})}_import(e){return w(this,void 0,void 0,function*(){let t=yield this._v1Import(e);if(t!=null)return t;let n=yield this._v0Import(e);return n??null})}_v1Import(e){var t,n,i;return w(this,void 0,void 0,function*(){let r=this.parser.json;if(!(((t=r.extensionsUsed)===null||t===void 0?void 0:t.indexOf("VRMC_vrm"))!==-1))return null;let a=(n=r.extensions)===null||n===void 0?void 0:n.VRMC_vrm;if(a==null)return null;let u=a.specVersion;if(!Ri.has(u))return console.warn(`VRMMetaLoaderPlugin: Unknown VRMC_vrm specVersion "${u}"`),null;let d=a.meta;if(!d)return null;let c=d.licenseUrl;if(!new Set(this.acceptLicenseUrls).has(c))throw new Error(`VRMMetaLoaderPlugin: The license url "${c}" is not accepted`);let p;return this.needThumbnailImage&&d.thumbnailImage!=null&&(p=(i=yield this._extractGLTFImage(d.thumbnailImage))!==null&&i!==void 0?i:void 0),{metaVersion:"1",name:d.name,version:d.version,authors:d.authors,copyrightInformation:d.copyrightInformation,contactInformation:d.contactInformation,references:d.references,thirdPartyLicenses:d.thirdPartyLicenses,thumbnailImage:p,licenseUrl:d.licenseUrl,avatarPermission:d.avatarPermission,allowExcessivelyViolentUsage:d.allowExcessivelyViolentUsage,allowExcessivelySexualUsage:d.allowExcessivelySexualUsage,commercialUsage:d.commercialUsage,allowPoliticalOrReligiousUsage:d.allowPoliticalOrReligiousUsage,allowAntisocialOrHateUsage:d.allowAntisocialOrHateUsage,creditNotation:d.creditNotation,allowRedistribution:d.allowRedistribution,modification:d.modification,otherLicenseUrl:d.otherLicenseUrl}})}_v0Import(e){var t;return w(this,void 0,void 0,function*(){let i=(t=this.parser.json.extensions)===null||t===void 0?void 0:t.VRM;if(!i)return null;let r=i.meta;if(!r)return null;if(!this.acceptV0Meta)throw new Error("VRMMetaLoaderPlugin: Attempted to load VRM0.0 meta but acceptV0Meta is false");let s;return this.needThumbnailImage&&r.texture!=null&&r.texture!==-1&&(s=yield this.parser.getDependency("texture",r.texture)),{metaVersion:"0",allowedUserName:r.allowedUserName,author:r.author,commercialUssageName:r.commercialUssageName,contactInformation:r.contactInformation,licenseName:r.licenseName,otherLicenseUrl:r.otherLicenseUrl,otherPermissionUrl:r.otherPermissionUrl,reference:r.reference,sexualUssageName:r.sexualUssageName,texture:s??void 0,title:r.title,version:r.version,violentUssageName:r.violentUssageName}})}_extractGLTFImage(e){var t;return w(this,void 0,void 0,function*(){let i=(t=this.parser.json.images)===null||t===void 0?void 0:t[e];if(i==null)return console.warn(`VRMMetaLoaderPlugin: Attempt to use images[${e}] of glTF as a thumbnail but the image doesn't exist`),null;let r=i.uri;if(i.bufferView!=null){let a=yield this.parser.getDependency("bufferView",i.bufferView),u=new Blob([a],{type:i.mimeType});r=URL.createObjectURL(u)}return r==null?(console.warn(`VRMMetaLoaderPlugin: Attempt to use images[${e}] of glTF as a thumbnail but the image couldn't load properly`),null):yield new o.ImageLoader().loadAsync(Mi(r,this.parser.options.path)).catch(a=>(console.error(a),console.warn("VRMMetaLoaderPlugin: Failed to load a thumbnail image"),null))})}},Pe=class{constructor(e){this.scene=e.scene,this.meta=e.meta,this.humanoid=e.humanoid,this.expressionManager=e.expressionManager,this.firstPerson=e.firstPerson,this.lookAt=e.lookAt}update(e){this.humanoid.update(),this.lookAt&&this.lookAt.update(e),this.expressionManager&&this.expressionManager.update()}},hn=class{get name(){return"VRMC_vrm"}constructor(e,t){var n,i,r,s,a;this.parser=e;let u=t?.helperRoot,d=t?.autoUpdateHumanBones;this.expressionPlugin=(n=t?.expressionPlugin)!==null&&n!==void 0?n:new ie(e),this.firstPersonPlugin=(i=t?.firstPersonPlugin)!==null&&i!==void 0?i:new ge(e),this.humanoidPlugin=(r=t?.humanoidPlugin)!==null&&r!==void 0?r:new Re(e,{helperRoot:u,autoUpdateHumanBones:d}),this.lookAtPlugin=(s=t?.lookAtPlugin)!==null&&s!==void 0?s:new Se(e,{helperRoot:u}),this.metaPlugin=(a=t?.metaPlugin)!==null&&a!==void 0?a:new Ae(e)}afterRoot(e){return w(this,void 0,void 0,function*(){yield this.metaPlugin.afterRoot(e),yield this.humanoidPlugin.afterRoot(e),yield this.expressionPlugin.afterRoot(e),yield this.lookAtPlugin.afterRoot(e),yield this.firstPersonPlugin.afterRoot(e);let t=e.userData.vrmMeta,n=e.userData.vrmHumanoid;if(t&&n){let i=new Pe({scene:e.scene,expressionManager:e.userData.vrmExpressionManager,firstPerson:e.userData.vrmFirstPerson,humanoid:n,lookAt:e.userData.vrmLookAt,meta:t});e.userData.vrmCore=i}})}},Pt=class extends Pe{constructor(e){super(e),this.materials=e.materials,this.springBoneManager=e.springBoneManager,this.nodeConstraintManager=e.nodeConstraintManager}update(e){super.update(e),this.nodeConstraintManager&&this.nodeConstraintManager.update(),this.springBoneManager&&this.springBoneManager.update(e),this.materials&&this.materials.forEach(t=>{t.update&&t.update(e)})}};function he(l,e,t,n){function i(r){return r instanceof t?r:new t(function(s){s(r)})}return new(t||(t=Promise))(function(r,s){function a(c){try{d(n.next(c))}catch(h){s(h)}}function u(c){try{d(n.throw(c))}catch(h){s(h)}}function d(c){c.done?r(c.value):i(c.value).then(a,u)}d((n=n.apply(l,e||[])).next())})}function B(l,e,t,n){function i(r){return r instanceof t?r:new t(function(s){s(r)})}return new(t||(t=Promise))(function(r,s){function a(c){try{d(n.next(c))}catch(h){s(h)}}function u(c){try{d(n.throw(c))}catch(h){s(h)}}function d(c){c.done?r(c.value):i(c.value).then(a,u)}d((n=n.apply(l,e||[])).next())})}var xi=`// #define PHONG

varying vec3 vViewPosition;

#ifndef FLAT_SHADED
  varying vec3 vNormal;
#endif

#include <common>

// #include <uv_pars_vertex>
#ifdef MTOON_USE_UV
  varying vec2 vUv;

  // COMPAT: pre-r151 uses a common uvTransform
  #if THREE_VRM_THREE_REVISION < 151
    uniform mat3 uvTransform;
  #endif
#endif

// #include <uv2_pars_vertex>
// COMAPT: pre-r151 uses uv2 for lightMap and aoMap
#if THREE_VRM_THREE_REVISION < 151
  #if defined( USE_LIGHTMAP ) || defined( USE_AOMAP )
    attribute vec2 uv2;
    varying vec2 vUv2;
    uniform mat3 uv2Transform;
  #endif
#endif

// #include <displacementmap_pars_vertex>
// #include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>

#ifdef USE_OUTLINEWIDTHMULTIPLYTEXTURE
  uniform sampler2D outlineWidthMultiplyTexture;
  uniform mat3 outlineWidthMultiplyTextureUvTransform;
#endif

uniform float outlineWidthFactor;

void main() {

  // #include <uv_vertex>
  #ifdef MTOON_USE_UV
    // COMPAT: pre-r151 uses a common uvTransform
    #if THREE_VRM_THREE_REVISION >= 151
      vUv = uv;
    #else
      vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
    #endif
  #endif

  // #include <uv2_vertex>
  // COMAPT: pre-r151 uses uv2 for lightMap and aoMap
  #if THREE_VRM_THREE_REVISION < 151
    #if defined( USE_LIGHTMAP ) || defined( USE_AOMAP )
      vUv2 = ( uv2Transform * vec3( uv2, 1 ) ).xy;
    #endif
  #endif

  #include <color_vertex>

  #include <beginnormal_vertex>
  #include <morphnormal_vertex>
  #include <skinbase_vertex>
  #include <skinnormal_vertex>

  // we need this to compute the outline properly
  objectNormal = normalize( objectNormal );

  #include <defaultnormal_vertex>

  #ifndef FLAT_SHADED // Normal computed with derivatives when FLAT_SHADED
    vNormal = normalize( transformedNormal );
  #endif

  #include <begin_vertex>

  #include <morphtarget_vertex>
  #include <skinning_vertex>
  // #include <displacementmap_vertex>
  #include <project_vertex>
  #include <logdepthbuf_vertex>
  #include <clipping_planes_vertex>

  vViewPosition = - mvPosition.xyz;

  float outlineTex = 1.0;

  #ifdef OUTLINE
    #ifdef USE_OUTLINEWIDTHMULTIPLYTEXTURE
      vec2 outlineWidthMultiplyTextureUv = ( outlineWidthMultiplyTextureUvTransform * vec3( vUv, 1 ) ).xy;
      outlineTex = texture2D( outlineWidthMultiplyTexture, outlineWidthMultiplyTextureUv ).g;
    #endif

    #ifdef OUTLINE_WIDTH_WORLD
      float worldNormalLength = length( transformedNormal );
      vec3 outlineOffset = outlineWidthFactor * outlineTex * worldNormalLength * objectNormal;
      gl_Position = projectionMatrix * modelViewMatrix * vec4( outlineOffset + transformed, 1.0 );
    #endif

    #ifdef OUTLINE_WIDTH_SCREEN
      vec3 clipNormal = ( projectionMatrix * modelViewMatrix * vec4( objectNormal, 0.0 ) ).xyz;
      vec2 projectedNormal = normalize( clipNormal.xy );
      projectedNormal.x *= projectionMatrix[ 0 ].x / projectionMatrix[ 1 ].y;
      gl_Position.xy += 2.0 * outlineWidthFactor * outlineTex * projectedNormal.xy;
    #endif

    gl_Position.z += 1E-6 * gl_Position.w; // anti-artifact magic
  #endif

  #include <worldpos_vertex>
  // #include <envmap_vertex>
  #include <shadowmap_vertex>
  #include <fog_vertex>

}`,yi=`// #define PHONG

uniform vec3 litFactor;

uniform float opacity;

uniform vec3 shadeColorFactor;
#ifdef USE_SHADEMULTIPLYTEXTURE
  uniform sampler2D shadeMultiplyTexture;
  uniform mat3 shadeMultiplyTextureUvTransform;
#endif

uniform float shadingShiftFactor;
uniform float shadingToonyFactor;

#ifdef USE_SHADINGSHIFTTEXTURE
  uniform sampler2D shadingShiftTexture;
  uniform mat3 shadingShiftTextureUvTransform;
  uniform float shadingShiftTextureScale;
#endif

uniform float giEqualizationFactor;

uniform vec3 parametricRimColorFactor;
#ifdef USE_RIMMULTIPLYTEXTURE
  uniform sampler2D rimMultiplyTexture;
  uniform mat3 rimMultiplyTextureUvTransform;
#endif
uniform float rimLightingMixFactor;
uniform float parametricRimFresnelPowerFactor;
uniform float parametricRimLiftFactor;

#ifdef USE_MATCAPTEXTURE
  uniform vec3 matcapFactor;
  uniform sampler2D matcapTexture;
  uniform mat3 matcapTextureUvTransform;
#endif

uniform vec3 emissive;
uniform float emissiveIntensity;

uniform vec3 outlineColorFactor;
uniform float outlineLightingMixFactor;

#ifdef USE_UVANIMATIONMASKTEXTURE
  uniform sampler2D uvAnimationMaskTexture;
  uniform mat3 uvAnimationMaskTextureUvTransform;
#endif

uniform float uvAnimationScrollXOffset;
uniform float uvAnimationScrollYOffset;
uniform float uvAnimationRotationPhase;

#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>

// #include <uv_pars_fragment>
#if ( defined( MTOON_USE_UV ) && !defined( MTOON_UVS_VERTEX_ONLY ) )
  varying vec2 vUv;
#endif

// #include <uv2_pars_fragment>
// COMAPT: pre-r151 uses uv2 for lightMap and aoMap
#if THREE_VRM_THREE_REVISION < 151
  #if defined( USE_LIGHTMAP ) || defined( USE_AOMAP )
    varying vec2 vUv2;
  #endif
#endif

#include <map_pars_fragment>

#ifdef USE_MAP
  uniform mat3 mapUvTransform;
#endif

// #include <alphamap_pars_fragment>

#if THREE_VRM_THREE_REVISION >= 132
  #include <alphatest_pars_fragment>
#endif

#include <aomap_pars_fragment>
// #include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>

#ifdef USE_EMISSIVEMAP
  uniform mat3 emissiveMapUvTransform;
#endif

// #include <envmap_common_pars_fragment>
// #include <envmap_pars_fragment>
// #include <cube_uv_reflection_fragment>
#include <fog_pars_fragment>

// #include <bsdfs>
// COMPAT: pre-r151 doesn't have BRDF_Lambert in <common>
#if THREE_VRM_THREE_REVISION < 151
  vec3 BRDF_Lambert( const in vec3 diffuseColor ) {
    return RECIPROCAL_PI * diffuseColor;
  }
#endif

#include <lights_pars_begin>

#if THREE_VRM_THREE_REVISION >= 132
  #include <normal_pars_fragment>
#endif

// #include <lights_phong_pars_fragment>
varying vec3 vViewPosition;

#if THREE_VRM_THREE_REVISION < 132
  #ifndef FLAT_SHADED
    varying vec3 vNormal;
  #endif
#endif

struct MToonMaterial {
  vec3 diffuseColor;
  vec3 shadeColor;
  float shadingShift;
};

float linearstep( float a, float b, float t ) {
  return clamp( ( t - a ) / ( b - a ), 0.0, 1.0 );
}

/**
 * Convert NdotL into toon shading factor using shadingShift and shadingToony
 */
float getShading(
  const in float dotNL,
  const in float shadow,
  const in float shadingShift
) {
  float shading = dotNL;
  shading = shading + shadingShift;
  shading = linearstep( -1.0 + shadingToonyFactor, 1.0 - shadingToonyFactor, shading );
  shading *= shadow;
  return shading;
}

/**
 * Mix diffuseColor and shadeColor using shading factor and light color
 */
vec3 getDiffuse(
  const in MToonMaterial material,
  const in float shading,
  in vec3 lightColor
) {
  #ifdef DEBUG_LITSHADERATE
    return vec3( BRDF_Lambert( shading * lightColor ) );
  #endif

  #if THREE_VRM_THREE_REVISION < 132
    #ifndef PHYSICALLY_CORRECT_LIGHTS
      lightColor *= PI;
    #endif
  #endif

  vec3 col = lightColor * BRDF_Lambert( mix( material.shadeColor, material.diffuseColor, shading ) );

  // The "comment out if you want to PBR absolutely" line
  #ifdef V0_COMPAT_SHADE
    col = min( col, material.diffuseColor );
  #endif

  return col;
}

// COMPAT: pre-r156 uses a struct GeometricContext
#if THREE_VRM_THREE_REVISION >= 157
  void RE_Direct_MToon( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in MToonMaterial material, const in float shadow, inout ReflectedLight reflectedLight ) {
    float dotNL = clamp( dot( geometryNormal, directLight.direction ), -1.0, 1.0 );
    vec3 irradiance = directLight.color;

    // directSpecular will be used for rim lighting, not an actual specular
    reflectedLight.directSpecular += irradiance;

    irradiance *= dotNL;

    float shading = getShading( dotNL, shadow, material.shadingShift );

    // toon shaded diffuse
    reflectedLight.directDiffuse += getDiffuse( material, shading, directLight.color );
  }

  void RE_IndirectDiffuse_MToon( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in MToonMaterial material, inout ReflectedLight reflectedLight ) {
    // indirect diffuse will use diffuseColor, no shadeColor involved
    reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );

    // directSpecular will be used for rim lighting, not an actual specular
    reflectedLight.directSpecular += irradiance;
  }
#else
  void RE_Direct_MToon( const in IncidentLight directLight, const in GeometricContext geometry, const in MToonMaterial material, const in float shadow, inout ReflectedLight reflectedLight ) {
    float dotNL = clamp( dot( geometry.normal, directLight.direction ), -1.0, 1.0 );
    vec3 irradiance = directLight.color;

    #if THREE_VRM_THREE_REVISION < 132
      #ifndef PHYSICALLY_CORRECT_LIGHTS
        irradiance *= PI;
      #endif
    #endif

    // directSpecular will be used for rim lighting, not an actual specular
    reflectedLight.directSpecular += irradiance;

    irradiance *= dotNL;

    float shading = getShading( dotNL, shadow, material.shadingShift );

    // toon shaded diffuse
    reflectedLight.directDiffuse += getDiffuse( material, shading, directLight.color );
  }

  void RE_IndirectDiffuse_MToon( const in vec3 irradiance, const in GeometricContext geometry, const in MToonMaterial material, inout ReflectedLight reflectedLight ) {
    // indirect diffuse will use diffuseColor, no shadeColor involved
    reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );

    // directSpecular will be used for rim lighting, not an actual specular
    reflectedLight.directSpecular += irradiance;
  }
#endif

#define RE_Direct RE_Direct_MToon
#define RE_IndirectDiffuse RE_IndirectDiffuse_MToon
#define Material_LightProbeLOD( material ) (0)

#include <shadowmap_pars_fragment>
// #include <bumpmap_pars_fragment>

// #include <normalmap_pars_fragment>
#ifdef USE_NORMALMAP

  uniform sampler2D normalMap;
  uniform mat3 normalMapUvTransform;
  uniform vec2 normalScale;

#endif

// COMPAT: USE_NORMALMAP_OBJECTSPACE used to be OBJECTSPACE_NORMALMAP in pre-r151
#if defined( USE_NORMALMAP_OBJECTSPACE ) || defined( OBJECTSPACE_NORMALMAP )

  uniform mat3 normalMatrix;

#endif

// COMPAT: USE_NORMALMAP_TANGENTSPACE used to be TANGENTSPACE_NORMALMAP in pre-r151
#if ! defined ( USE_TANGENT ) && ( defined ( USE_NORMALMAP_TANGENTSPACE ) || defined ( TANGENTSPACE_NORMALMAP ) )

  // Per-Pixel Tangent Space Normal Mapping
  // http://hacksoflife.blogspot.ch/2009/11/per-pixel-tangent-space-normal-mapping.html

  // three-vrm specific change: it requires \`uv\` as an input in order to support uv scrolls

  // Temporary compat against shader change @ Three.js r126, r151
  #if THREE_VRM_THREE_REVISION >= 151

    mat3 getTangentFrame( vec3 eye_pos, vec3 surf_norm, vec2 uv ) {

      vec3 q0 = dFdx( eye_pos.xyz );
      vec3 q1 = dFdy( eye_pos.xyz );
      vec2 st0 = dFdx( uv.st );
      vec2 st1 = dFdy( uv.st );

      vec3 N = surf_norm;

      vec3 q1perp = cross( q1, N );
      vec3 q0perp = cross( N, q0 );

      vec3 T = q1perp * st0.x + q0perp * st1.x;
      vec3 B = q1perp * st0.y + q0perp * st1.y;

      float det = max( dot( T, T ), dot( B, B ) );
      float scale = ( det == 0.0 ) ? 0.0 : inversesqrt( det );

      return mat3( T * scale, B * scale, N );

    }

  #elif THREE_VRM_THREE_REVISION >= 126

    vec3 perturbNormal2Arb( vec2 uv, vec3 eye_pos, vec3 surf_norm, vec3 mapN, float faceDirection ) {

      vec3 q0 = vec3( dFdx( eye_pos.x ), dFdx( eye_pos.y ), dFdx( eye_pos.z ) );
      vec3 q1 = vec3( dFdy( eye_pos.x ), dFdy( eye_pos.y ), dFdy( eye_pos.z ) );
      vec2 st0 = dFdx( uv.st );
      vec2 st1 = dFdy( uv.st );

      vec3 N = normalize( surf_norm );

      vec3 q1perp = cross( q1, N );
      vec3 q0perp = cross( N, q0 );

      vec3 T = q1perp * st0.x + q0perp * st1.x;
      vec3 B = q1perp * st0.y + q0perp * st1.y;

      // three-vrm specific change: Workaround for the issue that happens when delta of uv = 0.0
      // TODO: Is this still required? Or shall I make a PR about it?
      if ( length( T ) == 0.0 || length( B ) == 0.0 ) {
        return surf_norm;
      }

      float det = max( dot( T, T ), dot( B, B ) );
      float scale = ( det == 0.0 ) ? 0.0 : faceDirection * inversesqrt( det );

      return normalize( T * ( mapN.x * scale ) + B * ( mapN.y * scale ) + N * mapN.z );

    }

  #else

    vec3 perturbNormal2Arb( vec2 uv, vec3 eye_pos, vec3 surf_norm, vec3 mapN ) {

      // Workaround for Adreno 3XX dFd*( vec3 ) bug. See #9988

      vec3 q0 = vec3( dFdx( eye_pos.x ), dFdx( eye_pos.y ), dFdx( eye_pos.z ) );
      vec3 q1 = vec3( dFdy( eye_pos.x ), dFdy( eye_pos.y ), dFdy( eye_pos.z ) );
      vec2 st0 = dFdx( uv.st );
      vec2 st1 = dFdy( uv.st );

      float scale = sign( st1.t * st0.s - st0.t * st1.s ); // we do not care about the magnitude

      vec3 S = ( q0 * st1.t - q1 * st0.t ) * scale;
      vec3 T = ( - q0 * st1.s + q1 * st0.s ) * scale;

      // three-vrm specific change: Workaround for the issue that happens when delta of uv = 0.0
      // TODO: Is this still required? Or shall I make a PR about it?

      if ( length( S ) == 0.0 || length( T ) == 0.0 ) {
        return surf_norm;
      }

      S = normalize( S );
      T = normalize( T );
      vec3 N = normalize( surf_norm );

      #ifdef DOUBLE_SIDED

        // Workaround for Adreno GPUs gl_FrontFacing bug. See #15850 and #10331

        bool frontFacing = dot( cross( S, T ), N ) > 0.0;

        mapN.xy *= ( float( frontFacing ) * 2.0 - 1.0 );

      #else

        mapN.xy *= ( float( gl_FrontFacing ) * 2.0 - 1.0 );

      #endif

      mat3 tsn = mat3( S, T, N );
      return normalize( tsn * mapN );

    }

  #endif

#endif

// #include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>

// == post correction ==========================================================
void postCorrection() {
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
  #include <fog_fragment>
  #include <premultiplied_alpha_fragment>
  #include <dithering_fragment>
}

// == main procedure ===========================================================
void main() {
  #include <clipping_planes_fragment>

  vec2 uv = vec2(0.5, 0.5);

  #if ( defined( MTOON_USE_UV ) && !defined( MTOON_UVS_VERTEX_ONLY ) )
    uv = vUv;

    float uvAnimMask = 1.0;
    #ifdef USE_UVANIMATIONMASKTEXTURE
      vec2 uvAnimationMaskTextureUv = ( uvAnimationMaskTextureUvTransform * vec3( uv, 1 ) ).xy;
      uvAnimMask = texture2D( uvAnimationMaskTexture, uvAnimationMaskTextureUv ).b;
    #endif

    float uvRotCos = cos( uvAnimationRotationPhase * uvAnimMask );
    float uvRotSin = sin( uvAnimationRotationPhase * uvAnimMask );
    uv = mat2( uvRotCos, -uvRotSin, uvRotSin, uvRotCos ) * ( uv - 0.5 ) + 0.5;
    uv = uv + vec2( uvAnimationScrollXOffset, uvAnimationScrollYOffset ) * uvAnimMask;
  #endif

  #ifdef DEBUG_UV
    gl_FragColor = vec4( 0.0, 0.0, 0.0, 1.0 );
    #if ( defined( MTOON_USE_UV ) && !defined( MTOON_UVS_VERTEX_ONLY ) )
      gl_FragColor = vec4( uv, 0.0, 1.0 );
    #endif
    return;
  #endif

  vec4 diffuseColor = vec4( litFactor, opacity );
  ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
  vec3 totalEmissiveRadiance = emissive * emissiveIntensity;

  #include <logdepthbuf_fragment>

  // #include <map_fragment>
  #ifdef USE_MAP
    vec2 mapUv = ( mapUvTransform * vec3( uv, 1 ) ).xy;
    vec4 sampledDiffuseColor = texture2D( map, mapUv );
    #ifdef DECODE_VIDEO_TEXTURE
      sampledDiffuseColor = vec4( mix( pow( sampledDiffuseColor.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), sampledDiffuseColor.rgb * 0.0773993808, vec3( lessThanEqual( sampledDiffuseColor.rgb, vec3( 0.04045 ) ) ) ), sampledDiffuseColor.w );
    #endif
    diffuseColor *= sampledDiffuseColor;
  #endif

  // #include <color_fragment>
  #if ( defined( USE_COLOR ) && !defined( IGNORE_VERTEX_COLOR ) )
    diffuseColor.rgb *= vColor;
  #endif

  // #include <alphamap_fragment>

  #include <alphatest_fragment>

  // #include <specularmap_fragment>

  // #include <normal_fragment_begin>
  float faceDirection = gl_FrontFacing ? 1.0 : -1.0;

  #ifdef FLAT_SHADED

    vec3 fdx = dFdx( vViewPosition );
    vec3 fdy = dFdy( vViewPosition );
    vec3 normal = normalize( cross( fdx, fdy ) );

  #else

    vec3 normal = normalize( vNormal );

    #ifdef DOUBLE_SIDED

      normal *= faceDirection;

    #endif

  #endif

  #ifdef USE_NORMALMAP

    vec2 normalMapUv = ( normalMapUvTransform * vec3( uv, 1 ) ).xy;

  #endif

  #ifdef USE_NORMALMAP_TANGENTSPACE

    #ifdef USE_TANGENT

      mat3 tbn = mat3( normalize( vTangent ), normalize( vBitangent ), normal );

    #else

      mat3 tbn = getTangentFrame( - vViewPosition, normal, normalMapUv );

    #endif

    #if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )

      tbn[0] *= faceDirection;
      tbn[1] *= faceDirection;

    #endif

  #endif

  #ifdef USE_CLEARCOAT_NORMALMAP

    #ifdef USE_TANGENT

      mat3 tbn2 = mat3( normalize( vTangent ), normalize( vBitangent ), normal );

    #else

      mat3 tbn2 = getTangentFrame( - vViewPosition, normal, vClearcoatNormalMapUv );

    #endif

    #if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )

      tbn2[0] *= faceDirection;
      tbn2[1] *= faceDirection;

    #endif

  #endif

  // non perturbed normal for clearcoat among others

  vec3 nonPerturbedNormal = normal;

  #ifdef OUTLINE
    normal *= -1.0;
  #endif

  // #include <normal_fragment_maps>

  // COMPAT: USE_NORMALMAP_OBJECTSPACE used to be OBJECTSPACE_NORMALMAP in pre-r151
  #if defined( USE_NORMALMAP_OBJECTSPACE ) || defined( OBJECTSPACE_NORMALMAP )

    normal = texture2D( normalMap, normalMapUv ).xyz * 2.0 - 1.0; // overrides both flatShading and attribute normals

    #ifdef FLIP_SIDED

      normal = - normal;

    #endif

    #ifdef DOUBLE_SIDED

      // Temporary compat against shader change @ Three.js r126
      // See: #21205, #21307, #21299
      #if THREE_VRM_THREE_REVISION >= 126

        normal = normal * faceDirection;

      #else

        normal = normal * ( float( gl_FrontFacing ) * 2.0 - 1.0 );

      #endif

    #endif

    normal = normalize( normalMatrix * normal );

  // COMPAT: USE_NORMALMAP_TANGENTSPACE used to be TANGENTSPACE_NORMALMAP in pre-r151
  #elif defined( USE_NORMALMAP_TANGENTSPACE ) || defined( TANGENTSPACE_NORMALMAP )

    vec3 mapN = texture2D( normalMap, normalMapUv ).xyz * 2.0 - 1.0;
    mapN.xy *= normalScale;

    // COMPAT: pre-r151
    #if THREE_VRM_THREE_REVISION >= 151 || defined( USE_TANGENT )

      normal = normalize( tbn * mapN );

    #else

      // pre-r126
      #if THREE_VRM_THREE_REVISION >= 126

        normal = perturbNormal2Arb( uv, -vViewPosition, normal, mapN, faceDirection );

      #else

        normal = perturbNormal2Arb( uv, -vViewPosition, normal, mapN );

      #endif

    #endif

  #endif

  // #include <emissivemap_fragment>
  #ifdef USE_EMISSIVEMAP
    vec2 emissiveMapUv = ( emissiveMapUvTransform * vec3( uv, 1 ) ).xy;
    totalEmissiveRadiance *= texture2D( emissiveMap, emissiveMapUv ).rgb;
  #endif

  #ifdef DEBUG_NORMAL
    gl_FragColor = vec4( 0.5 + 0.5 * normal, 1.0 );
    return;
  #endif

  // -- MToon: lighting --------------------------------------------------------
  // accumulation
  // #include <lights_phong_fragment>
  MToonMaterial material;

  material.diffuseColor = diffuseColor.rgb;

  material.shadeColor = shadeColorFactor;
  #ifdef USE_SHADEMULTIPLYTEXTURE
    vec2 shadeMultiplyTextureUv = ( shadeMultiplyTextureUvTransform * vec3( uv, 1 ) ).xy;
    material.shadeColor *= texture2D( shadeMultiplyTexture, shadeMultiplyTextureUv ).rgb;
  #endif

  #if ( defined( USE_COLOR ) && !defined( IGNORE_VERTEX_COLOR ) )
    material.shadeColor.rgb *= vColor;
  #endif

  material.shadingShift = shadingShiftFactor;
  #ifdef USE_SHADINGSHIFTTEXTURE
    vec2 shadingShiftTextureUv = ( shadingShiftTextureUvTransform * vec3( uv, 1 ) ).xy;
    material.shadingShift += texture2D( shadingShiftTexture, shadingShiftTextureUv ).r * shadingShiftTextureScale;
  #endif

  // #include <lights_fragment_begin>

  // MToon Specific changes:
  // Since we want to take shadows into account of shading instead of irradiance,
  // we had to modify the codes that multiplies the results of shadowmap into color of direct lights.

  // COMPAT: pre-r156 uses a struct GeometricContext
  #if THREE_VRM_THREE_REVISION >= 157
    vec3 geometryPosition = - vViewPosition;
    vec3 geometryNormal = normal;
    vec3 geometryViewDir = ( isOrthographic ) ? vec3( 0, 0, 1 ) : normalize( vViewPosition );

    vec3 geometryClearcoatNormal;

    #ifdef USE_CLEARCOAT

      geometryClearcoatNormal = clearcoatNormal;

    #endif
  #else
    GeometricContext geometry;

    geometry.position = - vViewPosition;
    geometry.normal = normal;
    geometry.viewDir = ( isOrthographic ) ? vec3( 0, 0, 1 ) : normalize( vViewPosition );

    #ifdef USE_CLEARCOAT

      geometry.clearcoatNormal = clearcoatNormal;

    #endif
  #endif

  IncidentLight directLight;

  // since these variables will be used in unrolled loop, we have to define in prior
  float shadow;

  #if ( NUM_POINT_LIGHTS > 0 ) && defined( RE_Direct )

    PointLight pointLight;
    #if defined( USE_SHADOWMAP ) && NUM_POINT_LIGHT_SHADOWS > 0
    PointLightShadow pointLightShadow;
    #endif

    #pragma unroll_loop_start
    for ( int i = 0; i < NUM_POINT_LIGHTS; i ++ ) {

      pointLight = pointLights[ i ];

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        getPointLightInfo( pointLight, geometryPosition, directLight );
      #elif THREE_VRM_THREE_REVISION >= 132
        getPointLightInfo( pointLight, geometry, directLight );
      #else
        getPointDirectLightIrradiance( pointLight, geometry, directLight );
      #endif

      shadow = 1.0;
      #if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_POINT_LIGHT_SHADOWS )
      pointLightShadow = pointLightShadows[ i ];
      // COMPAT: pre-r166
      // r166 introduced shadowIntensity
      #if THREE_VRM_THREE_REVISION >= 166
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getPointShadow( pointShadowMap[ i ], pointLightShadow.shadowMapSize, pointLightShadow.shadowIntensity, pointLightShadow.shadowBias, pointLightShadow.shadowRadius, vPointShadowCoord[ i ], pointLightShadow.shadowCameraNear, pointLightShadow.shadowCameraFar ) : 1.0;
      #else
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getPointShadow( pointShadowMap[ i ], pointLightShadow.shadowMapSize, pointLightShadow.shadowBias, pointLightShadow.shadowRadius, vPointShadowCoord[ i ], pointLightShadow.shadowCameraNear, pointLightShadow.shadowCameraFar ) : 1.0;
      #endif
      #endif

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, shadow, reflectedLight );
      #else
        RE_Direct( directLight, geometry, material, shadow, reflectedLight );
      #endif

    }
    #pragma unroll_loop_end

  #endif

  #if ( NUM_SPOT_LIGHTS > 0 ) && defined( RE_Direct )

    SpotLight spotLight;
    #if defined( USE_SHADOWMAP ) && NUM_SPOT_LIGHT_SHADOWS > 0
    SpotLightShadow spotLightShadow;
    #endif

    #pragma unroll_loop_start
    for ( int i = 0; i < NUM_SPOT_LIGHTS; i ++ ) {

      spotLight = spotLights[ i ];

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        getSpotLightInfo( spotLight, geometryPosition, directLight );
      #elif THREE_VRM_THREE_REVISION >= 132
        getSpotLightInfo( spotLight, geometry, directLight );
      #else
        getSpotDirectLightIrradiance( spotLight, geometry, directLight );
      #endif

      shadow = 1.0;
      #if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
      spotLightShadow = spotLightShadows[ i ];
      // COMPAT: pre-r166
      // r166 introduced shadowIntensity
      #if THREE_VRM_THREE_REVISION >= 166
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getShadow( spotShadowMap[ i ], spotLightShadow.shadowMapSize, spotLightShadow.shadowIntensity, spotLightShadow.shadowBias, spotLightShadow.shadowRadius, vSpotShadowCoord[ i ] ) : 1.0;
      #else
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getShadow( spotShadowMap[ i ], spotLightShadow.shadowMapSize, spotLightShadow.shadowBias, spotLightShadow.shadowRadius, vSpotShadowCoord[ i ] ) : 1.0;
      #endif
      #endif

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, shadow, reflectedLight );
      #else
        RE_Direct( directLight, geometry, material, shadow, reflectedLight );
      #endif

    }
    #pragma unroll_loop_end

  #endif

  #if ( NUM_DIR_LIGHTS > 0 ) && defined( RE_Direct )

    DirectionalLight directionalLight;
    #if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
    DirectionalLightShadow directionalLightShadow;
    #endif

    #pragma unroll_loop_start
    for ( int i = 0; i < NUM_DIR_LIGHTS; i ++ ) {

      directionalLight = directionalLights[ i ];

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        getDirectionalLightInfo( directionalLight, directLight );
      #elif THREE_VRM_THREE_REVISION >= 132
        getDirectionalLightInfo( directionalLight, geometry, directLight );
      #else
        getDirectionalDirectLightIrradiance( directionalLight, geometry, directLight );
      #endif

      shadow = 1.0;
      #if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_DIR_LIGHT_SHADOWS )
      directionalLightShadow = directionalLightShadows[ i ];
      // COMPAT: pre-r166
      // r166 introduced shadowIntensity
      #if THREE_VRM_THREE_REVISION >= 166
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getShadow( directionalShadowMap[ i ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowIntensity, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
      #else
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getShadow( directionalShadowMap[ i ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
      #endif
      #endif

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, shadow, reflectedLight );
      #else
        RE_Direct( directLight, geometry, material, shadow, reflectedLight );
      #endif

    }
    #pragma unroll_loop_end

  #endif

  // #if ( NUM_RECT_AREA_LIGHTS > 0 ) && defined( RE_Direct_RectArea )

  //   RectAreaLight rectAreaLight;

  //   #pragma unroll_loop_start
  //   for ( int i = 0; i < NUM_RECT_AREA_LIGHTS; i ++ ) {

  //     rectAreaLight = rectAreaLights[ i ];
  //     RE_Direct_RectArea( rectAreaLight, geometry, material, reflectedLight );

  //   }
  //   #pragma unroll_loop_end

  // #endif

  #if defined( RE_IndirectDiffuse )

    vec3 iblIrradiance = vec3( 0.0 );

    vec3 irradiance = getAmbientLightIrradiance( ambientLightColor );

    // COMPAT: pre-r156 uses a struct GeometricContext
    // COMPAT: pre-r156 doesn't have a define USE_LIGHT_PROBES
    #if THREE_VRM_THREE_REVISION >= 157
      #if defined( USE_LIGHT_PROBES )
        irradiance += getLightProbeIrradiance( lightProbe, geometryNormal );
      #endif
    #elif THREE_VRM_THREE_REVISION >= 133
      irradiance += getLightProbeIrradiance( lightProbe, geometry.normal );
    #else
      irradiance += getLightProbeIrradiance( lightProbe, geometry );
    #endif

    #if ( NUM_HEMI_LIGHTS > 0 )

      #pragma unroll_loop_start
      for ( int i = 0; i < NUM_HEMI_LIGHTS; i ++ ) {

        // COMPAT: pre-r156 uses a struct GeometricContext
        #if THREE_VRM_THREE_REVISION >= 157
          irradiance += getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal );
        #elif THREE_VRM_THREE_REVISION >= 133
          irradiance += getHemisphereLightIrradiance( hemisphereLights[ i ], geometry.normal );
        #else
          irradiance += getHemisphereLightIrradiance( hemisphereLights[ i ], geometry );
        #endif

      }
      #pragma unroll_loop_end

    #endif

  #endif

  // #if defined( RE_IndirectSpecular )

  //   vec3 radiance = vec3( 0.0 );
  //   vec3 clearcoatRadiance = vec3( 0.0 );

  // #endif

  #include <lights_fragment_maps>
  #include <lights_fragment_end>

  // modulation
  #include <aomap_fragment>

  vec3 col = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse;

  #ifdef DEBUG_LITSHADERATE
    gl_FragColor = vec4( col, diffuseColor.a );
    postCorrection();
    return;
  #endif

  // -- MToon: rim lighting -----------------------------------------
  vec3 viewDir = normalize( vViewPosition );

  #ifndef PHYSICALLY_CORRECT_LIGHTS
    reflectedLight.directSpecular /= PI;
  #endif
  vec3 rimMix = mix( vec3( 1.0 ), reflectedLight.directSpecular, 1.0 );

  vec3 rim = parametricRimColorFactor * pow( saturate( 1.0 - dot( viewDir, normal ) + parametricRimLiftFactor ), parametricRimFresnelPowerFactor );

  #ifdef USE_MATCAPTEXTURE
    {
      vec3 x = normalize( vec3( viewDir.z, 0.0, -viewDir.x ) );
      vec3 y = cross( viewDir, x ); // guaranteed to be normalized
      vec2 sphereUv = 0.5 + 0.5 * vec2( dot( x, normal ), -dot( y, normal ) );
      sphereUv = ( matcapTextureUvTransform * vec3( sphereUv, 1 ) ).xy;
      vec3 matcap = texture2D( matcapTexture, sphereUv ).rgb;
      rim += matcapFactor * matcap;
    }
  #endif

  #ifdef USE_RIMMULTIPLYTEXTURE
    vec2 rimMultiplyTextureUv = ( rimMultiplyTextureUvTransform * vec3( uv, 1 ) ).xy;
    rim *= texture2D( rimMultiplyTexture, rimMultiplyTextureUv ).rgb;
  #endif

  col += rimMix * rim;

  // -- MToon: Emission --------------------------------------------------------
  col += totalEmissiveRadiance;

  // #include <envmap_fragment>

  // -- Almost done! -----------------------------------------------------------
  #if defined( OUTLINE )
    col = outlineColorFactor.rgb * mix( vec3( 1.0 ), col, outlineLightingMixFactor );
  #endif

  #ifdef OPAQUE
    diffuseColor.a = 1.0;
  #endif

  gl_FragColor = vec4( col, diffuseColor.a );
  postCorrection();
}
`,wi={None:"none",Normal:"normal",LitShadeRate:"litShadeRate",UV:"uv"},Mt={None:"none",WorldCoordinates:"worldCoordinates",ScreenCoordinates:"screenCoordinates"},Si={3e3:"",3001:"srgb"};function Rt(l){return parseInt(o.REVISION,10)>=152?l.colorSpace:Si[l.encoding]}var K=class extends o.ShaderMaterial{get color(){return this.uniforms.litFactor.value}set color(e){this.uniforms.litFactor.value=e}get map(){return this.uniforms.map.value}set map(e){this.uniforms.map.value=e}get normalMap(){return this.uniforms.normalMap.value}set normalMap(e){this.uniforms.normalMap.value=e}get normalScale(){return this.uniforms.normalScale.value}set normalScale(e){this.uniforms.normalScale.value=e}get emissive(){return this.uniforms.emissive.value}set emissive(e){this.uniforms.emissive.value=e}get emissiveIntensity(){return this.uniforms.emissiveIntensity.value}set emissiveIntensity(e){this.uniforms.emissiveIntensity.value=e}get emissiveMap(){return this.uniforms.emissiveMap.value}set emissiveMap(e){this.uniforms.emissiveMap.value=e}get shadeColorFactor(){return this.uniforms.shadeColorFactor.value}set shadeColorFactor(e){this.uniforms.shadeColorFactor.value=e}get shadeMultiplyTexture(){return this.uniforms.shadeMultiplyTexture.value}set shadeMultiplyTexture(e){this.uniforms.shadeMultiplyTexture.value=e}get shadingShiftFactor(){return this.uniforms.shadingShiftFactor.value}set shadingShiftFactor(e){this.uniforms.shadingShiftFactor.value=e}get shadingShiftTexture(){return this.uniforms.shadingShiftTexture.value}set shadingShiftTexture(e){this.uniforms.shadingShiftTexture.value=e}get shadingShiftTextureScale(){return this.uniforms.shadingShiftTextureScale.value}set shadingShiftTextureScale(e){this.uniforms.shadingShiftTextureScale.value=e}get shadingToonyFactor(){return this.uniforms.shadingToonyFactor.value}set shadingToonyFactor(e){this.uniforms.shadingToonyFactor.value=e}get giEqualizationFactor(){return this.uniforms.giEqualizationFactor.value}set giEqualizationFactor(e){this.uniforms.giEqualizationFactor.value=e}get matcapFactor(){return this.uniforms.matcapFactor.value}set matcapFactor(e){this.uniforms.matcapFactor.value=e}get matcapTexture(){return this.uniforms.matcapTexture.value}set matcapTexture(e){this.uniforms.matcapTexture.value=e}get parametricRimColorFactor(){return this.uniforms.parametricRimColorFactor.value}set parametricRimColorFactor(e){this.uniforms.parametricRimColorFactor.value=e}get rimMultiplyTexture(){return this.uniforms.rimMultiplyTexture.value}set rimMultiplyTexture(e){this.uniforms.rimMultiplyTexture.value=e}get rimLightingMixFactor(){return this.uniforms.rimLightingMixFactor.value}set rimLightingMixFactor(e){this.uniforms.rimLightingMixFactor.value=e}get parametricRimFresnelPowerFactor(){return this.uniforms.parametricRimFresnelPowerFactor.value}set parametricRimFresnelPowerFactor(e){this.uniforms.parametricRimFresnelPowerFactor.value=e}get parametricRimLiftFactor(){return this.uniforms.parametricRimLiftFactor.value}set parametricRimLiftFactor(e){this.uniforms.parametricRimLiftFactor.value=e}get outlineWidthMultiplyTexture(){return this.uniforms.outlineWidthMultiplyTexture.value}set outlineWidthMultiplyTexture(e){this.uniforms.outlineWidthMultiplyTexture.value=e}get outlineWidthFactor(){return this.uniforms.outlineWidthFactor.value}set outlineWidthFactor(e){this.uniforms.outlineWidthFactor.value=e}get outlineColorFactor(){return this.uniforms.outlineColorFactor.value}set outlineColorFactor(e){this.uniforms.outlineColorFactor.value=e}get outlineLightingMixFactor(){return this.uniforms.outlineLightingMixFactor.value}set outlineLightingMixFactor(e){this.uniforms.outlineLightingMixFactor.value=e}get uvAnimationMaskTexture(){return this.uniforms.uvAnimationMaskTexture.value}set uvAnimationMaskTexture(e){this.uniforms.uvAnimationMaskTexture.value=e}get uvAnimationScrollXOffset(){return this.uniforms.uvAnimationScrollXOffset.value}set uvAnimationScrollXOffset(e){this.uniforms.uvAnimationScrollXOffset.value=e}get uvAnimationScrollYOffset(){return this.uniforms.uvAnimationScrollYOffset.value}set uvAnimationScrollYOffset(e){this.uniforms.uvAnimationScrollYOffset.value=e}get uvAnimationRotationPhase(){return this.uniforms.uvAnimationRotationPhase.value}set uvAnimationRotationPhase(e){this.uniforms.uvAnimationRotationPhase.value=e}get ignoreVertexColor(){return this._ignoreVertexColor}set ignoreVertexColor(e){this._ignoreVertexColor=e,this.needsUpdate=!0}get v0CompatShade(){return this._v0CompatShade}set v0CompatShade(e){this._v0CompatShade=e,this.needsUpdate=!0}get debugMode(){return this._debugMode}set debugMode(e){this._debugMode=e,this.needsUpdate=!0}get outlineWidthMode(){return this._outlineWidthMode}set outlineWidthMode(e){this._outlineWidthMode=e,this.needsUpdate=!0}get isOutline(){return this._isOutline}set isOutline(e){this._isOutline=e,this.needsUpdate=!0}get isMToonMaterial(){return!0}constructor(e={}){var t;super({vertexShader:xi,fragmentShader:yi}),this.uvAnimationScrollXSpeedFactor=0,this.uvAnimationScrollYSpeedFactor=0,this.uvAnimationRotationSpeedFactor=0,this.fog=!0,this.normalMapType=o.TangentSpaceNormalMap,this._ignoreVertexColor=!0,this._v0CompatShade=!1,this._debugMode=wi.None,this._outlineWidthMode=Mt.None,this._isOutline=!1,e.transparentWithZWrite&&(e.depthWrite=!0),delete e.transparentWithZWrite,e.fog=!0,e.lights=!0,e.clipping=!0,parseInt(o.REVISION,10)<129&&(e.skinning=e.skinning||!1),parseInt(o.REVISION,10)<131&&(e.morphTargets=e.morphTargets||!1,e.morphNormals=e.morphNormals||!1),this.uniforms=o.UniformsUtils.merge([o.UniformsLib.common,o.UniformsLib.normalmap,o.UniformsLib.emissivemap,o.UniformsLib.fog,o.UniformsLib.lights,{litFactor:{value:new o.Color(1,1,1)},mapUvTransform:{value:new o.Matrix3},colorAlpha:{value:1},normalMapUvTransform:{value:new o.Matrix3},shadeColorFactor:{value:new o.Color(0,0,0)},shadeMultiplyTexture:{value:null},shadeMultiplyTextureUvTransform:{value:new o.Matrix3},shadingShiftFactor:{value:0},shadingShiftTexture:{value:null},shadingShiftTextureUvTransform:{value:new o.Matrix3},shadingShiftTextureScale:{value:1},shadingToonyFactor:{value:.9},giEqualizationFactor:{value:.9},matcapFactor:{value:new o.Color(1,1,1)},matcapTexture:{value:null},matcapTextureUvTransform:{value:new o.Matrix3},parametricRimColorFactor:{value:new o.Color(0,0,0)},rimMultiplyTexture:{value:null},rimMultiplyTextureUvTransform:{value:new o.Matrix3},rimLightingMixFactor:{value:1},parametricRimFresnelPowerFactor:{value:5},parametricRimLiftFactor:{value:0},emissive:{value:new o.Color(0,0,0)},emissiveIntensity:{value:1},emissiveMapUvTransform:{value:new o.Matrix3},outlineWidthMultiplyTexture:{value:null},outlineWidthMultiplyTextureUvTransform:{value:new o.Matrix3},outlineWidthFactor:{value:0},outlineColorFactor:{value:new o.Color(0,0,0)},outlineLightingMixFactor:{value:1},uvAnimationMaskTexture:{value:null},uvAnimationMaskTextureUvTransform:{value:new o.Matrix3},uvAnimationScrollXOffset:{value:0},uvAnimationScrollYOffset:{value:0},uvAnimationRotationPhase:{value:0}},(t=e.uniforms)!==null&&t!==void 0?t:{}]),this.setValues(e),this._uploadUniformsWorkaround(),this.customProgramCacheKey=()=>[...Object.entries(this._generateDefines()).map(([n,i])=>`${n}:${i}`),this.matcapTexture?`matcapTextureColorSpace:${Rt(this.matcapTexture)}`:"",this.shadeMultiplyTexture?`shadeMultiplyTextureColorSpace:${Rt(this.shadeMultiplyTexture)}`:"",this.rimMultiplyTexture?`rimMultiplyTextureColorSpace:${Rt(this.rimMultiplyTexture)}`:""].join(","),this.onBeforeCompile=n=>{let i=parseInt(o.REVISION,10),r=Object.entries(Object.assign(Object.assign({},this._generateDefines()),this.defines)).filter(([s,a])=>!!a).map(([s,a])=>`#define ${s} ${a}`).join(`
`)+`
`;n.vertexShader=r+n.vertexShader,n.fragmentShader=r+n.fragmentShader,i<154&&(n.fragmentShader=n.fragmentShader.replace("#include <colorspace_fragment>","#include <encodings_fragment>")),i<132&&(n.fragmentShader=n.fragmentShader.replace("#include <normal_pars_fragment>",""),n.fragmentShader=n.fragmentShader.replace("#include <alphatest_pars_fragment>",""))}}update(e){this._uploadUniformsWorkaround(),this._updateUVAnimation(e)}copy(e){return super.copy(e),this.map=e.map,this.normalMap=e.normalMap,this.emissiveMap=e.emissiveMap,this.shadeMultiplyTexture=e.shadeMultiplyTexture,this.shadingShiftTexture=e.shadingShiftTexture,this.matcapTexture=e.matcapTexture,this.rimMultiplyTexture=e.rimMultiplyTexture,this.outlineWidthMultiplyTexture=e.outlineWidthMultiplyTexture,this.uvAnimationMaskTexture=e.uvAnimationMaskTexture,this.normalMapType=e.normalMapType,this.uvAnimationScrollXSpeedFactor=e.uvAnimationScrollXSpeedFactor,this.uvAnimationScrollYSpeedFactor=e.uvAnimationScrollYSpeedFactor,this.uvAnimationRotationSpeedFactor=e.uvAnimationRotationSpeedFactor,this.ignoreVertexColor=e.ignoreVertexColor,this.v0CompatShade=e.v0CompatShade,this.debugMode=e.debugMode,this.outlineWidthMode=e.outlineWidthMode,this.isOutline=e.isOutline,this.needsUpdate=!0,this}_updateUVAnimation(e){this.uniforms.uvAnimationScrollXOffset.value+=e*this.uvAnimationScrollXSpeedFactor,this.uniforms.uvAnimationScrollYOffset.value+=e*this.uvAnimationScrollYSpeedFactor,this.uniforms.uvAnimationRotationPhase.value+=e*this.uvAnimationRotationSpeedFactor,this.uniformsNeedUpdate=!0}_uploadUniformsWorkaround(){this.uniforms.opacity.value=this.opacity,this._updateTextureMatrix(this.uniforms.map,this.uniforms.mapUvTransform),this._updateTextureMatrix(this.uniforms.normalMap,this.uniforms.normalMapUvTransform),this._updateTextureMatrix(this.uniforms.emissiveMap,this.uniforms.emissiveMapUvTransform),this._updateTextureMatrix(this.uniforms.shadeMultiplyTexture,this.uniforms.shadeMultiplyTextureUvTransform),this._updateTextureMatrix(this.uniforms.shadingShiftTexture,this.uniforms.shadingShiftTextureUvTransform),this._updateTextureMatrix(this.uniforms.matcapTexture,this.uniforms.matcapTextureUvTransform),this._updateTextureMatrix(this.uniforms.rimMultiplyTexture,this.uniforms.rimMultiplyTextureUvTransform),this._updateTextureMatrix(this.uniforms.outlineWidthMultiplyTexture,this.uniforms.outlineWidthMultiplyTextureUvTransform),this._updateTextureMatrix(this.uniforms.uvAnimationMaskTexture,this.uniforms.uvAnimationMaskTextureUvTransform),parseInt(o.REVISION,10)>=132&&(this.uniforms.alphaTest.value=this.alphaTest),this.uniformsNeedUpdate=!0}_generateDefines(){let e=parseInt(o.REVISION,10),t=this.outlineWidthMultiplyTexture!==null,n=this.map!==null||this.normalMap!==null||this.emissiveMap!==null||this.shadeMultiplyTexture!==null||this.shadingShiftTexture!==null||this.rimMultiplyTexture!==null||this.uvAnimationMaskTexture!==null;return{THREE_VRM_THREE_REVISION:e,OUTLINE:this._isOutline,MTOON_USE_UV:t||n,MTOON_UVS_VERTEX_ONLY:t&&!n,V0_COMPAT_SHADE:this._v0CompatShade,USE_SHADEMULTIPLYTEXTURE:this.shadeMultiplyTexture!==null,USE_SHADINGSHIFTTEXTURE:this.shadingShiftTexture!==null,USE_MATCAPTEXTURE:this.matcapTexture!==null,USE_RIMMULTIPLYTEXTURE:this.rimMultiplyTexture!==null,USE_OUTLINEWIDTHMULTIPLYTEXTURE:this._isOutline&&this.outlineWidthMultiplyTexture!==null,USE_UVANIMATIONMASKTEXTURE:this.uvAnimationMaskTexture!==null,IGNORE_VERTEX_COLOR:this._ignoreVertexColor===!0,DEBUG_NORMAL:this._debugMode==="normal",DEBUG_LITSHADERATE:this._debugMode==="litShadeRate",DEBUG_UV:this._debugMode==="uv",OUTLINE_WIDTH_WORLD:this._isOutline&&this._outlineWidthMode===Mt.WorldCoordinates,OUTLINE_WIDTH_SCREEN:this._isOutline&&this._outlineWidthMode===Mt.ScreenCoordinates}}_updateTextureMatrix(e,t){e.value&&(e.value.matrixAutoUpdate&&e.value.updateMatrix(),t.value.copy(e.value.matrix))}},Ai={"":3e3,srgb:3001};function Pi(l,e){parseInt(o.REVISION,10)>=152?l.colorSpace=e:l.encoding=Ai[e]}var Lt=class{get pending(){return Promise.all(this._pendings)}constructor(e,t){this._parser=e,this._materialParams=t,this._pendings=[]}assignPrimitive(e,t){t!=null&&(this._materialParams[e]=t)}assignColor(e,t,n){t!=null&&(this._materialParams[e]=new o.Color().fromArray(t),n&&this._materialParams[e].convertSRGBToLinear())}assignTexture(e,t,n){return B(this,void 0,void 0,function*(){let i=B(this,void 0,void 0,function*(){t!=null&&(yield this._parser.assignTexture(this._materialParams,e,t),n&&Pi(this._materialParams[e],"srgb"))});return this._pendings.push(i),i})}assignTextureByIndex(e,t,n){return B(this,void 0,void 0,function*(){return this.assignTexture(e,t!=null?{index:t}:void 0,n)})}},Li=new Set(["1.0","1.0-beta"]),Le=class l{get name(){return l.EXTENSION_NAME}constructor(e,t={}){var n,i,r;this.parser=e,this.renderOrderOffset=(n=t.renderOrderOffset)!==null&&n!==void 0?n:0,this.v0CompatShade=(i=t.v0CompatShade)!==null&&i!==void 0?i:!1,this.debugMode=(r=t.debugMode)!==null&&r!==void 0?r:"none",this._mToonMaterialSet=new Set}beforeRoot(){return B(this,void 0,void 0,function*(){this._removeUnlitExtensionIfMToonExists()})}afterRoot(e){return B(this,void 0,void 0,function*(){e.userData.vrmMToonMaterials=Array.from(this._mToonMaterialSet)})}getMaterialType(e){return this._getMToonExtension(e)?K:null}extendMaterialParams(e,t){let n=this._getMToonExtension(e);return n?this._extendMaterialParams(n,t):null}loadMesh(e){var t;return B(this,void 0,void 0,function*(){let n=this.parser,r=(t=n.json.meshes)===null||t===void 0?void 0:t[e];if(r==null)throw new Error(`MToonMaterialLoaderPlugin: Attempt to use meshes[${e}] of glTF but the mesh doesn't exist`);let s=r.primitives,a=yield n.loadMesh(e);if(s.length===1){let u=a,d=s[0].material;d!=null&&this._setupPrimitive(u,d)}else{let u=a;for(let d=0;d<s.length;d++){let c=u.children[d],h=s[d].material;h!=null&&this._setupPrimitive(c,h)}}return a})}_removeUnlitExtensionIfMToonExists(){let n=this.parser.json.materials;n?.map((i,r)=>{var s;this._getMToonExtension(r)&&(!((s=i.extensions)===null||s===void 0)&&s.KHR_materials_unlit)&&delete i.extensions.KHR_materials_unlit})}_getMToonExtension(e){var t,n;let s=(t=this.parser.json.materials)===null||t===void 0?void 0:t[e];if(s==null){console.warn(`MToonMaterialLoaderPlugin: Attempt to use materials[${e}] of glTF but the material doesn't exist`);return}let a=(n=s.extensions)===null||n===void 0?void 0:n[l.EXTENSION_NAME];if(a==null)return;let u=a.specVersion;if(!Li.has(u)){console.warn(`MToonMaterialLoaderPlugin: Unknown ${l.EXTENSION_NAME} specVersion "${u}"`);return}return a}_extendMaterialParams(e,t){var n;return B(this,void 0,void 0,function*(){delete t.metalness,delete t.roughness;let i=new Lt(this.parser,t);i.assignPrimitive("transparentWithZWrite",e.transparentWithZWrite),i.assignColor("shadeColorFactor",e.shadeColorFactor),i.assignTexture("shadeMultiplyTexture",e.shadeMultiplyTexture,!0),i.assignPrimitive("shadingShiftFactor",e.shadingShiftFactor),i.assignTexture("shadingShiftTexture",e.shadingShiftTexture,!0),i.assignPrimitive("shadingShiftTextureScale",(n=e.shadingShiftTexture)===null||n===void 0?void 0:n.scale),i.assignPrimitive("shadingToonyFactor",e.shadingToonyFactor),i.assignPrimitive("giEqualizationFactor",e.giEqualizationFactor),i.assignColor("matcapFactor",e.matcapFactor),i.assignTexture("matcapTexture",e.matcapTexture,!0),i.assignColor("parametricRimColorFactor",e.parametricRimColorFactor),i.assignTexture("rimMultiplyTexture",e.rimMultiplyTexture,!0),i.assignPrimitive("rimLightingMixFactor",e.rimLightingMixFactor),i.assignPrimitive("parametricRimFresnelPowerFactor",e.parametricRimFresnelPowerFactor),i.assignPrimitive("parametricRimLiftFactor",e.parametricRimLiftFactor),i.assignPrimitive("outlineWidthMode",e.outlineWidthMode),i.assignPrimitive("outlineWidthFactor",e.outlineWidthFactor),i.assignTexture("outlineWidthMultiplyTexture",e.outlineWidthMultiplyTexture,!1),i.assignColor("outlineColorFactor",e.outlineColorFactor),i.assignPrimitive("outlineLightingMixFactor",e.outlineLightingMixFactor),i.assignTexture("uvAnimationMaskTexture",e.uvAnimationMaskTexture,!1),i.assignPrimitive("uvAnimationScrollXSpeedFactor",e.uvAnimationScrollXSpeedFactor),i.assignPrimitive("uvAnimationScrollYSpeedFactor",e.uvAnimationScrollYSpeedFactor),i.assignPrimitive("uvAnimationRotationSpeedFactor",e.uvAnimationRotationSpeedFactor),i.assignPrimitive("v0CompatShade",this.v0CompatShade),i.assignPrimitive("debugMode",this.debugMode),yield i.pending})}_setupPrimitive(e,t){let n=this._getMToonExtension(t);if(n){let i=this._parseRenderOrder(n);e.renderOrder=i+this.renderOrderOffset,this._generateOutline(e),this._addToMaterialSet(e);return}}_generateOutline(e){let t=e.material;if(!(t instanceof K)||t.outlineWidthMode==="none"||t.outlineWidthFactor<=0)return;e.material=[t];let n=t.clone();n.name+=" (Outline)",n.isOutline=!0,n.side=o.BackSide,e.material.push(n);let i=e.geometry,r=i.index?i.index.count:i.attributes.position.count/3;i.addGroup(0,r,0),i.addGroup(0,r,1)}_addToMaterialSet(e){let t=e.material,n=new Set;Array.isArray(t)?t.forEach(i=>n.add(i)):n.add(t);for(let i of n)i instanceof K&&this._mToonMaterialSet.add(i)}_parseRenderOrder(e){var t;return(e.transparentWithZWrite?0:19)+((t=e.renderQueueOffsetNumber)!==null&&t!==void 0?t:0)}};Le.EXTENSION_NAME="VRMC_materials_mtoon";function Ii(l,e,t,n){function i(r){return r instanceof t?r:new t(function(s){s(r)})}return new(t||(t=Promise))(function(r,s){function a(c){try{d(n.next(c))}catch(h){s(h)}}function u(c){try{d(n.throw(c))}catch(h){s(h)}}function d(c){c.done?r(c.value):i(c.value).then(a,u)}d((n=n.apply(l,e||[])).next())})}var Ie=class l{get name(){return l.EXTENSION_NAME}constructor(e){this.parser=e}extendMaterialParams(e,t){return Ii(this,void 0,void 0,function*(){let n=this._getHDREmissiveMultiplierExtension(e);if(n==null)return;console.warn("VRMMaterialsHDREmissiveMultiplierLoaderPlugin: `VRMC_materials_hdr_emissiveMultiplier` is archived. Use `KHR_materials_emissive_strength` instead.");let i=n.emissiveMultiplier;t.emissiveIntensity=i})}_getHDREmissiveMultiplierExtension(e){var t,n;let s=(t=this.parser.json.materials)===null||t===void 0?void 0:t[e];if(s==null){console.warn(`VRMMaterialsHDREmissiveMultiplierLoaderPlugin: Attempt to use materials[${e}] of glTF but the material doesn't exist`);return}let a=(n=s.extensions)===null||n===void 0?void 0:n[l.EXTENSION_NAME];if(a!=null)return a}};Ie.EXTENSION_NAME="VRMC_materials_hdr_emissiveMultiplier";function Hi(l,e,t,n){function i(r){return r instanceof t?r:new t(function(s){s(r)})}return new(t||(t=Promise))(function(r,s){function a(c){try{d(n.next(c))}catch(h){s(h)}}function u(c){try{d(n.throw(c))}catch(h){s(h)}}function d(c){c.done?r(c.value):i(c.value).then(a,u)}d((n=n.apply(l,e||[])).next())})}function z(l){return Math.pow(l,2.2)}var It=class{get name(){return"VRMMaterialsV0CompatPlugin"}constructor(e){var t;this.parser=e,this._renderQueueMapTransparent=new Map,this._renderQueueMapTransparentZWrite=new Map;let n=this.parser.json;n.extensionsUsed=(t=n.extensionsUsed)!==null&&t!==void 0?t:[],n.extensionsUsed.indexOf("KHR_texture_transform")===-1&&n.extensionsUsed.push("KHR_texture_transform")}beforeRoot(){var e;return Hi(this,void 0,void 0,function*(){let t=this.parser.json,n=(e=t.extensions)===null||e===void 0?void 0:e.VRM,i=n?.materialProperties;i&&(this._populateRenderQueueMap(i),i.forEach((r,s)=>{var a,u;let d=(a=t.materials)===null||a===void 0?void 0:a[s];if(d==null){console.warn(`VRMMaterialsV0CompatPlugin: Attempt to use materials[${s}] of glTF but the material doesn't exist`);return}if(r.shader==="VRM/MToon"){let c=this._parseV0MToonProperties(r,d);t.materials[s]=c}else if(!((u=r.shader)===null||u===void 0)&&u.startsWith("VRM/Unlit")){let c=this._parseV0UnlitProperties(r,d);t.materials[s]=c}else r.shader==="VRM_USE_GLTFSHADER"||console.warn(`VRMMaterialsV0CompatPlugin: Unknown shader: ${r.shader}`)}))})}_parseV0MToonProperties(e,t){var n,i,r,s,a,u,d,c,h,p,f,g,m,_,v,M,x,E,T,y,R,P,S,A,L,O,W,Be,We,ke,ze,je,$e,Qe,qe,Xe,Ge,Ye,Ze,Je,Ke,et,tt,nt,it,rt,ot,st,at,lt,ut,dt,ct,ht,ft;let Wt=(i=(n=e.keywordMap)===null||n===void 0?void 0:n._ALPHABLEND_ON)!==null&&i!==void 0?i:!1,yn=((r=e.floatProperties)===null||r===void 0?void 0:r._ZWrite)===1&&Wt,wn=this._v0ParseRenderQueue(e),kt=(a=(s=e.keywordMap)===null||s===void 0?void 0:s._ALPHATEST_ON)!==null&&a!==void 0?a:!1,Sn=Wt?"BLEND":kt?"MASK":"OPAQUE",An=kt?(d=(u=e.floatProperties)===null||u===void 0?void 0:u._Cutoff)!==null&&d!==void 0?d:.5:void 0,Pn=((h=(c=e.floatProperties)===null||c===void 0?void 0:c._CullMode)!==null&&h!==void 0?h:2)===0,C=this._portTextureTransform(e),Ln=((f=(p=e.vectorProperties)===null||p===void 0?void 0:p._Color)!==null&&f!==void 0?f:[1,1,1,1]).map((Zt,Kn)=>Kn===3?Zt:z(Zt)),zt=(g=e.textureProperties)===null||g===void 0?void 0:g._MainTex,In=zt!=null?{index:zt,extensions:Object.assign({},C)}:void 0,Hn=(_=(m=e.floatProperties)===null||m===void 0?void 0:m._BumpScale)!==null&&_!==void 0?_:1,jt=(v=e.textureProperties)===null||v===void 0?void 0:v._BumpMap,bn=jt!=null?{index:jt,scale:Hn,extensions:Object.assign({},C)}:void 0,Un=((x=(M=e.vectorProperties)===null||M===void 0?void 0:M._EmissionColor)!==null&&x!==void 0?x:[0,0,0,1]).map(z),$t=(E=e.textureProperties)===null||E===void 0?void 0:E._EmissionMap,On=$t!=null?{index:$t,extensions:Object.assign({},C)}:void 0,Nn=((y=(T=e.vectorProperties)===null||T===void 0?void 0:T._ShadeColor)!==null&&y!==void 0?y:[.97,.81,.86,1]).map(z),Qt=(R=e.textureProperties)===null||R===void 0?void 0:R._ShadeTexture,Cn=Qt!=null?{index:Qt,extensions:Object.assign({},C)}:void 0,ae=(S=(P=e.floatProperties)===null||P===void 0?void 0:P._ShadeShift)!==null&&S!==void 0?S:0,le=(L=(A=e.floatProperties)===null||A===void 0?void 0:A._ShadeToony)!==null&&L!==void 0?L:.9;le=o.MathUtils.lerp(le,1,.5+.5*ae),ae=-ae-(1-le);let qt=(W=(O=e.floatProperties)===null||O===void 0?void 0:O._IndirectLightIntensity)!==null&&W!==void 0?W:.1,Vn=qt?1-qt:void 0,pt=(Be=e.textureProperties)===null||Be===void 0?void 0:Be._SphereAdd,Dn=pt!=null?[1,1,1]:void 0,Fn=pt!=null?{index:pt}:void 0,Bn=(ke=(We=e.floatProperties)===null||We===void 0?void 0:We._RimLightingMix)!==null&&ke!==void 0?ke:0,Xt=(ze=e.textureProperties)===null||ze===void 0?void 0:ze._RimTexture,Wn=Xt!=null?{index:Xt,extensions:Object.assign({},C)}:void 0,kn=(($e=(je=e.vectorProperties)===null||je===void 0?void 0:je._RimColor)!==null&&$e!==void 0?$e:[0,0,0,1]).map(z),zn=(qe=(Qe=e.floatProperties)===null||Qe===void 0?void 0:Qe._RimFresnelPower)!==null&&qe!==void 0?qe:1,jn=(Ge=(Xe=e.floatProperties)===null||Xe===void 0?void 0:Xe._RimLift)!==null&&Ge!==void 0?Ge:0,$n=["none","worldCoordinates","screenCoordinates"][(Ze=(Ye=e.floatProperties)===null||Ye===void 0?void 0:Ye._OutlineWidthMode)!==null&&Ze!==void 0?Ze:0],mt=(Ke=(Je=e.floatProperties)===null||Je===void 0?void 0:Je._OutlineWidth)!==null&&Ke!==void 0?Ke:0;mt=.01*mt;let Gt=(et=e.textureProperties)===null||et===void 0?void 0:et._OutlineWidthTexture,Qn=Gt!=null?{index:Gt,extensions:Object.assign({},C)}:void 0,qn=((nt=(tt=e.vectorProperties)===null||tt===void 0?void 0:tt._OutlineColor)!==null&&nt!==void 0?nt:[0,0,0]).map(z),Xn=((rt=(it=e.floatProperties)===null||it===void 0?void 0:it._OutlineColorMode)!==null&&rt!==void 0?rt:0)===1?(st=(ot=e.floatProperties)===null||ot===void 0?void 0:ot._OutlineLightingMix)!==null&&st!==void 0?st:1:0,Yt=(at=e.textureProperties)===null||at===void 0?void 0:at._UvAnimMaskTexture,Gn=Yt!=null?{index:Yt,extensions:Object.assign({},C)}:void 0,Yn=(ut=(lt=e.floatProperties)===null||lt===void 0?void 0:lt._UvAnimScrollX)!==null&&ut!==void 0?ut:0,ue=(ct=(dt=e.floatProperties)===null||dt===void 0?void 0:dt._UvAnimScrollY)!==null&&ct!==void 0?ct:0;ue!=null&&(ue=-ue);let Zn=(ft=(ht=e.floatProperties)===null||ht===void 0?void 0:ht._UvAnimRotation)!==null&&ft!==void 0?ft:0,Jn={specVersion:"1.0",transparentWithZWrite:yn,renderQueueOffsetNumber:wn,shadeColorFactor:Nn,shadeMultiplyTexture:Cn,shadingShiftFactor:ae,shadingToonyFactor:le,giEqualizationFactor:Vn,matcapFactor:Dn,matcapTexture:Fn,rimLightingMixFactor:Bn,rimMultiplyTexture:Wn,parametricRimColorFactor:kn,parametricRimFresnelPowerFactor:zn,parametricRimLiftFactor:jn,outlineWidthMode:$n,outlineWidthFactor:mt,outlineWidthMultiplyTexture:Qn,outlineColorFactor:qn,outlineLightingMixFactor:Xn,uvAnimationMaskTexture:Gn,uvAnimationScrollXSpeedFactor:Yn,uvAnimationScrollYSpeedFactor:ue,uvAnimationRotationSpeedFactor:Zn};return Object.assign(Object.assign({},t),{pbrMetallicRoughness:{baseColorFactor:Ln,baseColorTexture:In},normalTexture:bn,emissiveTexture:On,emissiveFactor:Un,alphaMode:Sn,alphaCutoff:An,doubleSided:Pn,extensions:{VRMC_materials_mtoon:Jn}})}_parseV0UnlitProperties(e,t){var n,i,r,s,a;let u=e.shader==="VRM/UnlitTransparentZWrite",d=e.shader==="VRM/UnlitTransparent"||u,c=this._v0ParseRenderQueue(e),h=e.shader==="VRM/UnlitCutout",p=d?"BLEND":h?"MASK":"OPAQUE",f=h?(i=(n=e.floatProperties)===null||n===void 0?void 0:n._Cutoff)!==null&&i!==void 0?i:.5:void 0,g=this._portTextureTransform(e),m=((s=(r=e.vectorProperties)===null||r===void 0?void 0:r._Color)!==null&&s!==void 0?s:[1,1,1,1]).map(z),_=(a=e.textureProperties)===null||a===void 0?void 0:a._MainTex,v=_!=null?{index:_,extensions:Object.assign({},g)}:void 0,M={specVersion:"1.0",transparentWithZWrite:u,renderQueueOffsetNumber:c,shadeColorFactor:m,shadeMultiplyTexture:v};return Object.assign(Object.assign({},t),{pbrMetallicRoughness:{baseColorFactor:m,baseColorTexture:v},alphaMode:p,alphaCutoff:f,extensions:{VRMC_materials_mtoon:M}})}_portTextureTransform(e){var t,n,i,r,s;let a=(t=e.vectorProperties)===null||t===void 0?void 0:t._MainTex;if(a==null)return{};let u=[(n=a?.[0])!==null&&n!==void 0?n:0,(i=a?.[1])!==null&&i!==void 0?i:0],d=[(r=a?.[2])!==null&&r!==void 0?r:1,(s=a?.[3])!==null&&s!==void 0?s:1];return u[1]=1-d[1]-u[1],{KHR_texture_transform:{offset:u,scale:d}}}_v0ParseRenderQueue(e){var t,n,i;let r=(n=(t=e.keywordMap)===null||t===void 0?void 0:t._ALPHABLEND_ON)!==null&&n!==void 0?n:!1,s=((i=e.floatProperties)===null||i===void 0?void 0:i._ZWrite)===1,a=0;if(r){let u=e.renderQueue;u!=null&&(s?a=this._renderQueueMapTransparentZWrite.get(u):a=this._renderQueueMapTransparent.get(u))}return a}_populateRenderQueueMap(e){let t=new Set,n=new Set;e.forEach(i=>{var r,s,a;let u=(s=(r=i.keywordMap)===null||r===void 0?void 0:r._ALPHABLEND_ON)!==null&&s!==void 0?s:!1,d=((a=i.floatProperties)===null||a===void 0?void 0:a._ZWrite)===1;if(u){let c=i.renderQueue;c!=null&&(d?n.add(c):t.add(c))}}),t.size>10&&console.warn(`VRMMaterialsV0CompatPlugin: This VRM uses ${t.size} render queues for Transparent materials while VRM 1.0 only supports up to 10 render queues. The model might not be rendered correctly.`),n.size>10&&console.warn(`VRMMaterialsV0CompatPlugin: This VRM uses ${n.size} render queues for TransparentZWrite materials while VRM 1.0 only supports up to 10 render queues. The model might not be rendered correctly.`),Array.from(t).sort().forEach((i,r)=>{let s=Math.min(Math.max(r-t.size+1,-9),0);this._renderQueueMapTransparent.set(i,s)}),Array.from(n).sort().forEach((i,r)=>{let s=Math.min(Math.max(r,0),9);this._renderQueueMapTransparentZWrite.set(i,s)})}};var N=new o.Vector3,ee=class extends o.Group{constructor(e){super(),this._attrPosition=new o.BufferAttribute(new Float32Array([0,0,0,0,0,0]),3),this._attrPosition.setUsage(o.DynamicDrawUsage);let t=new o.BufferGeometry;t.setAttribute("position",this._attrPosition);let n=new o.LineBasicMaterial({color:16711935,depthTest:!1,depthWrite:!1});this._line=new o.Line(t,n),this.add(this._line),this.constraint=e}updateMatrixWorld(e){N.setFromMatrixPosition(this.constraint.destination.matrixWorld),this._attrPosition.setXYZ(0,N.x,N.y,N.z),this.constraint.source&&N.setFromMatrixPosition(this.constraint.source.matrixWorld),this._attrPosition.setXYZ(1,N.x,N.y,N.z),this._attrPosition.needsUpdate=!0,super.updateMatrixWorld(e)}};function fn(l,e){return e.set(l.elements[12],l.elements[13],l.elements[14])}var bi=new o.Vector3,Ui=new o.Vector3;function Oi(l,e){return l.decompose(bi,e,Ui),e}function He(l){return l.invert?l.invert():l.inverse(),l}var se=class{constructor(e,t){this.destination=e,this.source=t,this.weight=1}},Ni=new o.Vector3,Ci=new o.Vector3,Vi=new o.Vector3,Di=new o.Quaternion,Fi=new o.Quaternion,Bi=new o.Quaternion,Ht=class extends se{get aimAxis(){return this._aimAxis}set aimAxis(e){this._aimAxis=e,this._v3AimAxis.set(e==="PositiveX"?1:e==="NegativeX"?-1:0,e==="PositiveY"?1:e==="NegativeY"?-1:0,e==="PositiveZ"?1:e==="NegativeZ"?-1:0)}get dependencies(){let e=new Set([this.source]);return this.destination.parent&&e.add(this.destination.parent),e}constructor(e,t){super(e,t),this._aimAxis="PositiveX",this._v3AimAxis=new o.Vector3(1,0,0),this._dstRestQuat=new o.Quaternion}setInitState(){this._dstRestQuat.copy(this.destination.quaternion)}update(){this.destination.updateWorldMatrix(!0,!1),this.source.updateWorldMatrix(!0,!1);let e=Di.identity(),t=Fi.identity();this.destination.parent&&(Oi(this.destination.parent.matrixWorld,e),He(t.copy(e)));let n=Ni.copy(this._v3AimAxis).applyQuaternion(this._dstRestQuat).applyQuaternion(e),i=fn(this.source.matrixWorld,Ci).sub(fn(this.destination.matrixWorld,Vi)).normalize(),r=Bi.setFromUnitVectors(n,i).premultiply(t).multiply(e).multiply(this._dstRestQuat);this.destination.quaternion.copy(this._dstRestQuat).slerp(r,this.weight)}};function pn(l,e,t,n){function i(r){return r instanceof t?r:new t(function(s){s(r)})}return new(t||(t=Promise))(function(r,s){function a(c){try{d(n.next(c))}catch(h){s(h)}}function u(c){try{d(n.throw(c))}catch(h){s(h)}}function d(c){c.done?r(c.value):i(c.value).then(a,u)}d((n=n.apply(l,e||[])).next())})}function Wi(l,e){let t=[l],n=l.parent;for(;n!==null;)t.unshift(n),n=n.parent;t.forEach(i=>{e(i)})}var bt=class{constructor(){this._constraints=new Set,this._objectConstraintsMap=new Map}get constraints(){return this._constraints}addConstraint(e){this._constraints.add(e);let t=this._objectConstraintsMap.get(e.destination);t==null&&(t=new Set,this._objectConstraintsMap.set(e.destination,t)),t.add(e)}deleteConstraint(e){this._constraints.delete(e),this._objectConstraintsMap.get(e.destination).delete(e)}setInitState(){let e=new Set,t=new Set;for(let n of this._constraints)this._processConstraint(n,e,t,i=>i.setInitState())}update(){let e=new Set,t=new Set;for(let n of this._constraints)this._processConstraint(n,e,t,i=>i.update())}_processConstraint(e,t,n,i){if(n.has(e))return;if(t.has(e))throw new Error("VRMNodeConstraintManager: Circular dependency detected while updating constraints");t.add(e);let r=e.dependencies;for(let s of r)Wi(s,a=>{let u=this._objectConstraintsMap.get(a);if(u)for(let d of u)this._processConstraint(d,t,n,i)});i(e),n.add(e)}},ki=new o.Quaternion,zi=new o.Quaternion,Ut=class extends se{get dependencies(){return new Set([this.source])}constructor(e,t){super(e,t),this._dstRestQuat=new o.Quaternion,this._invSrcRestQuat=new o.Quaternion}setInitState(){this._dstRestQuat.copy(this.destination.quaternion),He(this._invSrcRestQuat.copy(this.source.quaternion))}update(){let e=ki.copy(this._invSrcRestQuat).multiply(this.source.quaternion),t=zi.copy(this._dstRestQuat).multiply(e);this.destination.quaternion.copy(this._dstRestQuat).slerp(t,this.weight)}},ji=new o.Vector3,$i=new o.Quaternion,Qi=new o.Quaternion,Ot=class extends se{get rollAxis(){return this._rollAxis}set rollAxis(e){this._rollAxis=e,this._v3RollAxis.set(e==="X"?1:0,e==="Y"?1:0,e==="Z"?1:0)}get dependencies(){return new Set([this.source])}constructor(e,t){super(e,t),this._rollAxis="X",this._v3RollAxis=new o.Vector3(1,0,0),this._dstRestQuat=new o.Quaternion,this._invDstRestQuat=new o.Quaternion,this._invSrcRestQuatMulDstRestQuat=new o.Quaternion}setInitState(){this._dstRestQuat.copy(this.destination.quaternion),He(this._invDstRestQuat.copy(this._dstRestQuat)),He(this._invSrcRestQuatMulDstRestQuat.copy(this.source.quaternion)).multiply(this._dstRestQuat)}update(){let e=$i.copy(this._invDstRestQuat).multiply(this.source.quaternion).multiply(this._invSrcRestQuatMulDstRestQuat),t=ji.copy(this._v3RollAxis).applyQuaternion(e),i=Qi.setFromUnitVectors(t,this._v3RollAxis).premultiply(this._dstRestQuat).multiply(e);this.destination.quaternion.copy(this._dstRestQuat).slerp(i,this.weight)}},qi=new Set(["1.0","1.0-beta"]),be=class l{get name(){return l.EXTENSION_NAME}constructor(e,t){this.parser=e,this.helperRoot=t?.helperRoot}afterRoot(e){return pn(this,void 0,void 0,function*(){e.userData.vrmNodeConstraintManager=yield this._import(e)})}_import(e){var t;return pn(this,void 0,void 0,function*(){let n=this.parser.json;if(!(((t=n.extensionsUsed)===null||t===void 0?void 0:t.indexOf(l.EXTENSION_NAME))!==-1))return null;let r=new bt,s=yield this.parser.getDependencies("node");return s.forEach((a,u)=>{var d;let c=n.nodes[u],h=(d=c?.extensions)===null||d===void 0?void 0:d[l.EXTENSION_NAME];if(h==null)return;let p=h.specVersion;if(!qi.has(p)){console.warn(`VRMNodeConstraintLoaderPlugin: Unknown ${l.EXTENSION_NAME} specVersion "${p}"`);return}let f=h.constraint;if(f.roll!=null){let g=this._importRollConstraint(a,s,f.roll);r.addConstraint(g)}else if(f.aim!=null){let g=this._importAimConstraint(a,s,f.aim);r.addConstraint(g)}else if(f.rotation!=null){let g=this._importRotationConstraint(a,s,f.rotation);r.addConstraint(g)}}),e.scene.updateMatrixWorld(),r.setInitState(),r})}_importRollConstraint(e,t,n){let{source:i,rollAxis:r,weight:s}=n,a=t[i],u=new Ot(e,a);if(r!=null&&(u.rollAxis=r),s!=null&&(u.weight=s),this.helperRoot){let d=new ee(u);this.helperRoot.add(d)}return u}_importAimConstraint(e,t,n){let{source:i,aimAxis:r,weight:s}=n,a=t[i],u=new Ht(e,a);if(r!=null&&(u.aimAxis=r),s!=null&&(u.weight=s),this.helperRoot){let d=new ee(u);this.helperRoot.add(d)}return u}_importRotationConstraint(e,t,n){let{source:i,weight:r}=n,s=t[i],a=new Ut(e,s);if(r!=null&&(a.weight=r),this.helperRoot){let u=new ee(a);this.helperRoot.add(u)}return a}};be.EXTENSION_NAME="VRMC_node_constraint";var Ue=class{},xt=new o.Vector3,F=new o.Vector3,Oe=class extends Ue{get type(){return"capsule"}constructor(e){var t,n,i;super(),this.offset=(t=e?.offset)!==null&&t!==void 0?t:new o.Vector3(0,0,0),this.tail=(n=e?.tail)!==null&&n!==void 0?n:new o.Vector3(0,0,0),this.radius=(i=e?.radius)!==null&&i!==void 0?i:0}calculateCollision(e,t,n,i){xt.copy(this.offset).applyMatrix4(e),F.copy(this.tail).applyMatrix4(e),F.sub(xt);let r=F.lengthSq();i.copy(t).sub(xt);let s=F.dot(i);s<=0||(r<=s||F.multiplyScalar(s/r),i.sub(F));let a=n+this.radius,u=i.length()-a;return i.normalize(),u}},Ne=class extends Ue{get type(){return"sphere"}constructor(e){var t,n;super(),this.offset=(t=e?.offset)!==null&&t!==void 0?t:new o.Vector3(0,0,0),this.radius=(n=e?.radius)!==null&&n!==void 0?n:0}calculateCollision(e,t,n,i){i.copy(this.offset).applyMatrix4(e),i.negate().add(t);let r=n+this.radius,s=i.length()-r;return i.normalize(),s}},b=new o.Vector3,Nt=class extends o.BufferGeometry{constructor(e){super(),this.worldScale=1,this._currentRadius=0,this._currentOffset=new o.Vector3,this._currentTail=new o.Vector3,this._shape=e,this._attrPos=new o.BufferAttribute(new Float32Array(396),3),this.setAttribute("position",this._attrPos),this._attrIndex=new o.BufferAttribute(new Uint16Array(264),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let e=!1,t=this._shape.radius/this.worldScale;this._currentRadius!==t&&(this._currentRadius=t,e=!0),this._currentOffset.equals(this._shape.offset)||(this._currentOffset.copy(this._shape.offset),e=!0);let n=b.copy(this._shape.tail).divideScalar(this.worldScale);this._currentTail.distanceToSquared(n)>1e-10&&(this._currentTail.copy(n),e=!0),e&&this._buildPosition()}_buildPosition(){b.copy(this._currentTail).sub(this._currentOffset);let e=b.length()/this._currentRadius;for(let i=0;i<=16;i++){let r=i/16*Math.PI;this._attrPos.setXYZ(i,-Math.sin(r),-Math.cos(r),0),this._attrPos.setXYZ(17+i,e+Math.sin(r),Math.cos(r),0),this._attrPos.setXYZ(34+i,-Math.sin(r),0,-Math.cos(r)),this._attrPos.setXYZ(51+i,e+Math.sin(r),0,Math.cos(r))}for(let i=0;i<32;i++){let r=i/16*Math.PI;this._attrPos.setXYZ(68+i,0,Math.sin(r),Math.cos(r)),this._attrPos.setXYZ(100+i,e,Math.sin(r),Math.cos(r))}let t=Math.atan2(b.y,Math.sqrt(b.x*b.x+b.z*b.z)),n=-Math.atan2(b.z,b.x);this.rotateZ(t),this.rotateY(n),this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentOffset.x,this._currentOffset.y,this._currentOffset.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let e=0;e<34;e++){let t=(e+1)%34;this._attrIndex.setXY(e*2,e,t),this._attrIndex.setXY(68+e*2,34+e,34+t)}for(let e=0;e<32;e++){let t=(e+1)%32;this._attrIndex.setXY(136+e*2,68+e,68+t),this._attrIndex.setXY(200+e*2,100+e,100+t)}this._attrIndex.needsUpdate=!0}},Ct=class extends o.BufferGeometry{constructor(e){super(),this.worldScale=1,this._currentRadius=0,this._currentOffset=new o.Vector3,this._shape=e,this._attrPos=new o.BufferAttribute(new Float32Array(32*3*3),3),this.setAttribute("position",this._attrPos),this._attrIndex=new o.BufferAttribute(new Uint16Array(64*3),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let e=!1,t=this._shape.radius/this.worldScale;this._currentRadius!==t&&(this._currentRadius=t,e=!0),this._currentOffset.equals(this._shape.offset)||(this._currentOffset.copy(this._shape.offset),e=!0),e&&this._buildPosition()}_buildPosition(){for(let e=0;e<32;e++){let t=e/16*Math.PI;this._attrPos.setXYZ(e,Math.cos(t),Math.sin(t),0),this._attrPos.setXYZ(32+e,0,Math.cos(t),Math.sin(t)),this._attrPos.setXYZ(64+e,Math.sin(t),0,Math.cos(t))}this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentOffset.x,this._currentOffset.y,this._currentOffset.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let e=0;e<32;e++){let t=(e+1)%32;this._attrIndex.setXY(e*2,e,t),this._attrIndex.setXY(64+e*2,32+e,32+t),this._attrIndex.setXY(128+e*2,64+e,64+t)}this._attrIndex.needsUpdate=!0}},Xi=new o.Vector3,Ce=class extends o.Group{constructor(e){if(super(),this.matrixAutoUpdate=!1,this.collider=e,this.collider.shape instanceof Ne)this._geometry=new Ct(this.collider.shape);else if(this.collider.shape instanceof Oe)this._geometry=new Nt(this.collider.shape);else throw new Error("VRMSpringBoneColliderHelper: Unknown collider shape type detected");let t=new o.LineBasicMaterial({color:16711935,depthTest:!1,depthWrite:!1});this._line=new o.LineSegments(this._geometry,t),this.add(this._line)}dispose(){this._geometry.dispose()}updateMatrixWorld(e){this.collider.updateWorldMatrix(!0,!1),this.matrix.copy(this.collider.matrixWorld);let t=this.matrix.elements;this._geometry.worldScale=Xi.set(t[0],t[1],t[2]).length(),this._geometry.update(),super.updateMatrixWorld(e)}},Vt=class extends o.BufferGeometry{constructor(e){super(),this.worldScale=1,this._currentRadius=0,this._currentTail=new o.Vector3,this._springBone=e,this._attrPos=new o.BufferAttribute(new Float32Array(294),3),this.setAttribute("position",this._attrPos),this._attrIndex=new o.BufferAttribute(new Uint16Array(194),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let e=!1,t=this._springBone.settings.hitRadius/this.worldScale;this._currentRadius!==t&&(this._currentRadius=t,e=!0),this._currentTail.equals(this._springBone.initialLocalChildPosition)||(this._currentTail.copy(this._springBone.initialLocalChildPosition),e=!0),e&&this._buildPosition()}_buildPosition(){for(let e=0;e<32;e++){let t=e/16*Math.PI;this._attrPos.setXYZ(e,Math.cos(t),Math.sin(t),0),this._attrPos.setXYZ(32+e,0,Math.cos(t),Math.sin(t)),this._attrPos.setXYZ(64+e,Math.sin(t),0,Math.cos(t))}this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.setXYZ(96,0,0,0),this._attrPos.setXYZ(97,this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let e=0;e<32;e++){let t=(e+1)%32;this._attrIndex.setXY(e*2,e,t),this._attrIndex.setXY(64+e*2,32+e,32+t),this._attrIndex.setXY(128+e*2,64+e,64+t)}this._attrIndex.setXY(192,96,97),this._attrIndex.needsUpdate=!0}},Gi=new o.Vector3,Dt=class extends o.Group{constructor(e){super(),this.matrixAutoUpdate=!1,this.springBone=e,this._geometry=new Vt(this.springBone);let t=new o.LineBasicMaterial({color:16776960,depthTest:!1,depthWrite:!1});this._line=new o.LineSegments(this._geometry,t),this.add(this._line)}dispose(){this._geometry.dispose()}updateMatrixWorld(e){this.springBone.bone.updateWorldMatrix(!0,!1),this.matrix.copy(this.springBone.bone.matrixWorld);let t=this.matrix.elements;this._geometry.worldScale=Gi.set(t[0],t[1],t[2]).length(),this._geometry.update(),super.updateMatrixWorld(e)}},Ve=class extends o.Object3D{constructor(e){super(),this.shape=e}},Yi=new o.Matrix4;function Rn(l){return l.invert?l.invert():l.getInverse(Yi.copy(l)),l}var Ft=class{get inverse(){return this._shouldUpdateInverse&&(this._inverseCache.copy(this.matrix),Rn(this._inverseCache),this._shouldUpdateInverse=!1),this._inverseCache}constructor(e){this._inverseCache=new o.Matrix4,this._shouldUpdateInverse=!0,this.matrix=e;let t={set:(n,i,r)=>(this._shouldUpdateInverse=!0,n[i]=r,!0)};this._originalElements=e.elements,e.elements=new Proxy(e.elements,t)}revert(){this.matrix.elements=this._originalElements}},Zi=new o.Matrix4,U=new o.Vector3,Z=new o.Vector3,Ji=new o.Vector3,j=new o.Vector3,mn=new o.Vector3,J=new o.Vector3,vn=new o.Quaternion,$=new o.Matrix4,Ki=new o.Matrix4,Bt=class{get center(){return this._center}set center(e){var t;!((t=this._center)===null||t===void 0)&&t.userData.inverseCacheProxy&&(this._center.userData.inverseCacheProxy.revert(),delete this._center.userData.inverseCacheProxy),this._center=e,this._center&&(this._center.userData.inverseCacheProxy||(this._center.userData.inverseCacheProxy=new Ft(this._center.matrixWorld)))}get initialLocalChildPosition(){return this._initialLocalChildPosition}get _parentMatrixWorld(){return this.bone.parent?this.bone.parent.matrixWorld:Zi}constructor(e,t,n={},i=[]){var r,s,a,u,d,c;this._currentTail=new o.Vector3,this._prevTail=new o.Vector3,this._boneAxis=new o.Vector3,this._worldSpaceBoneLength=0,this._center=null,this._initialLocalMatrix=new o.Matrix4,this._initialLocalRotation=new o.Quaternion,this._initialLocalChildPosition=new o.Vector3,this.bone=e,this.bone.matrixAutoUpdate=!1,this.child=t,this.settings={hitRadius:(r=n.hitRadius)!==null&&r!==void 0?r:0,stiffness:(s=n.stiffness)!==null&&s!==void 0?s:1,gravityPower:(a=n.gravityPower)!==null&&a!==void 0?a:0,gravityDir:(d=(u=n.gravityDir)===null||u===void 0?void 0:u.clone())!==null&&d!==void 0?d:new o.Vector3(0,-1,0),dragForce:(c=n.dragForce)!==null&&c!==void 0?c:.4},this.colliderGroups=i}setInitState(){this._initialLocalMatrix.copy(this.bone.matrix),this._initialLocalRotation.copy(this.bone.quaternion),this.child?this._initialLocalChildPosition.copy(this.child.position):this._initialLocalChildPosition.copy(this.bone.position).normalize().multiplyScalar(.07);let e=this._getMatrixWorldToCenter($);this.bone.localToWorld(this._currentTail.copy(this._initialLocalChildPosition)).applyMatrix4(e),this._prevTail.copy(this._currentTail),this._boneAxis.copy(this._initialLocalChildPosition).normalize()}reset(){this.bone.quaternion.copy(this._initialLocalRotation),this.bone.updateMatrix(),this.bone.matrixWorld.multiplyMatrices(this._parentMatrixWorld,this.bone.matrix);let e=this._getMatrixWorldToCenter($);this.bone.localToWorld(this._currentTail.copy(this._initialLocalChildPosition)).applyMatrix4(e),this._prevTail.copy(this._currentTail)}update(e){if(e<=0)return;this._calcWorldSpaceBoneLength(),j.setFromMatrixPosition(this.bone.matrixWorld);let t=this._getMatrixWorldToCenter($);mn.copy(j).applyMatrix4(t);let n=vn.setFromRotationMatrix(t),i=Ki.copy(t).multiply(this._parentMatrixWorld),r=Z.copy(this._boneAxis).applyMatrix4(this._initialLocalMatrix).applyMatrix4(i).sub(mn).normalize(),s=Ji.copy(this.settings.gravityDir).applyQuaternion(n).normalize(),a=this._getMatrixCenterToWorld($);J.copy(this._currentTail).add(U.copy(this._currentTail).sub(this._prevTail).multiplyScalar(1-this.settings.dragForce)).add(U.copy(r).multiplyScalar(this.settings.stiffness*e)).add(U.copy(s).multiplyScalar(this.settings.gravityPower*e)).applyMatrix4(a),J.sub(j).normalize().multiplyScalar(this._worldSpaceBoneLength).add(j),this._collision(J),t=this._getMatrixWorldToCenter($),this._prevTail.copy(this._currentTail),this._currentTail.copy(U.copy(J).applyMatrix4(t));let u=Rn($.copy(this._parentMatrixWorld).multiply(this._initialLocalMatrix)),d=vn.setFromUnitVectors(this._boneAxis,U.copy(J).applyMatrix4(u).normalize());this.bone.quaternion.copy(this._initialLocalRotation).multiply(d),this.bone.updateMatrix(),this.bone.matrixWorld.multiplyMatrices(this._parentMatrixWorld,this.bone.matrix)}_collision(e){this.colliderGroups.forEach(t=>{t.colliders.forEach(n=>{let i=n.shape.calculateCollision(n.matrixWorld,e,this.settings.hitRadius,U);i<0&&(e.add(U.multiplyScalar(-i)),e.sub(j).normalize().multiplyScalar(this._worldSpaceBoneLength).add(j))})})}_calcWorldSpaceBoneLength(){U.setFromMatrixPosition(this.bone.matrixWorld),this.child?Z.setFromMatrixPosition(this.child.matrixWorld):(Z.copy(this._initialLocalChildPosition),Z.applyMatrix4(this.bone.matrixWorld)),this._worldSpaceBoneLength=U.sub(Z).length()}_getMatrixCenterToWorld(e){return this._center?e.copy(this._center.matrixWorld):e.identity(),e}_getMatrixWorldToCenter(e){return this._center?e.copy(this._center.userData.inverseCacheProxy.inverse):e.identity(),e}};function fe(l,e,t,n){function i(r){return r instanceof t?r:new t(function(s){s(r)})}return new(t||(t=Promise))(function(r,s){function a(c){try{d(n.next(c))}catch(h){s(h)}}function u(c){try{d(n.throw(c))}catch(h){s(h)}}function d(c){c.done?r(c.value):i(c.value).then(a,u)}d((n=n.apply(l,e||[])).next())})}function er(l,e){let t=[],n=l;for(;n!==null;)t.unshift(n),n=n.parent;t.forEach(i=>{e(i)})}function xn(l,e){l.children.forEach(t=>{e(t)||xn(t,e)})}var De=class{constructor(){this._joints=new Set,this._objectSpringBonesMap=new Map}get joints(){return this._joints}get springBones(){return console.warn("VRMSpringBoneManager: springBones is deprecated. use joints instead."),this._joints}get colliderGroups(){let e=new Set;return this._joints.forEach(t=>{t.colliderGroups.forEach(n=>{e.add(n)})}),Array.from(e)}get colliders(){let e=new Set;return this.colliderGroups.forEach(t=>{t.colliders.forEach(n=>{e.add(n)})}),Array.from(e)}addJoint(e){this._joints.add(e);let t=this._objectSpringBonesMap.get(e.bone);t==null&&(t=new Set,this._objectSpringBonesMap.set(e.bone,t)),t.add(e)}addSpringBone(e){console.warn("VRMSpringBoneManager: addSpringBone() is deprecated. use addJoint() instead."),this.addJoint(e)}deleteJoint(e){this._joints.delete(e),this._objectSpringBonesMap.get(e.bone).delete(e)}deleteSpringBone(e){console.warn("VRMSpringBoneManager: deleteSpringBone() is deprecated. use deleteJoint() instead."),this.deleteJoint(e)}setInitState(){let e=new Set,t=new Set,n=new Set;for(let i of this._joints)this._processSpringBone(i,e,t,n,r=>r.setInitState())}reset(){let e=new Set,t=new Set,n=new Set;for(let i of this._joints)this._processSpringBone(i,e,t,n,r=>r.reset())}update(e){let t=new Set,n=new Set,i=new Set;for(let r of this._joints)this._processSpringBone(r,t,n,i,s=>s.update(e)),xn(r.bone,s=>{var a,u;return((u=(a=this._objectSpringBonesMap.get(s))===null||a===void 0?void 0:a.size)!==null&&u!==void 0?u:0)>0?!0:(s.updateWorldMatrix(!1,!1),!1)})}_processSpringBone(e,t,n,i,r){if(n.has(e))return;if(t.has(e))throw new Error("VRMSpringBoneManager: Circular dependency detected while updating springbones");t.add(e);let s=this._getDependencies(e);for(let a of s)er(a,u=>{let d=this._objectSpringBonesMap.get(u);if(d)for(let c of d)this._processSpringBone(c,t,n,i,r);else i.has(u)||(u.updateWorldMatrix(!1,!1),i.add(u))});e.bone.updateMatrix(),e.bone.updateWorldMatrix(!1,!1),r(e),i.add(e.bone),n.add(e)}_getDependencies(e){let t=new Set,n=e.bone.parent;return n&&t.add(n),e.colliderGroups.forEach(i=>{i.colliders.forEach(r=>{t.add(r)})}),t}},tr=new Set(["1.0","1.0-beta"]),Fe=class l{get name(){return l.EXTENSION_NAME}constructor(e,t){this.parser=e,this.jointHelperRoot=t?.jointHelperRoot,this.colliderHelperRoot=t?.colliderHelperRoot}afterRoot(e){return fe(this,void 0,void 0,function*(){e.userData.vrmSpringBoneManager=yield this._import(e)})}_import(e){return fe(this,void 0,void 0,function*(){let t=yield this._v1Import(e);if(t!=null)return t;let n=yield this._v0Import(e);return n??null})}_v1Import(e){var t,n,i,r,s;return fe(this,void 0,void 0,function*(){let a=e.parser.json;if(!(((t=a.extensionsUsed)===null||t===void 0?void 0:t.indexOf(l.EXTENSION_NAME))!==-1))return null;let d=new De,c=yield e.parser.getDependencies("node"),h=(n=a.extensions)===null||n===void 0?void 0:n[l.EXTENSION_NAME];if(!h)return null;let p=h.specVersion;if(!tr.has(p))return console.warn(`VRMSpringBoneLoaderPlugin: Unknown ${l.EXTENSION_NAME} specVersion "${p}"`),null;let f=(i=h.colliders)===null||i===void 0?void 0:i.map((m,_)=>{var v,M,x,E,T;let y=c[m.node],R=m.shape;if(R.sphere)return this._importSphereCollider(y,{offset:new o.Vector3().fromArray((v=R.sphere.offset)!==null&&v!==void 0?v:[0,0,0]),radius:(M=R.sphere.radius)!==null&&M!==void 0?M:0});if(R.capsule)return this._importCapsuleCollider(y,{offset:new o.Vector3().fromArray((x=R.capsule.offset)!==null&&x!==void 0?x:[0,0,0]),radius:(E=R.capsule.radius)!==null&&E!==void 0?E:0,tail:new o.Vector3().fromArray((T=R.capsule.tail)!==null&&T!==void 0?T:[0,0,0])});throw new Error(`VRMSpringBoneLoaderPlugin: The collider #${_} has no valid shape`)}),g=(r=h.colliderGroups)===null||r===void 0?void 0:r.map((m,_)=>{var v;return{colliders:((v=m.colliders)!==null&&v!==void 0?v:[]).map(x=>{let E=f?.[x];if(E==null)throw new Error(`VRMSpringBoneLoaderPlugin: The colliderGroup #${_} attempted to use a collider #${x} but not found`);return E}),name:m.name}});return(s=h.springs)===null||s===void 0||s.forEach((m,_)=>{var v;let M=m.joints,x=(v=m.colliderGroups)===null||v===void 0?void 0:v.map(y=>{let R=g?.[y];if(R==null)throw new Error(`VRMSpringBoneLoaderPlugin: The spring #${_} attempted to use a colliderGroup ${y} but not found`);return R}),E=m.center!=null?c[m.center]:void 0,T;M.forEach(y=>{if(T){let R=T.node,P=c[R],S=y.node,A=c[S],L={hitRadius:T.hitRadius,dragForce:T.dragForce,gravityPower:T.gravityPower,stiffness:T.stiffness,gravityDir:T.gravityDir!=null?new o.Vector3().fromArray(T.gravityDir):void 0},O=this._importJoint(P,A,L,x);E&&(O.center=E),d.addJoint(O)}T=y})}),d.setInitState(),d})}_v0Import(e){var t,n,i;return fe(this,void 0,void 0,function*(){let r=e.parser.json;if(!(((t=r.extensionsUsed)===null||t===void 0?void 0:t.indexOf("VRM"))!==-1))return null;let a=(n=r.extensions)===null||n===void 0?void 0:n.VRM,u=a?.secondaryAnimation;if(!u)return null;let d=u?.boneGroups;if(!d)return null;let c=new De,h=yield e.parser.getDependencies("node"),p=(i=u.colliderGroups)===null||i===void 0?void 0:i.map(f=>{var g;let m=h[f.node];return{colliders:((g=f.colliders)!==null&&g!==void 0?g:[]).map((v,M)=>{var x,E,T;let y=new o.Vector3(0,0,0);return v.offset&&y.set((x=v.offset.x)!==null&&x!==void 0?x:0,(E=v.offset.y)!==null&&E!==void 0?E:0,v.offset.z?-v.offset.z:0),this._importSphereCollider(m,{offset:y,radius:(T=v.radius)!==null&&T!==void 0?T:0})})}});return d?.forEach((f,g)=>{let m=f.bones;m&&m.forEach(_=>{var v,M,x,E;let T=h[_],y=new o.Vector3;f.gravityDir?y.set((v=f.gravityDir.x)!==null&&v!==void 0?v:0,(M=f.gravityDir.y)!==null&&M!==void 0?M:0,(x=f.gravityDir.z)!==null&&x!==void 0?x:0):y.set(0,-1,0);let R=f.center!=null?h[f.center]:void 0,P={hitRadius:f.hitRadius,dragForce:f.dragForce,gravityPower:f.gravityPower,stiffness:f.stiffiness,gravityDir:y},S=(E=f.colliderGroups)===null||E===void 0?void 0:E.map(A=>{let L=p?.[A];if(L==null)throw new Error(`VRMSpringBoneLoaderPlugin: The spring #${g} attempted to use a colliderGroup ${A} but not found`);return L});T.traverse(A=>{var L;let O=(L=A.children[0])!==null&&L!==void 0?L:null,W=this._importJoint(A,O,P,S);R&&(W.center=R),c.addJoint(W)})})}),e.scene.updateMatrixWorld(),c.setInitState(),c})}_importJoint(e,t,n,i){let r=new Bt(e,t,n,i);if(this.jointHelperRoot){let s=new Dt(r);this.jointHelperRoot.add(s),s.renderOrder=this.jointHelperRoot.renderOrder}return r}_importSphereCollider(e,t){let{offset:n,radius:i}=t,r=new Ne({offset:n,radius:i}),s=new Ve(r);if(e.add(s),this.colliderHelperRoot){let a=new Ce(s);this.colliderHelperRoot.add(a),a.renderOrder=this.colliderHelperRoot.renderOrder}return s}_importCapsuleCollider(e,t){let{offset:n,radius:i,tail:r}=t,s=new Oe({offset:n,radius:i,tail:r}),a=new Ve(s);if(e.add(a),this.colliderHelperRoot){let u=new Ce(a);this.colliderHelperRoot.add(u),u.renderOrder=this.colliderHelperRoot.renderOrder}return a}};Fe.EXTENSION_NAME="VRMC_springBone";var _n=class{get name(){return"VRMLoaderPlugin"}constructor(e,t){var n,i,r,s,a,u,d,c,h,p;this.parser=e;let f=t?.helperRoot,g=t?.autoUpdateHumanBones;this.expressionPlugin=(n=t?.expressionPlugin)!==null&&n!==void 0?n:new ie(e),this.firstPersonPlugin=(i=t?.firstPersonPlugin)!==null&&i!==void 0?i:new ge(e),this.humanoidPlugin=(r=t?.humanoidPlugin)!==null&&r!==void 0?r:new Re(e,{helperRoot:f,autoUpdateHumanBones:g}),this.lookAtPlugin=(s=t?.lookAtPlugin)!==null&&s!==void 0?s:new Se(e,{helperRoot:f}),this.metaPlugin=(a=t?.metaPlugin)!==null&&a!==void 0?a:new Ae(e),this.mtoonMaterialPlugin=(u=t?.mtoonMaterialPlugin)!==null&&u!==void 0?u:new Le(e),this.materialsHDREmissiveMultiplierPlugin=(d=t?.materialsHDREmissiveMultiplierPlugin)!==null&&d!==void 0?d:new Ie(e),this.materialsV0CompatPlugin=(c=t?.materialsV0CompatPlugin)!==null&&c!==void 0?c:new It(e),this.springBonePlugin=(h=t?.springBonePlugin)!==null&&h!==void 0?h:new Fe(e,{colliderHelperRoot:f,jointHelperRoot:f}),this.nodeConstraintPlugin=(p=t?.nodeConstraintPlugin)!==null&&p!==void 0?p:new be(e,{helperRoot:f})}beforeRoot(){return he(this,void 0,void 0,function*(){yield this.materialsV0CompatPlugin.beforeRoot(),yield this.mtoonMaterialPlugin.beforeRoot()})}loadMesh(e){return he(this,void 0,void 0,function*(){return yield this.mtoonMaterialPlugin.loadMesh(e)})}getMaterialType(e){let t=this.mtoonMaterialPlugin.getMaterialType(e);return t??null}extendMaterialParams(e,t){return he(this,void 0,void 0,function*(){yield this.materialsHDREmissiveMultiplierPlugin.extendMaterialParams(e,t),yield this.mtoonMaterialPlugin.extendMaterialParams(e,t)})}afterRoot(e){return he(this,void 0,void 0,function*(){yield this.metaPlugin.afterRoot(e),yield this.humanoidPlugin.afterRoot(e),yield this.expressionPlugin.afterRoot(e),yield this.lookAtPlugin.afterRoot(e),yield this.firstPersonPlugin.afterRoot(e),yield this.springBonePlugin.afterRoot(e),yield this.nodeConstraintPlugin.afterRoot(e),yield this.mtoonMaterialPlugin.afterRoot(e);let t=e.userData.vrmMeta,n=e.userData.vrmHumanoid;if(t&&n){let i=new Pt({scene:e.scene,expressionManager:e.userData.vrmExpressionManager,firstPerson:e.userData.vrmFirstPerson,humanoid:n,lookAt:e.userData.vrmLookAt,meta:t,materials:e.userData.vrmMToonMaterials,springBoneManager:e.userData.vrmSpringBoneManager,nodeConstraintManager:e.userData.vrmNodeConstraintManager});e.userData.vrm=i}})}};function gn(l){if(Object.values(l).forEach(e=>{e?.isTexture&&e.dispose()}),l.isShaderMaterial){let e=l.uniforms;e&&Object.values(e).forEach(t=>{let n=t.value;n?.isTexture&&n.dispose()})}l.dispose()}function nr(l){let e=l.geometry;e&&e.dispose();let t=l.skeleton;t&&t.dispose();let n=l.material;n&&(Array.isArray(n)?n.forEach(i=>gn(i)):n&&gn(n))}function ir(l){l.traverse(nr)}function rr(l){let e=new Map;l.traverse(t=>{if(t.type!=="SkinnedMesh")return;let n=t,r=n.geometry.getAttribute("skinIndex"),s=e.get(r);if(!s){let a=[],u=[],d={},c=r.array;for(let h=0;h<c.length;h++){let p=c[h];d[p]===void 0&&(d[p]=a.length,a.push(n.skeleton.bones[p]),u.push(n.skeleton.boneInverses[p])),c[h]=d[p]}r.copyArray(c),r.needsUpdate=!0,s=new o.Skeleton(a,u),e.set(r,s)}n.bind(s,new o.Matrix4)})}function or(l){let e=new Map;l.traverse(t=>{var n,i,r,s;if(!t.isMesh)return;let a=t,u=a.geometry,d=u.index;if(d==null)return;let c=e.get(u);if(c!=null){a.geometry=c;return}let h=new o.BufferGeometry;h.name=u.name,h.morphTargetsRelative=u.morphTargetsRelative,u.groups.forEach(m=>{h.addGroup(m.start,m.count,m.materialIndex)}),h.boundingBox=(i=(n=u.boundingBox)===null||n===void 0?void 0:n.clone())!==null&&i!==void 0?i:null,h.boundingSphere=(s=(r=u.boundingSphere)===null||r===void 0?void 0:r.clone())!==null&&s!==void 0?s:null,h.setDrawRange(u.drawRange.start,u.drawRange.count),h.userData=u.userData,e.set(u,h);let p=[],f=[];{let m=d.array,_=new m.constructor(m.length),v=0;for(let M=0;M<m.length;M++){let x=m[M],E=p[x];E==null&&(p[x]=v,f[v]=x,E=v,v++),_[M]=E}h.setIndex(new vt(_,1,!1))}Object.keys(u.attributes).forEach(m=>{let _=u.attributes[m];if(_.isInterleavedBufferAttribute)throw new Error("removeUnnecessaryVertices: InterleavedBufferAttribute is not supported");let v=_.array,{itemSize:M,normalized:x}=_,E=new v.constructor(f.length*M);f.forEach((T,y)=>{for(let R=0;R<M;R++)E[y*M+R]=v[T*M+R]}),h.setAttribute(m,new vt(E,M,x))});let g=!0;Object.keys(u.morphAttributes).forEach(m=>{h.morphAttributes[m]=[];let _=u.morphAttributes[m];for(let v=0;v<_.length;v++){let M=_[v];if(M.isInterleavedBufferAttribute)throw new Error("removeUnnecessaryVertices: InterleavedBufferAttribute is not supported");let x=M.array,{itemSize:E,normalized:T}=M,y=new x.constructor(f.length*E);f.forEach((R,P)=>{for(let S=0;S<E;S++)y[P*E+S]=x[R*E+S]}),g=g&&y.every(R=>R===0),h.morphAttributes[m][v]=new vt(y,E,T)}}),g&&(h.morphAttributes={}),a.geometry=h}),Array.from(e.keys()).forEach(t=>{t.dispose()})}function sr(l){var e;((e=l.meta)===null||e===void 0?void 0:e.metaVersion)==="0"&&(l.scene.rotation.y=Math.PI)}var X=class{constructor(){}};X.deepDispose=ir;X.removeUnnecessaryJoints=rr;X.removeUnnecessaryVertices=or;X.rotateVRM0=sr;export{K as MToonMaterial,wi as MToonMaterialDebugMode,Le as MToonMaterialLoaderPlugin,Mt as MToonMaterialOutlineWidthMode,Pt as VRM,Ht as VRMAimConstraint,Pe as VRMCore,hn as VRMCoreLoaderPlugin,me as VRMExpression,ie as VRMExpressionLoaderPlugin,ve as VRMExpressionManager,te as VRMExpressionMaterialColorBind,G as VRMExpressionMaterialColorType,_e as VRMExpressionMorphTargetBind,cr as VRMExpressionOverrideType,yt as VRMExpressionPresetName,ne as VRMExpressionTextureTransformBind,q as VRMFirstPerson,ge as VRMFirstPersonLoaderPlugin,hr as VRMFirstPersonMeshAnnotationType,_t as VRMHumanBoneList,fr as VRMHumanBoneName,oi as VRMHumanBoneParentMap,Me as VRMHumanoid,Ee as VRMHumanoidHelper,Re as VRMHumanoidLoaderPlugin,_n as VRMLoaderPlugin,ye as VRMLookAt,Q as VRMLookAtBoneApplier,oe as VRMLookAtExpressionApplier,St as VRMLookAtHelper,Se as VRMLookAtLoaderPlugin,we as VRMLookAtRangeMap,pr as VRMLookAtTypeName,Ae as VRMMetaLoaderPlugin,se as VRMNodeConstraint,ee as VRMNodeConstraintHelper,be as VRMNodeConstraintLoaderPlugin,bt as VRMNodeConstraintManager,li as VRMRequiredHumanBoneName,Ot as VRMRollConstraint,Ut as VRMRotationConstraint,Ve as VRMSpringBoneCollider,Ce as VRMSpringBoneColliderHelper,Ue as VRMSpringBoneColliderShape,Oe as VRMSpringBoneColliderShapeCapsule,Ne as VRMSpringBoneColliderShapeSphere,Bt as VRMSpringBoneJoint,Dt as VRMSpringBoneJointHelper,Fe as VRMSpringBoneLoaderPlugin,De as VRMSpringBoneManager,X as VRMUtils};
/*! Bundled license information:

@pixiv/three-vrm/lib/three-vrm.module.js:
  (*!
   * @pixiv/three-vrm v2.1.3
   * VRM file loader for three.js.
   *
   * Copyright (c) 2019-2024 pixiv Inc.
   * @pixiv/three-vrm is distributed under MIT License
   * https://github.com/pixiv/three-vrm/blob/release/LICENSE
   *)
  (*!
   * @pixiv/three-vrm-core v2.1.3
   * The implementation of core features of VRM, for @pixiv/three-vrm
   *
   * Copyright (c) 2020-2024 pixiv Inc.
   * @pixiv/three-vrm-core is distributed under MIT License
   * https://github.com/pixiv/three-vrm/blob/release/LICENSE
   *)

@pixiv/three-vrm/lib/three-vrm.module.js:
  (*!
   * @pixiv/three-vrm-materials-mtoon v2.1.3
   * MToon (toon material) module for @pixiv/three-vrm
   *
   * Copyright (c) 2020-2024 pixiv Inc.
   * @pixiv/three-vrm-materials-mtoon is distributed under MIT License
   * https://github.com/pixiv/three-vrm/blob/release/LICENSE
   *)

@pixiv/three-vrm/lib/three-vrm.module.js:
  (*!
   * @pixiv/three-vrm-materials-hdr-emissive-multiplier v2.1.3
   * Support VRMC_hdr_emissiveMultiplier for @pixiv/three-vrm
   *
   * Copyright (c) 2020-2024 pixiv Inc.
   * @pixiv/three-vrm-materials-hdr-emissive-multiplier is distributed under MIT License
   * https://github.com/pixiv/three-vrm/blob/release/LICENSE
   *)

@pixiv/three-vrm/lib/three-vrm.module.js:
  (*!
   * @pixiv/three-vrm-materials-v0compat v2.1.3
   * VRM0.0 materials compatibility layer plugin for @pixiv/three-vrm
   *
   * Copyright (c) 2020-2024 pixiv Inc.
   * @pixiv/three-vrm-materials-v0compat is distributed under MIT License
   * https://github.com/pixiv/three-vrm/blob/release/LICENSE
   *)

@pixiv/three-vrm/lib/three-vrm.module.js:
  (*!
   * @pixiv/three-vrm-node-constraint v2.1.3
   * Node constraint module for @pixiv/three-vrm
   *
   * Copyright (c) 2020-2024 pixiv Inc.
   * @pixiv/three-vrm-node-constraint is distributed under MIT License
   * https://github.com/pixiv/three-vrm/blob/release/LICENSE
   *)

@pixiv/three-vrm/lib/three-vrm.module.js:
  (*!
   * @pixiv/three-vrm-springbone v2.1.3
   * Spring bone module for @pixiv/three-vrm
   *
   * Copyright (c) 2020-2024 pixiv Inc.
   * @pixiv/three-vrm-springbone is distributed under MIT License
   * https://github.com/pixiv/three-vrm/blob/release/LICENSE
   *)
*/
//# sourceMappingURL=three-vrm.mjs.map