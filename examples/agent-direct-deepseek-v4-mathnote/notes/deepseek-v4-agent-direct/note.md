---
title: DeepSeek-V4 技术解读（精修版）
date: 2026-08-04
tags:
  - AI/大模型
  - DeepSeek
  - 论文解读
  - 视频笔记
  - 架构分析
source:
  video: https://www.bilibili.com/video/BV1rpovBCEGH/
  paper: https://arxiv.org/abs/2606.19348
  report: https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf
  wechat: https://mp.weixin.qq.com/s/8bxXqS2R8Fx5-1TLDBiEDg
  hf: https://huggingface.co/collections/deepseek-ai/deepseek-v4
  modelscope: https://modelscope.cn/collections/deepseek-ai/DeepSeek-V4
related:
  - "note_original.md"
---

# DeepSeek-V4 技术解读(精修版)

**一句话结论**:DeepSeek-V4 不是"更大",而是把注意力从 O(n²) 里解放出来,用 **CSA+HCA 混合注意力 + mHC 残差约束 + Muon 优化器** 三个改动,把"百万 token 上下文"从实验室变成了可常规部署的能力。V4-Pro 在 1M 上下文下推理 FLOPs 只需 V3.2 的 27%、KV cache 只需 10%。

---

## 0. 阅读地图

| 章节 | 内容 | 主要来源 |
|---|---|---|
| §1 | 模型与发布信息 | HF 集合 / 论文 |
| §2 | 技术路线图:V1→V4 每次架构改动的动机 | 视频 |
| §3 | 三大架构创新(CSA+HCA / mHC / Muon) | 论文 |
| §4 | 训练与基础设施 | 论文 |
| §5 | 效率与评测数据 | 论文 |
| §6 | 技术评注:这些改动为什么重要 | 分析 |
| §7 | 参考文献 | 学术引用格式 |
| §8 | 观众观点 | 视频评论 |

---

## 1. 模型与发布信息

**论文[1]与[2]**:DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence(arXiv:2606.19348,**preview 版**,共 8 页正文 + 附录,44 页;技术报告见[2],官方发布公告见[3])。

| 模型 | 总参数 | 激活参数 | 预训练 tokens | 定位 |
|---|---|---|---|---|
| **DeepSeek-V4-Pro** | 1.6T | 49B | 33T | 旗舰,推理能力上限(Pro-Max 为最高 reasoning effort 模式) |
| **DeepSeek-V4-Flash** | 284B | 13B | 32T | 高性价比,小参数高激活效率 |

两者**原生支持 1M token 上下文**。保留 V3 的 **DeepSeekMoE + 多 token 预测(MTP)** 框架;MoE 路由专家参数用 **FP4** 精度。

作为 preview 版本,V4 的核心定位是**把百万级上下文变成常规部署成本可承受的能力**:论文强调在 1M 上下文下 V4-Pro 仅需 V3.2 的 27% 推理 FLOPs 与 10% 的 KV cache,让长程 Agent 工作流、跨文档分析、测试时扩展(test-time scaling)变得切实可行。

| 指标 | V4-Pro | V4-Flash |
|---|---|---|
| 总参数 / 激活参数 | 1.6T / 49B | 284B / 13B |
| 预训练 tokens | 33T | 32T |
| 上下文长度 | 1M | 1M |
| 推理强度模式 | Non-think / Think High / Think Max | 同左 |
| 1M 上下文 FLOPs(相对 V3.2) | 27% | 10% |
| 1M 上下文 KV cache(相对 V3.2) | 10% | 7% |

模型权重均已开源:Hugging Face[4] 与 ModelScope[5] 共收录 7 个模型:

| 模型 | 参数量 | 说明 |
|---|---|---|
| DeepSeek-V4-Flash-Base | 292B | 基础版 |
| DeepSeek-V4-Flash | 291B | 文本生成 |
| DeepSeek-V4-Pro-Base | 1.6T | 基础版 |
| DeepSeek-V4-Pro | 1.6T | 文本生成 |
| DeepSeek-V4-Flash-DSpark | 165B | 稀疏版 |
| DeepSeek-V4-Pro-DSpark | 1.7T | 稀疏版 |
| DeepSeek-V4-Flash-0731 | 304B | 快照版本 |

