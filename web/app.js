'use strict';
const $ = id => document.getElementById(id);
const examples = {
  qa: '用一句话解释什么是机器学习。',
  summary: '请用三点总结以下会议记录：项目已完成需求分析。下一步实现模型路由与统计。周五进行测试和演示。',
  code: '请用 Python 实现二分查找，说明时间复杂度，并给出空数组和找不到元素的测试用例。',
  long: '请总结这份项目周报：\n' + '本周完成课程项目的需求分析、接口设计与测试。模型路由需要综合考虑任务类型、难度和输入长度。下一阶段将验证异常处理与缓存效果。\n'.repeat(42)
};
const labels = {eco:'轻量',balanced:'均衡',reasoner:'推理',qa:'问答',summary:'摘要',code:'代码',reasoning:'推理'};
let latest = null;
const count = () => $('charCount').textContent = `${$('prompt').value.length} / 24000`;
document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => {
  $('prompt').value = examples[button.dataset.example];
  document.querySelectorAll('[data-example]').forEach(x => x.classList.toggle('chosen', x === button));
  count();
}));
$('prompt').addEventListener('input', count);

const payload = () => ({prompt:$('prompt').value,preference:$('preference').value,max_tokens:Number($('maxTokens').value),use_cache:$('cache').checked,confirm_live:true});
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result = await response.json();
  if (!result.ok) { const err = new Error(`${result.error.code}：${result.error.message}`); err.result=result; throw err; }
  return result;
}
function showError(error) {$('error').hidden=false; $('error').textContent=error.message || String(error);}
function element(tag, text) {const el=document.createElement(tag); el.textContent=text; return el;}
function render(result) {
  latest=result; $('download').disabled=false; const route=result.route;
  $('jsonOutput').textContent=JSON.stringify(result,null,2);
  document.querySelectorAll('.model').forEach(el=>el.classList.toggle('selected', el.id===`tier-${route.tier}`));
  $('resultBadge').textContent = result.cache_hit ? '缓存命中 · 0 次新调用' : result.answer ? (result.incomplete?'输出未完成':'真实调用完成') : '仅预览 · 0 次调用';
  const box=$('routeDetails'); box.replaceChildren();
  box.append(element('strong',`${route.task_label} → ${route.model.replace('openai/','')} · ${route.thinking==='enabled'?'思考开启':'思考关闭'}`));
  const ul=document.createElement('ul'); route.reasons.forEach(reason=>ul.append(element('li',reason))); box.append(ul);
  const m=element('div',''); m.className='route-metrics';
  const texts=result.answer ? [`输入 ${result.input_tokens ?? '未知'} / 输出 ${result.output_tokens ?? '未知'} Token`,`请求 ${result.latency_ms} ms`,`模型调用 ${result.model_latency_ms} ms`,`费用估算 ${result.currency} ${result.cost===null?'未知':result.cost.toFixed(6)}`] : [`输出上限 ${route.max_output_tokens} Token`,`预算估计 ${route.currency} ${route.estimated_cost_at_output_limit.toFixed(6)}`];
  texts.forEach(t=>m.append(element('span',t))); box.append(m);
  $('answer').textContent=result.warning ? `${result.warning}\n${result.answer}` : result.answer || `路由预览已完成。${route.pricing_note}。\n点击“发送并执行”调用真实模型。`;
}
async function execute(action) {
  $('error').hidden=true; latest=null; $('download').disabled=true; $('answer').textContent='正在处理当前任务…'; $('routeDetails').replaceChildren(); $('jsonOutput').textContent='{}'; document.querySelectorAll('.model').forEach(el=>el.classList.remove('selected')); $('run').disabled=$('preview').disabled=true;
  const started=Date.now(); const timer=setInterval(()=>{$('resultBadge').textContent=`正在调用 · ${Math.floor((Date.now()-started)/1000)} 秒`;},1000); $('resultBadge').textContent='处理中…';
  try {render(await api(`/api/${action}`,payload()));}
  catch(error){showError(error); $('answer').textContent='本次请求未完成，请根据错误提示调整后重试。'; $('resultBadge').textContent='请求失败'; if(error.result){latest=error.result;$('jsonOutput').textContent=JSON.stringify(latest,null,2);}}
  finally {clearInterval(timer); $('run').disabled=$('preview').disabled=false; await refresh();}
}
async function refresh(){
  try {
    const state=await api('/api/stats');
    const groups=state.groups, sum=key=>groups.reduce((v,g)=>v+(g[key]||0),0);
    $('statRequests').textContent=sum('requests'); $('statCalls').textContent=sum('provider_calls'); $('statCache').textContent=sum('cache_hits'); $('statTokens').textContent=(sum('input_tokens')+sum('output_tokens')).toLocaleString();
    $('statCost').textContent=groups.length>1?groups.map(g=>`${g.currency} ${g.known_cost.toFixed(6)}`).join(' / '):(groups[0]?.known_cost||0).toFixed(6);
    $('costLabel').textContent='用量估算成本'+' · '+(groups.length>1?'多币种':groups[0]?.currency||'USD');
    $('tokenTag').textContent='（服务返回）';
    $('statsNote').textContent=`${state.note} 未知费用请求：${sum('unknown_cost_requests')}。费用以服务商账单为准。`;
    $('history').replaceChildren();
    if(!state.recent.length){const row=element('tr','');const cell=element('td','暂无记录');cell.colSpan=7;row.append(cell);$('history').append(row);}
    state.recent.slice(0,8).forEach(r=>{const row=element('tr','');[new Date(r.created_at).toLocaleTimeString('zh-CN'),labels[r.task_type],labels[r.tier],r.status==='error'?r.error_code:r.cache_hit?'缓存命中':'调用完成',r.input_tokens===null?'未知':r.input_tokens+r.output_tokens,`${r.latency_ms} ms`,`${r.currency} ${r.cost===null?'未知':r.cost.toFixed(6)}`].forEach(t=>row.append(element('td',t)));$('history').append(row);});
  } catch(error){showError(error);}
}
$('run').onclick=()=>execute('run'); $('preview').onclick=()=>execute('plan'); $('refresh').onclick=refresh;
$('clearCache').onclick=async()=>{try{const r=await api('/api/cache/clear',{});$('resultBadge').textContent=`已清空 ${r.cleared_entries} 条缓存`;}catch(error){showError(error);}};
$('download').onclick=()=>{if(!latest)return;const url=URL.createObjectURL(new Blob([JSON.stringify(latest,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='router-result.json';a.click();URL.revokeObjectURL(url);};
async function settingsStatus(){const s=await api('/api/settings');$('connectionStatus').textContent=s.configured?'密钥已配置 · '+s.storage:'尚未配置密钥';return s;}
$('openSettings').onclick=()=>{$('settingsPanel').hidden=false;};
$('closeSettings').onclick=()=>{$('settingsPanel').hidden=true;$('apiKey').value='';};
async function settingsAction(action){
  const buttons=['saveSettings','checkSettings','clearSettings'];buttons.forEach(id=>$(id).disabled=true);
  $('settingsMessage').textContent='正在处理…';
  try{
    const data=action==='save'?{api_key:$('apiKey').value}:{};
    const result=await api(action==='save'?'/api/settings':`/api/settings/${action}`,data);
    if(action==='save'){$('apiKey').value='';latest=null;$('download').disabled=true;}
    $('settingsMessage').textContent=action==='check'?(result.missing_required_models.length?'连接成功，但缺少模型：'+result.missing_required_models.join(', '):'连接成功 · '+result.models.join(' / ')) : action==='save'?'已保存，下一次请求立即使用新密钥。':'本地密钥已移除；如设置了环境变量，将使用环境变量。';
    await settingsStatus();
  }catch(error){$('settingsMessage').textContent=error.message;}
  finally{buttons.forEach(id=>$(id).disabled=false);}
}
$('saveSettings').onclick=()=>settingsAction('save');$('checkSettings').onclick=()=>settingsAction('check');$('clearSettings').onclick=()=>settingsAction('clear');
count();refresh();settingsStatus().catch(showError);
