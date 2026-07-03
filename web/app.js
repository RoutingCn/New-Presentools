const state={project:null,analysis:null,proposal:null,selected:null,comments:[],htmlPreview:null};
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const api={
  async request(method,path,body){
    const response=await fetch(path,{method,headers:body?{"Content-Type":"application/json"}:{},body:body?JSON.stringify(body):undefined});
    const value=await response.json();
    if(!response.ok)throw new Error(value.error||"请求失败");
    return value;
  },
  get(path){return this.request("GET",path)},
  post(path,body={}){return this.request("POST",path,body)}
};

function toast(message,error=false){
  const el=$("#toast"); el.textContent=message; el.classList.toggle("error",error); el.classList.add("show");
  clearTimeout(toast.timer); toast.timer=setTimeout(()=>el.classList.remove("show"),2600);
}
function busy(button,on,text="处理中…"){
  if(!button)return;
  if(on){button.dataset.text=button.textContent;button.textContent=text;button.disabled=true}
  else{button.textContent=button.dataset.text||button.textContent;button.disabled=false}
}
function safe(value){
  const el=document.createElement("span");el.textContent=value??"";return el.innerHTML;
}
function stageNumber(stage){return {contract:0,analysis:1,structure:2,script:3,locked:4}[stage]??0}
function flowState(){
  const p=state.project;if(!p)return ["任务契约","填写主题并创建项目","主题、受众和表达目标清楚"];
  const nodes=p.content_nodes||[],hasContent=nodes.some(n=>n.kind!=="script"),hasScript=nodes.some(n=>n.kind==="script"),pending=state.proposal?.status==="pending";
  if(p.stage==="locked")return ["HTML 锁定版已生成","查看、下载或回到记忆复盘","锁定版不直接覆盖，全量版仍保留"];
  if(pending)return ["总控提案待审","批准写入全量版，或退回继续讨论","提案只会在批准后改变全量内容"];
  if(!hasContent)return ["深度分析未写入","启动分析并审核总控提案","先形成内容结构，再进入逐字稿"];
  if(!hasScript)return ["内容结构已形成","生成逐字稿提案，或继续提交修订意见","结构稳定后再进入讲稿层"];
  return ["逐字稿已形成","生成 HTML 锁定版","HTML 只读取内容结构，不混入逐字稿"];
}
function renderFlowBridge(){
  const bridge=$("#flow-bridge");if(!bridge)return;
  const [current,next,guard]=flowState();
  $("#bridge-current").textContent=current;$("#bridge-next").textContent=next;$("#bridge-guard").textContent=guard;
}
function setStage(stage){
  if(!state.project)return;
  state.project.stage=stage;const current=stageNumber(stage),names=["任务契约","深度分析","内容结构","逐字稿","HTML 展示"];
  $$(".step").forEach((el,i)=>{el.classList.toggle("active",i===current);el.classList.toggle("complete",i<current||stage==="locked")});
  $("#stage-count").textContent=`${current+1} / 5`;$("#stage-badge").textContent=names[current];
  $("#controller-state").textContent=stage==="locked"?"正式版已锁定":`总控：${names[current]}`;
  renderFlowBridge();
}
function renderProject(){
  const p=state.project;if(!p)return;
  $("#project-setup").classList.add("hidden");$("#project-dashboard").classList.remove("hidden");
  $("#header-title").textContent=p.title;$("#contract-audience").textContent=p.audience;$("#project-id").textContent=p.id;
  $("#workspace-kicker").textContent="ORCHESTRATION";$("#workspace-title").textContent=p.title;
  $("#save-state").textContent="事件已写入本地存储";$("#event-count").textContent=`${p.event_count||1} 条事件`;
  setStage(p.stage||"contract");renderContent();
  updateActionButtons();renderFlowBridge();
}
function renderDeliveries(){
  Object.entries(state.analysis.deliveries).forEach(([role,d])=>{
    const row=$(`[data-agent="${role}"]`);row.classList.add("complete");$("p",row).textContent=d.summary;$("em",row).textContent="交付完成";
    row.title=`${d.quality_checks.join("；")}\n不确定性：${d.uncertainties.join("；")}`;
  });
  $("#delivery-count").textContent="4 / 4 已交付";
}
function renderProposal(){
  const p=state.proposal;$("#proposal-section").classList.remove("hidden");
  $("#proposal-title").textContent=p.title;$("#proposal-rationale").textContent=p.rationale;
  $("#changes-table").innerHTML=p.changes.map((c,i)=>`<div class="change"><small>${safe(c.kind)}</small><strong>${String(i+1).padStart(2,"0")} · ${safe(c.title)}</strong><p>${safe(c.body)}</p></div>`).join("");
  renderFlowBridge();
}
function renderContent(){
  const allNodes=state.project?.content_nodes||[],nodes=allNodes.filter(n=>n.kind!=="script"),scripts=allNodes.filter(n=>n.kind==="script");if(!nodes.length)return;
  $("#content-section").classList.remove("hidden");$("#content-count").textContent=`${nodes.length} 个内容对象`;
  $("#html-section").classList.remove("hidden");
  $("#outline-list").innerHTML=nodes.map((n,i)=>`<button class="outline-item" data-id="${n.id}"><span>${String(i+1).padStart(2,"0")}</span><strong>${safe(n.title)}</strong></button>`).join("");
  $("#content-document").innerHTML=nodes.map((n,i)=>`<article class="node" data-id="${n.id}" tabindex="0"><small>§${String(i+1).padStart(2,"0")}<br>L${i*4+1}–${i*4+4}</small><span><h3>${safe(n.title)}</h3><p>${safe(n.body)}</p></span></article>`).join("");
  renderScriptDownload(scripts);
  $$("[data-id]").forEach(el=>{
    el.addEventListener("click",()=>selectNode(el.dataset.id));
    el.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" ")selectNode(el.dataset.id)});
  });
}
function renderScriptDownload(scripts){
  const box=$("#script-download");if(!box)return;
  if(!scripts.length){box.classList.add("hidden");box.innerHTML="";return}
  box.classList.remove("hidden");
  box.innerHTML='<button class="button" type="button" id="download-script">下载逐字稿</button>';
  $("#download-script").addEventListener("click",()=>downloadScript(scripts));
}
function downloadScript(scripts){
  const text=scripts.map((node,i)=>`# ${i+1}. ${cleanScriptTitle(node.title)}\n\n${node.body}`).join("\n\n---\n\n");
  const blob=new Blob([text],{type:"text/plain;charset=utf-8"});
  const url=URL.createObjectURL(blob);
  const link=document.createElement("a");
  link.href=url;link.download=`${state.project?.title||"presentation"}-script.txt`;link.click();
}
function cleanScriptTitle(title){
  return String(title||"").replace(/^逐字稿[：:]\s*/,"");
}
function selectNode(id){
  const nodes=state.project.content_nodes,node=nodes.find(n=>n.id===id);if(!node)return;
  state.selected=node;$$("[data-id]").forEach(el=>el.classList.toggle("selected",el.dataset.id===id));
  const i=nodes.indexOf(node);$("#selection-ref").textContent=`§${String(i+1).padStart(2,"0")} · ${node.title}`;
  $("#selection-copy").textContent=node.body;switchTab("comments");
}
async function refresh(){
  state.project=await api.get(`/api/projects/${state.project.id}`);
  state.project.event_count=1+(state.analysis?5:0)+(state.project.proposals?.filter(p=>p.status==="accepted").length||0)+(state.project.artifacts?.length||0);
  renderProject();
}
function updateActionButtons(){
  if(!state.project)return;
  const hasContent=state.project.content_nodes.some(node=>node.kind!=="script");
  const hasScript=state.project.content_nodes.some(node=>node.kind==="script");
  $("#generate-script").disabled=!hasContent||hasScript||state.project.stage==="locked";
  $("#lock-artifact").disabled=!hasContent||state.project.stage==="locked";
  $("#lock-html-preview").disabled=!state.htmlPreview||state.project.stage==="locked";
}
async function analyze(){
  const button=$("#analyze-topic");busy(button,true,"分析进行中…");$("#analysis-status").classList.remove("hidden");setStage("analysis");
  const messages=["拆解核心问题与边界…","资料 Agent 标记证据缺口…","内容 Agent 建立论证结构…","创意与视觉 Agent 形成表达路线…","总控正在执行质量门槛…"];
  let i=0;const timer=setInterval(()=>{$("#analysis-message").textContent=messages[Math.min(i,messages.length-1)];$("#status-progress").style.width=`${Math.min(92,18+i*18)}%`;i++},320);
  try{
    state.analysis=await api.post(`/api/projects/${state.project.id}/analyze`,{});state.proposal=state.analysis.proposal;
    renderDeliveries();renderProposal();$("#status-progress").style.width="100%";$("#analysis-message").textContent="四个 Agent 已交付，总控提案等待批准。";
    toast("深度分析已完成，等待批准总控提案。");
  }catch(error){toast(error.message,true)}
  finally{clearInterval(timer);busy(button,false);if(state.analysis)button.disabled=true}
}
async function accept(){
  const button=$("#accept-proposal");busy(button,true,"写入中…");
  try{
    await api.post(`/api/projects/${state.project.id}/proposals/${state.proposal.id}/accept`,{});
    state.proposal=null;await refresh();$("#proposal-section").classList.add("hidden");toast("提案已写入全量内容版，原提案仍保留。");
  }catch(error){toast(error.message,true)}finally{busy(button,false)}
}
async function generateScript(){
  const button=$("#generate-script");busy(button,true,"生成中…");
  try{
    state.proposal=await api.post(`/api/projects/${state.project.id}/script`,{});
    renderProposal();setStage("script");toast("逐字稿提案已生成，等待批准写入全量版。");
  }catch(error){toast(error.message,true)}finally{busy(button,false);updateActionButtons()}
}
async function lock(){
  const button=$("#lock-artifact");busy(button,true,"生成中…");
  try{
    const artifact=await api.post(`/api/projects/${state.project.id}/html/preview`,{name:"HTML 预览"});
    state.htmlPreview=artifact;openGeneratedHtml(artifact.html,state.project.title);
    $("#html-section").classList.remove("hidden");$("#lock-html-preview").disabled=false;setStage("locked");toast(`HTML 预览已生成：${artifact.id}`);
  }catch(error){toast(error.message,true);busy(button,false)}
  finally{busy(button,false);updateActionButtons()}
}
async function lockHtmlPreview(){
  if(!state.htmlPreview)return;
  const button=$("#lock-html-preview");busy(button,true,"锁定中…");
  try{
    const artifact=await api.post(`/api/projects/${state.project.id}/html/${state.htmlPreview.id}/lock`,{});
    state.htmlPreview=null;await refresh();setStage("locked");$("#lock-artifact").textContent="HTML 已锁定";await memory();toast(`HTML 已锁定：${artifact.id}`);
  }catch(error){toast(error.message,true)}finally{busy(button,false);updateActionButtons()}
}
function renderHtmlProvider(summary){
  $("#html-provider-summary").textContent=summary.provider==="ark"?`Ark · ${summary.model}`:"本地模板";
  $("#html-provider-kind").value=summary.provider==="ark"?"ark":"local-template";
  $("#html-base-url").value=summary.base_url||"";
  $("#html-model").value=summary.model||"";
  $("#html-api-key").value="";
}
async function loadHtmlProvider(){
  try{renderHtmlProvider(await api.get("/api/html-provider"))}
  catch(error){toast(error.message,true)}
}
async function saveHtmlProvider(event){
  event.preventDefault();const button=$("#save-html-provider");busy(button,true,"保存中…");
  try{
    const summary=await api.post("/api/html-provider",{
      provider:$("#html-provider-kind").value,
      base_url:$("#html-base-url").value,
      model:$("#html-model").value,
      api_key:$("#html-api-key").value,
      require_remote:$("#html-provider-kind").value==="ark"
    });
    renderHtmlProvider(summary);toast("HTML API 已保存，密钥未写入项目记忆。");
  }catch(error){toast(error.message,true)}finally{busy(button,false)}
}
async function testHtmlProvider(){
  const button=$("#test-html-provider");busy(button,true,"测试中…");
  try{const result=await api.post("/api/html-provider/test",{});toast(`HTML API 可用：${result.provider}`)}
  catch(error){toast(error.message,true)}finally{busy(button,false)}
}
function openGeneratedHtml(html,title){
  const blob=new Blob([html],{type:"text/html;charset=utf-8"});
  const url=URL.createObjectURL(blob);
  const opened=window.open(url,`html-${Date.now()}`);
  if(!opened){
    const link=document.createElement("a");
    link.href=url;link.download=`${title||"presentation"}.html`;link.click();
  }
}
async function memory(){
  if(!state.project)return;
  try{const result=await api.get(`/api/projects/${state.project.id}/memory`);$("#memory-content").textContent=result.markdown}
  catch(error){toast(error.message,true)}
}
function switchTab(name){
  $$(".tabs button").forEach(b=>b.classList.toggle("active",b.dataset.tab===name));
  $$(".tool").forEach(v=>v.classList.toggle("active",v.dataset.view===name));
  if(name==="memory")memory();
}
function handleStepNavigation(stage){
  const target={
    contract:"#project-dashboard",
    analysis:"#analysis-status",
    structure:state.proposal?"#proposal-section":"#content-section",
    script:"#script-download",
    locked:"#content-section",
    html:"#html-section",
  }[stage]||"#project-dashboard";
  const el=$(target);if(el&&!el.classList.contains("hidden"))el.scrollIntoView({behavior:"smooth",block:"start"});
  if(stage==="locked")switchTab("memory");
}
async function rejectProposal(event){
  event?.preventDefault();event?.stopImmediatePropagation();
  if(!state.proposal)return;
  const button=$("#reject-proposal");busy(button,true,"退回中...");
  try{
    await api.post(`/api/projects/${state.project.id}/proposals/${state.proposal.id}/reject`,{});
    state.proposal=null;$("#proposal-section").classList.add("hidden");await refresh();
    toast("提案已回退，未写入全量内容版。");
  }catch(error){toast(error.message,true)}finally{busy(button,false);updateActionButtons()}
}
async function submitComment(event){
  event.preventDefault();event.stopImmediatePropagation();
  const input=$("#comment-input"),text=input.value.trim();if(!text)return;
  const ref=state.selected?$("#selection-ref").textContent:"项目整体";
  const button=event.submitter||$("#comment-form button[type='submit']");
  busy(button,true,"总控修订中...");
  $("#comment-thread").insertAdjacentHTML("beforeend",`<article><strong>${safe(ref)}</strong><p>${safe(text)}</p></article>`);
  try{
    state.proposal=await api.post(`/api/projects/${state.project.id}/comments`,{text,target_id:state.selected?.id});
    renderProposal();input.value="";toast("意见已转为总控修订提案，等待批准写入全量内容版。");
  }catch(error){toast(error.message,true)}
  finally{busy(button,false);updateActionButtons()}
}