---

## 2. 技术路线图:V1 → V4 的演进逻辑

视频[6](up 主 @闪客)用"你就是梁文峰"的第一人称,还原了每条技术路线"当初为什么要这么改"。这条主线比单看 V4 论文更有价值——**V4 的每个组件几乎都是前面论文的累积**。

```
V1  DeepSeek LLM (2024-01)
     └─ 缩放定律研究:超参数(bs/lr/数据/算力)对训练的影响
V2  DeepSeekMoE + MLA
     ├─ MoE:FFN 拆专家,细粒度路由 + 共享专家 → 激活参数大降
     └─ MLA:KV 先压缩成 latent 再还原 → KV cache 大降
V3  671B MoE / 激活 37B
     └─ 低成本稳定训练 + 性能比肩前沿开源 → 社区爆红
R1  纯强化学习(GRPO,无 SFT)
     └─ 自发涌现推理能力,Aha moment
V3.2  DSA 稀疏注意力
     └─ 不固定窗口,按相关性找 token
V4  CSA + HCA 混合注意力(1M context)
     └─ 压缩 KV + 稀疏/稠密注意力组合
```

**关键洞见**:V4 的注意力效率不是一步到位。MLA(V2)证明了"KV 可压缩",DSA(V3.2)证明了"attention 可稀疏",V4 把两者合成 CSA,再加 HCA 做更激进压缩。这正是"来时路的总和"。

---

## 3. 三大架构创新

### 3.1 混合注意力:CSA + HCA

**问题**:标准注意力对每个 query 都要算与全部历史 KV 的相关性,复杂度 O(n²)。上下文到百万级后,单 token 推理 FLOPs 和 KV cache 都不可承受。

**CSA(Compressed Sparse Attention)** 两步走:
1. **压缩 KV**:每 m 个 token 的 KV 压缩成 1 条压缩 KV 条目(C^Comp),序列长度压到 1/m。
2. **稀疏选择**:在压缩后的 KV 上做 DSA,用 **Lightning Indexer** 以低秩方式生成 indexer query,选出 top-k 条最相关的压缩 KV 做核心注意力;同时保留一个小滑动窗口的原始 KV 以增强局部细粒度依赖。

**HCA(Heavily Compressed Attention)**:把每 m'(≫m) 个 token 合并成 1 条,压缩更狠,但**保持稠密注意力**(不再稀疏选择),承担"全局概况"角色。

两者**交错布置**成混合结构:局部细节由 CSA 的滑动窗口捕捉,长程结构由 HCA 兜底。这是把"稀疏(选谁)"和"压缩(怎么压)"两种思路组合进一个模型。

**Lightning Indexer**:CSA 的稀疏选择由轻量索引器完成——复用压缩算子生成压缩后的 indexer keys,再以低秩方式(先降维再升维)为每个 query 生成多条 indexer queries,计算与各压缩块的相似度得分,选出 top-k 条参与核心注意力。其 QK 路径在推理与后训练中以 **FP4** 精度运行,加速长上下文下的注意力分数计算。

### 3.2 mHC(Manifold-Constrained Hyper-Connections)

**问题**:朴素残差连接 x_{l+1} = x_l + F(x_l) 信息传递太死板,层数深了信号可能失真。

**HC 的改进**(字节提出):把残差流宽度从 d 扩到 n_hc·d,用三个可学习线性映射(A 输入映射、B 残差变换、C 输出映射)控制信息流。但 B 连乘可能让谱范数失控 → **梯度爆炸**。

**mHC 的约束**:把残差映射矩阵 B 约束到**双随机矩阵流形(Birkhoff 多面体)**:
- 双随机矩阵 = 行和、列和都等于 1 的非负矩阵;
- 约束后谱范数 ‖B‖₂ ≤ 1,**映射非扩张**,前向/反向传播数值稳定;
- 该集合对乘法封闭,**深层堆叠也稳定**;
- 投影用 **Sinkhorn-Knopp 迭代**(20 次):先 exp 保证非负,再交替行/列归一化。

A、C 映射用 Sigmoid 约束非负有界,避免信号抵消。

