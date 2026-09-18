// Real browser actions, with a paced one-minute narration overlay.
(async () => {
  const byId=id=>document.getElementById(id);
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const start=performance.now();
  const until=async(seconds,minHold=0)=>sleep(Math.max(minHold,seconds*1000-(performance.now()-start)));
  const ready=async()=>{for(let i=0;i<1300;i++){if(!byId('run').disabled)return;await sleep(100);}throw Error('Request timeout');};
  const evidence=[];
  const run=async()=>{
    byId('run').click();await ready();
    const r=JSON.parse(byId('jsonOutput').textContent);
    if(!r.ok||r.incomplete)throw Error('Generation did not complete');
    evidence.push(r);return r;
  };
  const banner=document.createElement('div');
  Object.assign(banner.style,{position:'fixed',bottom:'18px',left:'50%',transform:'translateX(-50%)',zIndex:1000,padding:'14px 22px',background:'#153a35',color:'#fff',borderRadius:'8px',fontSize:'18px',boxShadow:'0 6px 25px #0002',whiteSpace:'nowrap',display:'flex',alignItems:'center',gap:'24px'});
  const line=document.createElement('span'),clock=document.createElement('span');
  Object.assign(clock.style,{fontSize:'12px',opacity:'.7',fontVariantNumeric:'tabular-nums'});
  banner.append(line,clock);banner.setAttribute('aria-label','演示字幕');document.body.append(banner);
  const timer=setInterval(()=>{clock.textContent='演示 '+Math.floor((performance.now()-start)/1000)+' 秒';},500);
  const caption=text=>line.textContent=text;
  try {
    caption('第25题 · AI模型智能路由 / DeepSeek 真实 API');
    scrollTo(0,0);await until(4);
    byId('openSettings').click();
    caption('动态配置密钥：本机加密保存，修改后立即生效');
    byId('checkSettings').click();
    for(let i=0;i<220&&byId('checkSettings').disabled;i++)await sleep(100);
    if(!byId('settingsMessage').textContent.includes('连接成功'))throw Error('Connection test failed');
    await until(10.5,2000);byId('closeSettings').click();
    document.querySelector('[data-example="qa"]').click();byId('maxTokens').value='256';
    byId('preview').click();await ready();
    caption('01 / 简单问答 → Flash；预览展示依据，不调用模型');
    await until(16);
    const qa=await run();if(qa.cache_hit)throw Error('First request must call the real API');
    caption('真实模型回答：Token 由服务返回，费用按官方价格估算');
    await until(24,3500);
    document.querySelector('[data-example="summary"]').click();
    caption('02 / 摘要整理 → Pro 均衡档位，关闭思考');
    const summary=await run();if(summary.cache_hit)throw Error('Summary must call the real API');
    await until(33,3500);
    document.querySelector('[data-example="code"]').click();byId('maxTokens').value='2048';
    caption('03 / 代码分析 → Pro 推理档位，显式开启思考');
    const code=await run();if(code.cache_hit)throw Error('Code must call the real API');
    await until(44,3000);
    byId('answer').scrollTo({top:byId('answer').scrollHeight,behavior:'smooth'});
    caption('查看代码、复杂度与边界用例；生成的代码不会自动执行');
    await until(48,2500);
    const cached=await run();if(!cached.cache_hit)throw Error('Expected local cache hit');
    caption('04 / 相同任务命中缓存：新增调用、Token、费用均为 0');
    await until(53,3000);
    document.querySelector('.stats-panel').scrollIntoView({behavior:'smooth',block:'center'});
    caption('05 / 调用统计看板 · Skill + Script · nanobot 已验证');
    await until(57.5,3500);
    window.__recordedEvidence=evidence;
    return {ok:true,description:'Three real API calls, one cache hit, configuration check and detailed result inspection.'};
  } finally {clearInterval(timer);banner.remove();}
})();
