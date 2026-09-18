# 测试与实测报告

日期：2026-09-17；Windows / Python3.11.9 / LiteLLM1.101.0 / nanobot0.3.5。

## 自动测试

37 passed，JUnit见artifacts/test-results.xml。覆盖路由与偏好、长文本、上下文、参数边界、缓存计价/过期/容量、密钥变化隔离、usage缺失、失败与不完整回答不缓存、Windows数据库关闭、加密凭据与动态更新、错误脱敏、HTTP设置接口同源和字段限制、CLI退出码、nanobot Skill加载。自动测试无需个人API。

十条验收案例10/10通过，结果artifacts/routing-cases.json。它们是人工功能测试，不代表真实任务分布上的准确率。

## DeepSeek真实调用

artifacts/evaluation.json包含三条首轮真实结果和三条重复缓存结果。首轮路由为Flash问答、Pro摘要、Pro思考代码；全部finish_reason=stop。新增输入135、输出333 Token，估算费用USD0.00139044。三条重复请求新增API调用/Token/费用全部为0。未运行无缓存六次的付费基线。

供应商返回了输入缓存命中/未命中分项，费用按公开峰谷费率估算。没有对账单做最终核销，没有将这些样例作为回答质量基准。

## Runtime链路

artifacts/nanobot-verification.json：真实SkillsLoader与ExecTool，工作区限制开启，调用脚本获得DeepSeek回答。

artifacts/nanobot-agent-verification.txt：完整自然语言Agent实测，读取Skill、写临时任务、执行CLI，摘要路由至Pro；新增一次任务模型调用，36输入/6输出Token。编排层费用另计，单次成功不证明任意自然语言的规划正确性。

nanobot 0.3.5要求会话目录在工作区之外。启动器已将不含Key的公开配置放入用户应用数据目录，密钥仅注入子进程环境，解决该版本的初始化约束。

## 网页与视频

artifacts/ui-check.json与mobile-check.json记录配置页可见、密码框不回显、无效Key拒绝、关闭清空、三类预览、空输入及布局检查。视频34.76秒、H.264、1440×1080、25fps，内嵌中文字幕。三次生成全部来自真实API，另有一次本地缓存命中；recorded-live-calls.json与视频为同批证据。

视频与evaluation.json来自不同批次，回答与Token可能不同。画面抽帧检查覆盖设置、摘要、代码、缓存与统计。密钥没有进入画面。

## 验证边界

已验证本地Windows环境、真实模型和一条完整Agent流程。其他系统CI配置已提供，需推送后查看远端执行结果。没有声称网络稳定性、服务限流、模型质量、账单或多用户并发均已充分验证。