**动态参数化**:三个映射的参数由输入动态生成——对残差状态做 RMSNorm 展平后,经可学习的低秩投影 $W^{\mathrm{pre}}/W^{\mathrm{res}}/W^{\mathrm{post}}$ 生成原始参数,再叠加静态偏置,最后投影到双随机流形 / 经 Sigmoid。既保留残差路径表达力,又保证信号不发散。

**直觉**:相当于给残差连接装了一个"能量守恒"约束——信息可以重组但不能发散。

### 3.3 Muon 优化器

V3 用 AdamW,V4 的大部分模块换 **Muon**——矩阵级优化器,通过牛顿-舒尔茨(Newton–Schulz)迭代对参数矩阵做正交化式更新,收敛更快、训练更稳。配置:momentum 0.95、weight decay 0.1,每步更新矩阵 RMS 重标至 0.18 以复用 AdamW 学习率。工程上配套 hybrid ZeRO 分片 + BF16 梯度同步(见 §4.3),保证逐位可复现。

### 3.4 其他细节改动

- MoE 路由亲和度从 Sigmoid 改为 **Sqrt(Softplus)**;
- 去掉路由目标节点数约束,并重新设计并行策略维持训练效率;
- 前几个 Transformer block 的稠密 FFN 换成 **Hash routing** 的 MoE(按输入 token ID 的哈希函数定专家,省去路由学习);
- 仍用 auxiliary-loss-free 负载均衡 + 序列级均衡 loss(防止单序列内极端不均衡)。

---

## 4. 训练与基础设施

### 4.1 预训练:数据、配置与稳定性

**数据构建。** 在 V3 语料之上构建更多样、更高质量、上下文更长的语料(Flash 32T / Pro 33T tokens)。网页数据过滤批量自动生成与模板化内容(防模型坍缩);数学与编程仍为核心,中期训练引入 **agentic data** 强化编程;多语言语料扩大覆盖跨文化长尾知识;特别强调长文档语料(科学论文、技术报告等学术价值材料)。词表保持 128K,继承 token 切分与 FIM,改用**样本级注意力掩码**。

