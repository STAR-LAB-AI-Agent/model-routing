(async()=>{
const $=id=>document.getElementById(id);
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const ready=async()=>{for(let i=0;i<300;i++){if(!$('run').disabled)return;await pause(100);}throw Error('timeout');};
const checks=[];
$('openSettings').click();checks.push({name:'settings visible',pass:!$('settingsPanel').hidden});
checks.push({name:'key never echoed',pass:$('apiKey').type==='password'&&$('apiKey').value===''});
$('apiKey').value='invalid';$('saveSettings').click();
for(let i=0;i<100&&$('saveSettings').disabled;i++)await pause(50);
checks.push({name:'invalid key rejected',pass:$('settingsMessage').textContent.includes('INVALID_KEY')});
$('closeSettings').click();
checks.push({name:'key field cleared on close',pass:$('apiKey').value===''});
for(const [sample,tier] of [['qa','eco'],['summary','balanced'],['code','reasoner']]){
 document.querySelector('[data-example="'+sample+'"]').click();$('preview').click();await ready();
 const r=JSON.parse($('jsonOutput').textContent);checks.push({name:sample+' route',pass:r.route.tier===tier&&r.provider_calls===0});
}
$('prompt').value='';$('run').click();await ready();checks.push({name:'empty blocked',pass:$('error').textContent.includes('EMPTY_PROMPT')});
checks.push({name:'no horizontal overflow',pass:document.documentElement.scrollWidth<=innerWidth});
return {ok:checks.every(x=>x.pass),checks};
})()
