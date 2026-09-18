# Windows 现场验收操作指南

## 提前准备

使用当前已配置电脑时，项目路径为 D:\data\jd\260916\ai-model-router 。双击 start-demo.bat 即可。若换电脑，解压提交包，安装 Python 3.11/3.12，联网安装依赖，并在网页“API 配置”重新输入密钥。Windows 加密配置绑定用户，不应复制给他人。

确认网络、API 余额和 http://127.0.0.1:8765 页面可用。点击“API 配置 → 测试连接”，应显示 deepseek-flash 与 deepseek-v4-pro。连接测试不生成文本。不要在投屏时粘贴或朗读密钥。

报告先填写 docs/student-info.json，用 scripts/build_report.py 重建。备好 deliverables/demo.mp4，断网时可播放已录好的真实调用证据，但现场新请求需要联网。

## 约三分钟验收顺序

1. 介绍：“项目按类型、难度、长度在两个 DeepSeek 模型的三个档位之间选型，Skill 与 Script 为统一接口。”
2. 展示“API 配置”已配置状态及连接测试。说明可动态更换；现场无需更换有效密钥。
3. 点击“简单问答 → 仅预览路由”。解释 Flash、规则依据、0 次调用。再点击“发送并执行”，观察真实答案、服务返回 Token、耗时和费用估算。
4. 点击“摘要整理 → 发送并执行”。展示 Pro 均衡档位与三点摘要。
5. 点击“代码推理”，输出预算选2048或4096，再执行。展示 Pro 思考开启、最终代码与复杂度。代码只展示，不自动运行。
6. 保持任务、预算和偏好不变，再次执行。展示“缓存命中”，新增调用、Token、费用为0；原始用量仍在JSON的 original_usage。
7. 清空输入后执行，应返回 EMPTY_PROMPT，模型调用数不增加。统计只记录进入执行流程的请求，前置校验失败不计入请求表。
8. 下滚看板，解释统计只覆盖任务模型，费用是估算，nanobot 编排费用另计。
9. 展示下方命令，证明独立脚本与 Runtime 集成。

## 终端演示

在项目文件夹地址栏输入 powershell 打开终端：

```powershell
.\.venv\Scripts\python.exe skills\ai-model-router\scripts\router.py plan --prompt "证明两个连续整数乘积为偶数"
.\.venv\Scripts\python.exe scripts\verify_nanobot.py
.\.venv\Scripts\python.exe -m pytest -q
```

第二条会真实调用一次问答模型。结果中 skill_discovered=true、execution_tool=nanobot.agent.tools.shell.ExecTool、mode=live、usage_source=provider_reported。它证明 nanobot 加载与执行兼容，不声称编排模型自动选工具。

## 常见问题

- 端口占用：关闭上次服务窗口，或用 .venv\Scripts\python.exe app.py --port 8766 --open-browser。
- API_KEY_MISSING/AUTH_FAILED：在 API 配置更新并测试连接。源代码不需要改。
- UPSTREAM_ERROR/RATE_LIMITED：检查网络、余额和权限。失败不会以固定答案伪装成功。
- 输出预算耗尽：调到4096/8192重试，预算包含思考Token；会产生新费用。
- 缓存没命中：必须在同一网页服务进程内、10分钟内、内容及参数相同。独立CLI每次新进程不共享。
- 如何解释“3档2模型”：轻量用Flash；均衡与推理均用Pro，区别是thinking关闭/开启。
- 如何解释费用：以usage乘公开价格，考虑供应商输入缓存和峰谷时段，以DeepSeek账单最终核对。

## 展示完整自然语言Agent（可选加演）

执行 .venv\Scripts\python.exe scripts\run_nanobot.py --message "请使用 ai-model-router 技能，已授权真实调用及费用，请总结：需求完成，周五验收。报告模型、答案和用量。"。当前电脑已实测成功；它会额外产生编排模型费用。
