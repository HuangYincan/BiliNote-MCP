> 来源链接：https://www.bilibili.com/video/BV1r8nMz4EAj/

## 1. 为什么需要 Self-attention

在深度学习中，传统的神经网络模型（如回归或分类任务）通常处理的是单个向量作为输入。然而，在处理更复杂的问题时，我们往往需要将一排向量（Vector Set）作为输入，且这些向量的长度是动态变化的。

*   **输入为向量集合的场景**：
    *   **文字处理**：一个句子由多个词汇组成，每个词汇可以用一个向量表示。由于句子长度不同，输入的向量集合大小也不同。
    *   **语音识别**：一段声音信号被切分成多个窗口（Window），每个窗口描述为一小段信号，即一个 Frame（向量）。
    *   **图结构（Graph）**：社交网络或分子结构可以看作图，每个节点（人或原子）都可以表示为一个向量。

*   **词汇向量化的表示方法**：
    *   **One-hot Encoding**：简单但无法体现语义关联（如无法识别 cat 与 dog 的相似性）。
    *   **Word Embedding**：赋予每个词汇一个包含语义信息的向量，相似词汇在向量空间中会聚集成团。

## 2. 输出的三种类型

根据输入向量集合的情况，输出通常分为以下三类：

1.  **输入与输出长度一致（Sequence Labeling）**：例如词性标注（POS tagging）或语音识别中的音标分类。
2.  **输入整个序列，输出单个标签**：例如情感分析（Sentiment Analysis）或判断一段声音的说话人身份。
3.  **输入整个序列，输出长度由模型决定（Sequence-to-Sequence）**：例如机器翻译或复杂的语音识别任务，输出长度与输入无关。

## 3. Sequence Labeling 的挑战与解决方案

*   **简单做法**：使用全连接网络（Fully Connected Network, FCN）对每个向量逐一处理。
    *   *缺陷*：忽略了上下文信息。例如在 "I saw a saw" 中，两个 "saw" 的词性不同，但 FCN 看到相同的输入向量会输出相同的标签。
*   **改进方案**：引入上下文（Context）。
    *   将当前向量及其前后相邻的向量串联起来（Windowing），一起输入到 FCN 中。
    *   *局限性*：窗口大小难以设定，若要覆盖整个序列，参数量会剧增且容易过拟合。

## 4. Self-attention 机制

Self-attention 旨在解决上述问题，通过处理整个序列的信息生成新的向量，让后续的 FCN 能够基于全局上下文进行决策。

*   **运作流程**：
    1.  输入一串向量 $A$（可以是原始输入或隐藏层输出）。
    2.  输出另一串向量 $B$。每一个 $B^i$ 都是在考虑了整个序列所有 $A$ 的信息后生成的。
    3.  Self-attention 可以与 FCN 交替使用，前者处理全局关联，后者处理特定位置的特征。

*   **计算过程（以生成 $b^1$ 为例）**：
    *   **计算关联性（Attention Score）**：
        1.  对于每个向量 $a^i$，计算其 Query ($q^i = W^q a^i$)、Key ($k^i = W^k a^i$) 和 Value ($v^i = W^v a^i$)。
        2.  通过 $q^1$ 与序列中所有 $k^j$ 做点积（Dot-product）计算相关程度 $\alpha_{1,j} = q^1 \cdot k^j$。
    *   **归一化**：
        *   对所有 $\alpha$ 进行 Soft-max 操作，得到 $\alpha'$：
            $$\alpha'_{1,i} = \frac{\exp(\alpha_{1,i})}{\sum_{j} \exp(\alpha_{1,j})}$$
    *   **抽取信息**：
        *   将每个向量的 Value ($v^i$) 乘以对应的权重 $\alpha'_{1,i}$，求和得到 $b^1$：
            $$b^1 = \sum_{i} \alpha'_{1,i} v^i$$

![](Assets/screenshot_000_ac8d5550-0e2b-4909-9061-66ef912ed790.jpg)*
![](Assets/screenshot_001_0f6d3d25-7e9c-481f-8960-50178d088696.jpg)*
![](Assets/screenshot_002_b950c00a-a307-49df-b3f3-d820680ce2e4.jpg)*
![](Assets/screenshot_003_6fa0440c-16f6-41f8-9bb0-763ee95b6f62.jpg)*
![](Assets/screenshot_004_71f32d8f-8356-46cb-aaa8-e5f96a0400b2.jpg)*
![](Assets/screenshot_005_340c8f19-14be-4ec6-bf3a-e455197ca10e.jpg)*
![](Assets/screenshot_006_665bbd68-d258-41f5-81c8-0b53de6b3567.jpg)*
![](Assets/screenshot_007_f9d70bfc-ecb7-47d1-bdab-4dc38e187b01.jpg)*
![](Assets/screenshot_008_682b52a6-dfb0-4255-bc7c-c70162fad9d3.jpg)*
![](Assets/screenshot_009_f8cd4489-81c2-4650-a7fb-73d6a85a8380.jpg)*
![](Assets/screenshot_010_fe1ebfad-fc64-4421-9d3e-c33a28911efc.jpg)*
![](Assets/screenshot_011_f5ae9787-c362-4df2-83c1-425426371b2e.jpg)*
![](Assets/screenshot_012_4e5b25c1-0231-4755-91af-83c784aa0812.jpg)*
![](Assets/screenshot_013_29e84b44-3f67-448b-a9e8-0cbaa65da36e.jpg)*
![](Assets/screenshot_014_f9359984-421d-4edf-9b44-f047fe4efd09.jpg)*
![](Assets/screenshot_015_c21a7359-abd8-422a-91d1-ee9ce929be0e.jpg)*
![](Assets/screenshot_016_86fb26f5-bad0-42d1-874c-931fd8f8c259.jpg)*
![](Assets/screenshot_017_d17e8256-2401-4019-9361-189e4ecc9487.jpg)*

## 5. 观众观点
*   **核心优势**：观众指出 Self-attention 与 RNN 的主要区别在于并行计算能力，RNN 需要逐个传递数据，而 Self-attention 可以一次性处理。
*   **对比 CNN**：CNN 可被视为感受野（Receptive Field）受限的 Self-attention。
*   **图神经网络应用**：在 Graph 中使用 Self-attention 时，通常只关注有边连接的节点，利用领域知识减少无关计算。
*   **学习建议**：多位观众推荐先看李宏毅老师的视频入门，后续配合李沐老师的进阶讲解，并强调一定要动手实现代码，因为原理与实现细节存在差异。
*   **补充资料**：李宏毅老师提供相关课件与代码，可关注公众号【AI评论员】回复【079】获取。