(async function loadProviderStatus(){
  const badge=document.querySelector("#provider-status");
  if(!badge)return;
  try{
    const response=await fetch("/api/health");
    const health=await response.json();
    if(!response.ok)throw new Error("health request failed");
    badge.lastChild.textContent=health.provider==="deepseek"
      ? ` DeepSeek · ${health.model}`
      : " 本地模拟";
  }catch(error){
    badge.lastChild.textContent=" Provider 状态未知";
  }
})();