**模型配置。** 两者均 CSA/HCA 交错布置(CSA $m{=}4$,HCA $m'{=}128$,滑动窗口 128):

| 参数 | Flash | Pro |
|---|---|---|
| Transformer 层数 | 43 | 61 |
| 隐层维度 $d$ | 4096 | 7168 |
| 稀疏注意 top-$k$ | 512 | 1024 |
| query 头数 / 压缩维度 | 64 / 1024 | 128 / 1536 |
| 路由专家数(激活 6) | 256 | 384 |
| 专家中间维度 | 2048 | 3072 |
| mHC 扩展因子 $n_{hc}$ / Sinkhorn 迭代 | 4 / 20 | 4 / 20 |
| 总参数 / 激活参数 | 284B / 13B | 1.6T / 49B |

**训练配置。** 混合优化器:大部分参数 **Muon**(momentum 0.95、wd 0.1、RMS 重标至 0.18),embedding/预测头/RMSNorm 用 AdamW。Flash 最大 batch 75.5M、峰值 lr $2.7\times10^{-4}$;Pro 最大 batch 94.4M、峰值 lr $2.0\times10^{-4}$;2000 步 warmup + cosine 衰减,序列长度 4K→16K→64K→1M 渐进。注意力稀疏:前 1T tokens 用稠密注意预热,64K 长度引入稀疏注意,并对 Lightning indexer 短阶段预热。

**训练稳定性。** loss spike 与 MoE 层离群值强相关,路由机制放大问题。两项对策:
- **Anticipatory Routing(前瞻路由)**:路由索引用历史参数 $\theta_{t-\Delta t}$ 提前计算缓存,解耦主干与路由网络更新;额外开销约 20%,仅在检测到 spike 时自动触发短回滚启用。
- **SwiGLU Clamping**:线性分量截断到 $[-10,10]$,gate 上界 10,显著抑制离群值。

### 4.2 后训练:两阶段范式

与 V3.2 相比,关键改动是**将混合 RL 阶段整体替换为 On-Policy Distillation(OPD)**。

**阶段一:领域专家训练。** 各领域 SFT + GRPO,要点:
- **三档推理模式**:Non-think / Think High / Think Max,以 `<think>` 标记 + 不同长度惩罚/上下文窗口实现;Think Max 在 system prompt 注入"最大推理强度、禁止捷径"指令。
- **生成式奖励模型(GRM)**:难验证任务不用标量奖励模型,让 actor 网络原生充当 GRM,评判与生成能力联合优化,仅需少量人类标注。
- **工具调用 schema**:`|DSML|` 特殊 token + XML 格式,减少转义失败与工具调用错误。
- **Interleaved Thinking**:工具调用场景用 1M 上下文保留全部推理历史(跨用户消息);普通对话仍丢弃旧推理。
- **Quick Instruction**:输入序列追加专用特殊 token(是否搜索、生成标题/query、判断权威性),复用 KV cache 避免冗余 prefill,降低 TTFT。

**阶段二:多教师 on-policy 蒸馏。** 对 10 余个专家教师优化反向 KL(式 1),学生用自己的轨迹采样;采用**全词表 logit 蒸馏**(而非逐 token KL),梯度估计更稳定、保真度更高。

$$ \mathcal{L}_{\mathrm{OPD}}(\theta)=\sum_{i=1}^{N} w_i\, D_{\mathrm{KL}}(\pi_\theta \parallel \pi_{E_i}) \tag{1} $$

这一"分而治之再蒸馏"范式使 1.6T 通用模型能多领域同时强。

### 4.3 基础设施

**细粒度专家并行(EP)。** MoE 层分解为 Dispatch/Linear-1/Linear-2/Combine 四阶段,通信总时长 < 计算时长;按 wave 切分专家实现计算/通信细粒度流水重叠(理论 1.92×),NVIDIA 与昇腾实测推理加速 1.50–1.73×,RL rollout 最高 1.96×;CUDA mega-kernel `MegaMoE` 已并入 DeepGEMM 开源。硬件建议:计算/通信比达 $C/B\le2d=6144$ FLOPs/Byte 后带宽不再是瓶颈。

**TileLang DSL。** 融合 kernel 替代数百个 Torch ATen 算子:① Host Codegen 把校验移出 Python 路径,调用开销从数百微秒降到 $<1\mu s$;② 集成 Z3 SMT 求解器做形式化整数分析;③ 默认关 fast-math、对齐 CUDA 工具链,实现 bitwise 可复现。

**Batch-invariant 确定性 kernel。** 保证 token 输出与其在 batch 中的位置无关:注意力解码用双 kernel 规避 wave-quantization;矩阵乘全线换 DeepGEMM、弃 split-k;反传确定性——注意力每 SM 独立累加再确定性求和,MoE 反传 token 排序 + 缓冲隔离,mHC 小矩阵确定性归约。

**训练框架。**
- **Muon 高效实现**:混合 ZeRO bucket 分配(稠密参数背包算法限并行度,MoE 按专家展平分发);连续同形参数合并批量跑 Newton–Schulz;BF16 下 Newton–Schulz 仍稳定,随机舍入压缩 MoE 梯度到 BF16,通信减半。
- **mHC 节省实现**:融合 kernel + 选择性重算 + 调整 DualPipe 1F1B 重叠,wall-time 开销仅 6.7%。
- **上下文并行(CP)**:两阶段通信——先传尾部 $m$ 条未压缩 KV 跨边界压缩,再 all-gather 压缩 KV 由 fused select-and-pad 重组。
- **张量级激活检查点**:TorchFX 追踪图,注解张量自动重算,重算子图插入反传;零拷贝、零额外开销。

**推理框架:异构 KV cache 与磁盘存储。** 混合注意力无法套用 PagedAttention:KV cache 分经典 KV cache(CSA/HCA)+ **state cache**(SWA 与未压缩尾部),请求分配定长块、按 $\mathrm{lcm}(m,m')$ 对齐。共享前缀用磁盘 KV 存储免重复 prefill:压缩 KV 直接落盘复用;SWA KV 约为压缩 KV 的 8 倍,提供全量缓存 / 周期检查点 / 零缓存重算三策略。

**后训练基建。**
- **FP4 QAT**:MoE 专家权重 + CSA indexer QK 路径 FP4 量化,index 分数降 BF16;top-k 选择器加速 2×、保持 99.7% KV 召回率;FP4→FP8 反量化无损(E4M3 比 E2M1 多 2 指数位)。
- **全词表 OPD 教师调度**:教师权重分布式存储按需加载,只缓存教师末层隐状态、训练时重建 logits,避免 $|V|>100k$ 落盘;样本按教师索引排序,每 mini-batch 至多一个教师头驻留。
- **可抢占容错 rollout**:token 粒度 WAL + 抢占时保存 KV cache,恢复续解码;硬件故障用 WAL 重跑 prefill,避免从零重生成的长度偏差。
- **百万上下文 RL**:rollout 数据拆轻量元数据 + 重 per-token 字段,共享内存加载器按 mini-batch 消费,降内存压力。
- **Agent 沙箱(DSec)**:基于 3FS 的弹性计算平台,单集群数十万并发沙箱;统一 SDK 抽象函数调用/容器/microVM/fullVM 四类基座,分层镜像加载 + 轨迹日志确定性重放。

---

## 5. 效率与评测数据

### 5.1 效率(1M context,相对 V3.2)

| 模型 | 单 token 推理 FLOPs | KV cache |
|---|---|---|
| DeepSeek-V4-Pro | 27%(FP8 等效) | 10% |
| DeepSeek-V4-Flash | 10% | 7% |

注:FP4×FP8 峰值 FLOPs 在当前硬件与 FP8×FP8 相同,但**未来硬件理论上可再省 1/3**。

### 5.2 评测(V4-Pro-Max,即最高推理强度模式)

| 维度 | 表现 |
|---|---|
| 知识 | SimpleQA / 中文 SimpleQA 显著领先开源;MMLU-Pro / HLE / GPQA 小幅领先开源,紧追 Gemini-3.1-Pro |
| 推理 | 强于 GPT-5.2、Gemini-3.0-Pro;弱于 GPT-5.4、Gemini-3.1-Pro(**落后前沿约 3–6 个月**) |
| Agent | 与 Kimi-K2.6、GLM-5.1 持平;内部评测 > Claude Sonnet 4.5,≈ Opus 4.5 |
| 长上下文 | 1M context 学术基准**超过 Gemini-3.1-Pro** |

**基础模型对比**(V3.2-Base vs V4-Base):

| 基准 | V3.2-Base | V4-Flash-Base | V4-Pro-Base |
|---|---|---|---|
| MMLU (5-shot) | 87.8 | 88.7 | 90.1 |
| MMLU-Pro (5-shot) | 65.5 | 68.3 | 73.5 |
| C-Eval (5-shot) | 90.4 | 92.1 | 93.1 |
| SimpleQA-verified (25-shot) | 28.3 | 30.1 | 55.2 |
| SuperGPQA (5-shot) | 45.0 | 46.5 | 53.9 |
| FACTS Parametric (25-shot) | 27.1 | 33.9 | 62.6 |
| HumanEval (Pass@1) | 62.8 | 69.5 | 76.8 |
| LongBench-V2 (1-shot) | 40.2 | 44.7 | 51.5 |

V4-Flash-Base 以更小参数量全面超越 V3.2-Base(尤其世界知识与长上下文);V4-Pro-Base 进一步全面领先。其中 **SimpleQA-verified** 与 **FACTS Parametric** 上 Pro-Base 相对 V3.2-Base 近乎翻倍(28.3→55.2、27.1→62.6),反映知识密集与事实性任务上的显著增益。

V4-Flash-Max:知识评测因参数小偏弱;但给更大 thinking budget 时,**推理任务与 Pro-Max 可比**——说明 Flash 是"效率换推理时间"的划算选择。

---

## 6. 技术评注

**① 方向转变:从"堆算力"到"减算力"。** 2026 年的开源大模型竞争早已不是单点参数竞赛。V4 的卖点不是最强,而是**百万上下文下的单位算力性价比**。这与 test-time scaling(推理时扩展)的趋势契合:上下文越长,注意力开销越占主导,压住它 = 解锁更长的推理。

**② MLA → CSA 是一脉相承的。** V2 的 MLA 压缩的是"每个头的 KV";V4 的 CSA 压缩的是"序列维度上的 token"。同一个信念——KV 存在冗余——在不同维度上兑现。

**③ mHC 是"训练稳定化"的隐性功臣。** 论文把 mHC 列为三大创新之一,但它不直接提精度,而是让 1.6T 的模型**训得动**。1.6T 参数 + 百万上下文,数值稳定性是硬约束;双随机约束(非扩张映射)是一种优雅的数学解法。

**④ 落后前沿 3–6 个月是论文亲口承认的。** 这在官方技术报告里少见——既有坦诚,也说明推理/知识前沿的竞争依然胶着。DeepSeek 的差异化仍在"效率 + 开源 + 价格"。

**⑤ OPD 替代混合 RL 是一次"收敛性"选择。** 多专家合并若用权重混合或混合 RL,通常伴随性能回退;OPD 用学生自采样的 on-policy 轨迹做全词表 reverse-KL 蒸馏,把物理上分离的专家知识收编到统一参数空间,工程代价由全词表教师调度(§4.3)摊平。

**⑥ 1M 上下文的真正意义是解锁 test-time scaling。** 推理模型性能由"推理预算"决定;上下文越长、推理步数越多,注意力开销越占主导。V4 把百万上下文做到可常规部署,等价于把"长时间思考 / 长程工具调用"的成本降下来——这是下一代推理范式的基础设施。

---

## 7. 参考文献

[1] DeepSeek-AI. DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence[EB/OL]. arXiv:2606.19348, 2026. https://arxiv.org/abs/2606.19348

[2] DeepSeek-AI. DeepSeek-V4 Technical Report[EB/OL]. Hugging Face, 2026. https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf

[3] DeepSeek-AI. DeepSeek-V4 发布公告[EB/OL]. 微信公众号, 2026. https://mp.weixin.qq.com/s/8bxXqS2R8Fx5-1TLDBiEDg(抓取时触发微信安全验证,未能直接读取正文)

[4] DeepSeek-AI. DeepSeek-V4 Models[EB/OL]. Hugging Face Collection. https://huggingface.co/collections/deepseek-ai/deepseek-v4

[5] DeepSeek-AI. DeepSeek-V4 模型集合[EB/OL]. ModelScope. https://modelscope.cn/collections/deepseek-ai/DeepSeek-V4

[6] 闪客. 深入解读 DeepSeek V1~V4!男女老少都听得懂[EB/OL]. Bilibili, 2026. https://www.bilibili.com/video/BV1rpovBCEGH/

---

## 8. 观众观点(视频评论/弹幕)

弹幕高频:token、moe、DeepSeek、毕导、R1、transformer、夯爆了、有惊喜有突破。

- "从 V1 到 V4,歪歪斜斜的每页上都写着'模型压缩'几个字……满本上都写着两个字'没卡'" (513 赞)—— 网友对"没算力只能抠效率"的戏谑,反而点中了 V4 的本质。
- "仍然用古法阅读和古法 PPT 绘图的方式制作出如此高质的视频" (402 赞)—— 认可 up 主硬核与认真。
- "极少数硬核的 up……只有你是极少数出淤泥而不染的" (343 赞)。
- "闪客不愧为小梁文峰" (280 赞)。
- "感觉 dp 的热度比去年下降了好多,一刷都是豆包元宝千问" (130 赞)—— 竞争格局变化的真实感知。
- "周日赶项目 opus4.7 没解决的问题 v4pro 三轮解决了" (119 赞)—— 一线使用反馈。
- "v4 又降价了,缓存命中一折" (23 赞)—— 价格策略(缓存命中 1 折)。
- "有传言说 V4 放弃了 CUDA 架构,转用昇腾 GPU" (34 赞)—— 未证实传闻,存疑。

---

## 9. 与初稿的关系

本稿为精修版。初稿见 note_original.md,保留了原始视频笔记结构。精修版补充了:① 阅读地图;② 技术路线图;③ mHC 的数学直觉;④ 后训练两阶段范式;⑤ 技术评注与观点。视频截帧存放于 `Assets/`。
