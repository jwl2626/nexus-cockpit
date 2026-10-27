# cockpit-diag · 座舱智能诊断（教学版）

用 **ADB / Fastboot / 周立功 CAN / 以太网** 四类指令诊断车机（座舱），
把「老师傅的经验」变成**规则 + 可训练的小模型**，并给出「为什么这么判、下一步查什么」。

> 面向「想自己动手做一个」的人：代码全部可读、可改，没有黑盒框架，
> 训练部分用 numpy 手写，120 行。

---

## 先跑起来（不需要任何硬件）

```bat
python -m diag.cli demo
```

它会用合成数据完整跑一遍 **采集 → 特征化 → 训练 → 评估 → 诊断**，
并生成 `reports/demo-report.md`。约 10 秒。

你会看到这样的输出：

```text
样本 200  准确率 86.0%  漏检率 6.7%  误报率 16.4%
```

**这是正常的起点。** 真实项目第一次训练就在这个区间，不是 99%。

---

## 三个层次

| 层 | 干什么 | 在哪 |
| --- | --- | --- |
| 采集 | 发指令、记录结果 | `diag/channels/`、`diag/probe.py` |
| 特征+模型 | 把记录变成向量、训练分类器 | `diag/features.py`、`diag/model.py` |
| 决策 | 规则 + 模型融合，给理由和建议 | `diag/rules.py`、`diag/diagnose.py` |

---

## 常用命令

```bat
:: 完整演示（合成数据）
python -m diag.cli demo

:: 对真机跑一遍检查项，存成样本
python -m diag.cli probe --unit CAR-001 --label OK --out data/CAR-001.json

:: 用真实样本训练
python -m diag.cli train --data data/real-samples.json --out models/diag.npz

:: 对一条样本出诊断结论
python -m diag.cli diagnose --sample data/CAR-001.json
```

`probe` 只读，不会修改设备。通道没接好时会自动跳过（记 `skipped`），不会报一堆错。

---

## 我要改哪里

| 我想…… | 改这个文件 |
| --- | --- |
| 增加/删除一个检查项 | `checks/cockpit.json` |
| 改判定规则（老师傅经验） | `checks/rules.json` |
| 改特征怎么算 | `diag/features.py` |
| 换模型 | `diag/model.py`（保持 `fit/predict_proba` 接口即可） |
| 改诊断理由的措辞 | `diag/diagnose.py` |

**最重要的认知：加一个好的检查项，比调模型有效 10 倍。**

---

## 文档

| 文档 | 内容 |
| --- | --- |
| [01-从MNIST到座舱诊断](docs/01-从MNIST到座舱诊断.md) | **先读这个**。方法论、七步训练流程、和 MNIST 的对照 |
| [02-四个通道怎么采数据](docs/02-四个通道怎么采数据.md) | 每个通道采什么、坑在哪、待填的命令清单 |
| [03-评估漂移与上线](docs/03-评估漂移与上线.md) | 验收标准、数据漂移、L3 大模型怎么接 |

---

## 目录结构

```text
cockpit-diag/
├─ checks/
│  ├─ cockpit.json     # 检查项清单（你最常改的文件）
│  └─ rules.json       # 规则（老师傅经验）
├─ diag/
│  ├─ types.py         # 数据结构
│  ├─ channels/        # 四个通道
│  │  ├─ adb.py
│  │  ├─ fastboot.py
│  │  ├─ canbus.py     # 周立功 / python-can
│  │  └─ ethernet.py   # ping / TCP / UDP(DoIP)
│  ├─ probe.py         # 采集器
│  ├─ features.py      # 特征化（78 维怎么来的）
│  ├─ model.py         # 手写 softmax 回归
│  ├─ metrics.py       # 漏检率 / 误报率 / 混淆矩阵
│  ├─ rules.py         # 规则引擎
│  ├─ diagnose.py      # 规则 + 模型融合
│  ├─ synth.py         # 合成数据（没真机时用）
│  └─ cli.py           # 命令行
├─ data/               # 采集的样本
├─ models/             # 训练出来的模型
└─ reports/            # 评估报告
```

---

## 依赖

```text
Python 3.10+
numpy               # 训练
python-can          # CAN（可选，不用 CAN 就不装）
```

其他全部标准库。

---

## 安全边界

- 采集阶段**只读**：不发 `flash` / `erase` / 清故障码。
- 诊断结论带**置信度**，低置信度应该转人工复核。
- 不要把本工具的输出直接接到产线卡控上，先并行跑一个月。

---

## 下一步

1. 把真实指令填进 `checks/cockpit.json`（见 `docs/02` 的待填清单）
2. 拿 5 台好机 + 5 台坏机各 `probe` 一遍，验证采集链路
3. 扩到每类 30 条，`train` 出第一个真实模型

做到第 3 步，你就有一个属于自己的、能说清理由的诊断模型了。
