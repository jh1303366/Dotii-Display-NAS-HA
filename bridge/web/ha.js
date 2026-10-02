/* Native-screen companion: only the NAS talks to Home Assistant. */
(() => {
  const $ = id => document.getElementById(id);
  const ui = {loaded:false, entities:[], page:0, selected:null, chooseMode:false, busy:false, ha:{entities:[]}, enabled:false, revision:0};
  const modes = {off:'关机',cool:'制冷',heat:'制热',auto:'自动',dry:'除湿',fan_only:'送风',heat_cool:'冷热'};
  const el = (tag, text, cls) => {const n=document.createElement(tag); if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  async function api(path, body) {
    const response = await fetch('/api/v1/admin/ha/'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
    const data=await response.json();if(!response.ok)throw new Error(data.error||'请求失败');return data;
  }
  function note(text) {$('ha-note').textContent=text;}
  function display(entity) {
    if(!entity.available)return '不可用';
    if(entity.domain==='climate')return (modes[entity.state]||entity.state)+(entity.temperature==null?'':` · ${entity.temperature}°`);
    if(['light','switch','fan'].includes(entity.domain))return entity.state==='on'?'已开启':'已关闭';
    return entity.state+entity.unit;
  }
  async function command(entity, action, value) {
    if(ui.busy)return;ui.busy=true;render();note('正在发送指令…');
    try {const data=await api('command',{slot:entity.slot,revision:ui.revision,action,value});if(data.ha.revision===ui.revision)ui.ha=data.ha;note('指令已发送，状态以设备反馈为准');}
    catch(error){note(error.message);}
    finally{ui.busy=false;render();}
  }
  function button(text, fn, cls='') {const b=el('button',text,cls);b.type='button';b.addEventListener('click',fn);return b;}
  const artMetadata={"weather": {"ref": 1, "crop": [645, 272, 797, 387], "width": 86, "height": 65, "imageWidth": 1448, "imageHeight": 1086}, "ha_home": {"ref": 1, "crop": [640, 719, 799, 862], "width": 70, "height": 63, "imageWidth": 1448, "imageHeight": 1086}, "wifi": {"ref": 1, "crop": [479, 259, 548, 309], "width": 35, "height": 26, "imageWidth": 1448, "imageHeight": 1086}, "leaf": {"ref": 1, "crop": [941, 331, 1005, 395], "width": 32, "height": 32, "imageWidth": 1448, "imageHeight": 1086}, "bulb": {"ref": 3, "crop": [891, 122, 924, 157], "width": 31, "height": 33, "imageWidth": 1536, "imageHeight": 1024}, "snow": {"ref": 3, "crop": [1213, 99, 1238, 129], "width": 30, "height": 36, "imageWidth": 1536, "imageHeight": 1024}, "car": {"ref": 2, "crop": [375, 280, 842, 482], "width": 216, "height": 94, "imageWidth": 1254, "imageHeight": 1254}, "battery": {"ref": 2, "crop": [351, 540, 526, 640], "width": 74, "height": 42, "imageWidth": 1254, "imageHeight": 1254}, "nas": {"ref": 3, "crop": [195, 765, 248, 816], "width": 52, "height": 50, "imageWidth": 1536, "imageHeight": 1024}, "mode_cool": {"ref": 3, "crop": [1140, 220, 1178, 255], "width": 36, "height": 34, "imageWidth": 1536, "imageHeight": 1024}, "mode_heat": {"ref": 3, "crop": [1190, 224, 1215, 251], "width": 28, "height": 30, "imageWidth": 1536, "imageHeight": 1024}, "mode_fan": {"ref": 3, "crop": [1232, 224, 1259, 251], "width": 30, "height": 30, "imageWidth": 1536, "imageHeight": 1024}, "mode_dry": {"ref": 3, "crop": [1270, 223, 1294, 251], "width": 26, "height": 30, "imageWidth": 1536, "imageHeight": 1024}};
  const sectionNames=['我的家','灯光控制','空调控制','室内环境','扫地机器人','车辆状态','NAS 状态','其他设备'];
  const role = r => (ui.ha.entities||[]).find(e=>e.role===r);
  const val = (e,suffix='') => e&&e.available ? e.state+suffix : '--';
  function ring(root,x,y,size,start,end,value,color,width=16){
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${size} ${size}`);svg.classList.add('ha-ring');Object.assign(svg.style,{left:x+'px',top:y+'px',width:size+'px',height:size+'px'});
    const radius=(size-width)/2,center=size/2;let span=(end-start+360)%360;const defs=document.createElementNS(svg.namespaceURI,'defs'),g=document.createElementNS(svg.namespaceURI,'linearGradient');const gid='ha-grad-'+x+'-'+y+'-'+start;g.id=gid;g.setAttribute('x1','0%');g.setAttribute('y1','100%');g.setAttribute('x2','100%');g.setAttribute('y2','0%');for(const [offset,c] of [['0%','#438fff'],['100%','#bae8ff']]){const stop=document.createElementNS(svg.namespaceURI,'stop');stop.setAttribute('offset',offset);stop.setAttribute('stop-color',c);g.append(stop);}defs.append(g);svg.append(defs);
    const path=(from,to)=>{const pt=a=>[center+radius*Math.cos(a*Math.PI/180),center+radius*Math.sin(a*Math.PI/180)];const p=pt(from),q=pt(to);return `M ${p[0]} ${p[1]} A ${radius} ${radius} 0 ${to-from>180?1:0} 1 ${q[0]} ${q[1]}`;};
    for(const [v,c] of [[100,'#202b39'],[Math.max(0,Math.min(100,value)),color]]){if(v<=0)continue;const p=document.createElementNS(svg.namespaceURI,'path');p.setAttribute('d',path(start,start+span*v/100));p.setAttribute('fill','none');p.setAttribute('stroke',c==='#202b39'?c:`url(#${gid})`);p.setAttribute('stroke-width',width);p.setAttribute('stroke-linecap','round');svg.append(p);}root.append(svg);
  }
  function render() {
    const root=$('ha-screen');root.replaceChildren();const entities=ui.ha.entities||[];const connected=ui.enabled&&ui.ha.connected;
    const text=(t,x,y,w,cls='')=>{const n=el('div',t,'ha-position '+cls);Object.assign(n.style,{left:x+'px',top:y+'px',width:w+'px'});root.append(n);return n;};
    const btn=(t,x,y,w,h,fn,disabled=false)=>{const b=button(t,fn,'ha-round-button');Object.assign(b.style,{left:x+'px',top:y+'px',width:w+'px',height:h+'px'});b.disabled=disabled;root.append(b);return b;};
    const art=(name,x,y)=>{const m=artMetadata[name],scale=m.width/(m.crop[2]-m.crop[0]);const n=el('div',undefined,'ha-reference-art');Object.assign(n.style,{left:x+'px',top:y+'px',width:m.width+'px',height:m.height+'px',backgroundImage:`url(/ha-reference-${m.ref}.png)`,backgroundSize:`${m.imageWidth*scale}px ${m.imageHeight*scale}px`,backgroundPosition:`${-m.crop[0]*scale}px ${-m.crop[1]*scale}px`});root.append(n);return n;};
    const page=p=>{ui.page=(p+8)%8;ui.selected=null;ui.chooseMode=false;ui.listPage=0;render();};
    if(ui.selected==null&&(ui.page===1||ui.page===2))ui.selected=entities.find(e=>e.domain===(ui.page===1?'light':'climate'))?.slot??null;
    const selected=entities.find(e=>e.slot===ui.selected);const blocked=e=>!connected||ui.busy||!e?.available;
    const top=t=>{text(t,106,46,254,'ha-section-title');btn('‹',69,45,44,44,()=>selected?page(0):page(0));};
    const outer=(a,b,c)=>{ring(root,15,15,436,190,255,a,'#69c9ff',14);ring(root,15,15,436,105,175,b,'#4c91ff',14);ring(root,15,15,436,285,75,c,'#63dcfa',14);};
    const nav=()=>{btn('‹',107,359,48,48,()=>page(ui.page-1));btn('›',311,359,48,48,()=>page(ui.page+1));text(`${ui.page+1} / 8`,171,371,124,'ha-muted');};
    if(selected){
      top(selected.label+(connected?"":" · 离线"));const climate=selected.domain==='climate',light=selected.domain==='light',toggle=light||selected.domain==='switch',pct=selected.actions.includes(light?'brightness':'percentage');
      let v=climate?(selected.temperature-selected.min_temp)*100/(selected.max_temp-selected.min_temp):light?pct?(selected.brightness??0)*100/255:selected.state==='on'?100:0:selected.percentage??0;
      ring(root,103,92,260,135,405,v,'#69c9ff',17);if(climate)art('snow',218,132);else if(light)art('bulb',218,132);else text('◉',183,129,100,'ha-glyph');
      text(climate?(selected.temperature??'--')+'°':toggle&&!pct?(selected.state==='on'?'已开启':'已关闭'):Math.round(v)+'%',126,185,214,'ha-hero');text(climate?(modes[selected.state]||selected.state):toggle?pct?'亮度':'开关控制':selected.state==='off'?'已关闭':'风速',130,266,206,'ha-muted');
      const group=entities.filter(e=>e.domain===selected.domain),idx=group.findIndex(e=>e.slot===selected.slot);const adjacent=d=>{ui.selected=group[(idx+group.length+d)%group.length].slot;ui.chooseMode=false;render();};if(!climate){btn('‹',64,226,48,48,()=>adjacent(-1),group.length<2);btn('›',354,226,48,48,()=>adjacent(1),group.length<2);}
      if(climate){const choose=btn('',127,45,228,44,()=>adjacent(1),group.length<2);choose.style.background='transparent';choose.style.border='0';choose.setAttribute('aria-label','切换空调');choose.title='点击名称切换空调';}
      const disabled=blocked(selected);btn('⏻',climate?209:200,climate?295:314,climate?48:66,climate?48:66,()=>command(selected,climate?'mode':selected.state==='off'?'turn_on':'turn_off',climate?'off':''),disabled||climate&&!selected.hvac_modes.includes('off'));
      if(climate||pct){for(const d of [-1,1]){const target=climate?Math.round((Number(selected.temperature)+d*selected.temp_step)*10)/10:Math.max(0,Math.min(100,Math.round(v)+d*10));btn(d<0?'−':'+',climate?(d<0?64:354):(d<0?123:293),climate?226:322,climate?48:52,climate?48:52,()=>command(selected,climate?'temperature':light?'brightness':'percentage',target),disabled||climate&&(!selected.actions.includes('temperature')||target<selected.min_temp||target>selected.max_temp));}}
      if(climate){['cool','heat','fan_only','dry'].forEach((m,i)=>{const b=btn('',114+i*62,354,48,48,()=>command(selected,'mode',m),disabled||!selected.hvac_modes.includes(m));b.title=modes[m];art('mode_'+(m==='fan_only'?'fan':m),120+i*62,363);});btn('模式',174,405,118,30,()=>{ui.chooseMode=true;render();},disabled||!selected.actions.includes('mode'));if(ui.chooseMode){const picker=el('div',undefined,'ha-dial-modes');for(const m of selected.hvac_modes)picker.append(button(modes[m]||m,()=>{ui.chooseMode=false;command(selected,'mode',m);},'ha-mode-choice'));const cancel=button('取消',()=>{ui.chooseMode=false;render();},'ha-mode-choice');picker.append(cancel);root.append(picker);}}
    }else if(ui.page===0){
      const lights=entities.filter(e=>e.domain==='light'),on=lights.filter(e=>e.state==='on').length,available=entities.filter(e=>e.available).length,percent=entities.length?Math.round(available*100/entities.length):0;outer(connected?percent:0,lights.length?on*100/lights.length:0,90);
      art('wifi',110,104);text('在线率',68,139,116,'ha-muted');text(connected?percent+'%':'离线',68,166,116,'ha-stat');text(new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false}),111,212,244,'ha-clock');art('bulb',107,278);text('灯光',68,310,110,'ha-muted');text(`${on}/${lights.length}`,68,337,110,'ha-stat');art('leaf',350,146);text('空气',322,185,94,'ha-muted');text(role('pm25')?.available?(Number(role('pm25').state)<=35?'优':Number(role('pm25').state)<=75?'良':'偏高'):'--',327,211,80,'ha-air-quality');text('PM2.5 '+val(role('pm25')),303,255,116,'ha-muted');art('weather',190,112);const weather=entities.find(e=>e.domain==='weather');text(val(role('temperature'),'°C')+'  '+(({rainy:'下雨',sunny:'晴天',cloudy:'多云'})[weather?.state]||'多云'),160,285,162);text('湿度 '+val(role('humidity'),'%'),152,313,166,'ha-muted');if(connected){btn('',199,357,70,63,()=>page(1));art('ha_home',199,357);}
    }else if(ui.page===1||ui.page===2||ui.page===7){
      top(sectionNames[ui.page]);const group=entities.filter(e=>ui.page===1?e.domain==='light':ui.page===2?e.domain==='climate':['fan','switch'].includes(e.domain));const pages=Math.max(1,Math.ceil(group.length/4));ui.listPage=Math.min(ui.listPage||0,pages-1);
      group.slice(ui.listPage*4,ui.listPage*4+4).forEach((e,i)=>{const b=btn('',91+i%2*149,109+Math.floor(i/2)*112,135,102,()=>{ui.selected=e.slot;render();},!e.available);b.classList.add('ha-device-tile');b.append(el('strong',e.label),el('small',display(e)));});
      if(!group.length)text('暂未添加设备',80,202,306,'ha-muted');btn('‹',119,343,44,44,()=>{ui.listPage--;render();},ui.listPage===0);btn('›',303,343,44,44,()=>{ui.listPage++;render();},ui.listPage>=pages-1);text(`${ui.listPage+1} / ${pages}`,179,353,108,'ha-muted');
    }else if(ui.page===3){top('室内环境');for(const [i,r] of ['temperature','humidity','pm25'].entries()){text(['♨','◌','❧'][i],87,113+i*82,54,'ha-glyph');text(['客厅温度','客厅湿度','空气 PM2.5'][i],160,113+i*82,208,'ha-muted');text(val(role(r),['°C','%',''][i]),160,138+i*82,208,'ha-stat');}nav();
    }else if(ui.page===4){top('扫地机器人');const e=entities.find(e=>e.domain==='vacuum');const battery=role('vacuum_battery');ring(root,108,90,250,135,405,Number(battery?.state)||0,'#69c9ff',17);text('◉',182,130,102,'ha-glyph');text(val(battery,'%'),134,190,198,'ha-hero');text(({docked:'充电座待机',cleaning:'清扫中',paused:'已暂停',returning:'返回充电座',error:'故障'})[e?.state]||'不可用',110,266,246,'ha-muted');for(const [i,a] of ['start','pause','stop','return_to_base'].entries())btn(['▶','Ⅱ','■','⌂'][i],104+i*68,315,54,54,()=>command(e,a,''),blocked(e)||!e?.actions?.includes(a));text('开始 / 暂停 / 停止 / 回充',79,380,308,'ha-muted');
    }else if(ui.page===5){const battery=role('vehicle_battery');outer(Number(battery?.state)||0,0,80);art('car',125,94);art('battery',115,204);text(val(battery,'%'),185,195,206,'ha-hero ha-vehicle-percent');text(val(role('vehicle_range'),' km'),130,268,206);text(role('vehicle_lock')?.state==='on'?'已锁车':'锁车 --',70,318,110,'ha-muted');text(role('vehicle_charging')?.state==='Charging'?'充电中':'未充电',180,318,110,'ha-muted');text(val(role('vehicle_temperature'),'°C'),290,318,108,'ha-muted');text(role('vehicle_status')?.state==='offline'?'车辆离线 · 最近数据':'车辆状态 · 只读',92,361,282,'ha-blue');
    }else if(ui.page===6){top('NAS 状态');art('nas',207,97);for(const [i,r] of ['nas_cpu','nas_memory','nas_temperature'].entries()){text(['CPU','内存','温度'][i],94,169+i*62,110,'ha-muted');text(val(role(r),['%','%','°C'][i]),224,169+i*62,145);}nav();}
    const footer=selected?'':ui.busy&&ui.page!==0?'正在发送…':connected?'':'离线 · 暂停控制';text(footer,80,413,306,'ha-small');
    const dots=el('div',undefined,'ha-section-dots');for(let i=0;i<8;i++){const dot=button('',()=>page(i),i===ui.page?'active':'');dot.title=sectionNames[i];dot.setAttribute('aria-label',sectionNames[i]);dots.append(dot);}root.append(dots);
  }
  function configRows() {
    $('ha-entities').replaceChildren();
    ui.entities.forEach((item,i)=>{const row=el('div',undefined,'ha-config-row');const input=el('input');input.value=item.label;input.maxLength=10;input.setAttribute('aria-label','卡片名称');input.addEventListener('input',()=>item.label=input.value);row.append(input);
      const up=button('↑',()=>{[ui.entities[i-1],ui.entities[i]]=[ui.entities[i],ui.entities[i-1]];configRows();});up.disabled=i===0;const down=button('↓',()=>{[ui.entities[i+1],ui.entities[i]]=[ui.entities[i],ui.entities[i+1]];configRows();});down.disabled=i===ui.entities.length-1;
      row.append(up,down,button('×',()=>{ui.entities.splice(i,1);configRows();}),el('small',item.entity_id));$('ha-entities').append(row);});
  }
  window.renderHA = overview => {
    const incoming=overview.snapshot?.ha||{entities:[]};if(incoming.revision!==ui.revision){ui.selected=null;ui.chooseMode=false;ui.page=0;}ui.ha=incoming;ui.revision=ui.ha.revision;ui.enabled=!!overview.modules?.find(x=>x.id==='ha')?.enabled;
    if(!ui.loaded){const config=overview.ha_config||{};$('ha-url').value=config.url||'http://192.168.1.12:8123';ui.entities=(config.entities||[]).map(x=>({...x}));ui.loaded=true;configRows();}
    if(!state.moduleSaving.ha)$('ha-enabled').checked=ui.enabled;
    $('ha-nav-state').textContent=!ui.enabled?'已关闭':ui.ha.connected?'在线':'离线';
    if(!ui.busy)note(ui.ha.error||ui.ha.command_note||'状态每 5 秒刷新');render();
  };
  $('ha-enabled').addEventListener('change',e=>updateModule('ha',e.target.checked));
  $('ha-form').addEventListener('submit',async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await api('config',{url:$('ha-url').value,token:$('ha-token').value});$('ha-token').value='';note('连接已保存，点击查找设备');}catch(error){note(error.message);}finally{b.disabled=false;}});
  $('ha-discover').addEventListener('click',async e=>{e.target.disabled=true;try{const data=await api('entities');$('ha-entity-select').replaceChildren(el('option','请选择设备'));$('ha-entity-select').firstChild.value='';data.entities.sort((a,b)=>a.label.localeCompare(b.label,'zh')).forEach(x=>{const option=el('option',x.label+' · '+x.entity_id);option.value=x.entity_id;option.dataset.label=x.label;$('ha-entity-select').append(option);});note(`找到 ${data.entities.length} 个设备`);}catch(error){note(error.message);}finally{e.target.disabled=false;}});
  $('ha-add').addEventListener('click',()=>{const select=$('ha-entity-select');if(!select.value)return;if(ui.entities.length>=32){note('最多 32 个设备');return;}if(ui.entities.some(x=>x.entity_id===select.value)){note('这个设备已经添加');return;}ui.entities.push({entity_id:select.value,label:select.selectedOptions[0].dataset.label.slice(0,10)});configRows();});
  $('ha-save-entities').addEventListener('click',async e=>{e.target.disabled=true;try{await api('config',{entities:ui.entities});note('卡片已保存');}catch(error){note(error.message);}finally{e.target.disabled=false;}});
  if(state.overview)window.renderHA(state.overview);
})();