$("#project-form").addEventListener("submit",async event=>{
  event.preventDefault();const button=event.submitter;busy(button,true,"创建中…");
  try{
    state.project=await api.post("/api/projects",{title:$("#topic-input").value,audience:$("#audience-input").value,goal:$("#goal-input").value});
    renderProject();
    toast("项目已创建，正在启动深度分析。");
    await analyze();
  }catch(error){toast(error.message,true)}finally{busy(button,false)}
});
$("#analyze-topic").addEventListener("click",analyze);$("#generate-script").addEventListener("click",generateScript);$("#accept-proposal").addEventListener("click",accept);$("#reject-proposal").addEventListener("click",rejectProposal);$("#lock-artifact").addEventListener("click",lock);
$("#html-provider-form").addEventListener("submit",saveHtmlProvider);$("#test-html-provider").addEventListener("click",testHtmlProvider);$("#lock-html-preview").addEventListener("click",lockHtmlPreview);
$("#show-memory").addEventListener("click",()=>switchTab("memory"));$("#refresh-memory").addEventListener("click",memory);
$$(".tabs button").forEach(b=>b.addEventListener("click",()=>switchTab(b.dataset.tab)));
$$(".step").forEach(b=>b.addEventListener("click",()=>handleStepNavigation(b.dataset.stage)));
$("#collapse-outline").addEventListener("click",e=>{const list=$("#outline-list");list.classList.toggle("hidden");e.currentTarget.textContent=list.classList.contains("hidden")?"+":"−"});
$("#comment-form").addEventListener("submit",submitComment);
$("#comment-input").addEventListener("keydown",event=>{if(event.ctrlKey&&event.key==="Enter"){event.preventDefault();$("#comment-form").requestSubmit()}});
$("#research-search").addEventListener("click",()=>{
  const query=$("#research-query").value.trim();if(!query)return toast("请先输入搜索问题。",true);
  const result=$("#research-result");result.classList.remove("hidden");result.innerHTML=`<strong>已记录检索任务</strong><p>“${safe(query)}”将在接入检索 Provider 后同时搜索互联网与指定资料目录。当前不会生成虚构结果。</p>`;
});
loadHtmlProvider();
