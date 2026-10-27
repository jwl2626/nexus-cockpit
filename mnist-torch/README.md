# mnist-torch · 完整的 PyTorch MNIST 工程

不是一个 5 行的 `model.fit()` 演示，而是一个**能改、能跑、能上工位**的工程骨架：
配置分离、训练/验证/测试分离、早停、断点续训、混淆矩阵、错例可视化、TorchScript 导出、单图推理、单元测试。

---

## 1. 30 秒自检（不需要数据集）

```bat
run_smoke.bat
```

输出 `SMOKE OK —— 训练/评估/保存/导出/推理 全链路通过`。

它用**随机张量**跑完整条链路（形状和真实 MNIST 一模一样），验证的是代码，不是精度。
所以看到"准确率 14%"别慌——那是随机标签，本来就该是 10% 左右。

> 这是工程里很重要的一招：**把"能不能跑"和"准不准"解耦**。
> 换机器、换 Python 版本、改完代码，先跑 smoke，30 秒知道有没有把东西搞坏。

---

## 2. 训练真实 MNIST

### 2.1 先解决数据（国内网络的坑）

torchvision 默认从 `ossci-datasets.s3.amazonaws.com` 下载，**国内经常超时**。
手动准备：下载下面 4 个文件，放进 `data/MNIST/raw/`，再运行训练即可（torchvision 检测到文件就不联网了）。

```text
data/MNIST/raw/
├─ train-images-idx3-ubyte.gz
├─ train-labels-idx1-ubyte.gz
├─ t10k-images-idx3-ubyte.gz
└─ t10k-labels-idx1-ubyte.gz
```

可用的下载地址（任选）：

- 官方：`https://ossci-datasets.s3.amazonaws.com/mnist/`
- 备用：`https://storage.googleapis.com/cvdf-datasets/mnist/`
- 国内镜像：搜「MNIST idx3-ubyte 镜像」，很多高校/云盘镜像提供同一批文件

校验（肉眼比对即可）：`train-images` 约 9.9 MB，`t10k-images` 约 1.6 MB。

### 2.2 训练

```bat
:: CNN，5 轮
run_train.bat --config configs/cnn.json

:: MLP 基线
run_train.bat --config configs/mlp.json

:: 临时改参数，不用动配置文件
run_train.bat --config configs/cnn.json --epochs 8 --lr 5e-4 --batch-size 256
```

**预期结果**（GTX 1070 Ti，5 轮）：

| 模型 | 参数量 | 测试准确率 |
| --- | --- | --- |
| MLP 784-256-10 | 203,530 | 97.5% ~ 98.2% |
| SmallCNN | 824,458 | 99.0% ~ 99.3% |

> 这两个数字是公开基准，不是我在你机器上实测的（本机下载不到 MNIST）。
> 你跑完会在 `runs/<name>/report.txt` 里看到自己的真实数字。

### 2.3 产物

```text
runs/cnn/
├─ config.json        本次训练用的完整配置（复现靠它）
├─ train.log          训练日志
├─ history.json       每轮 loss/acc，可以拿去画曲线
├─ best.pt            验证集最好的模型
├─ last.pt            最后一个 epoch（断点续训用）
├─ report.txt         测试集报告：每类 P/R/F1 + 混淆矩阵
└─ misclassified.png  判错的 32 张样本拼图
```

`misclassified.png` 值得打开看一眼：MNIST 上判错的那 0.7%，基本都是"人写得太像另一个数"。

---

## 3. 命令一览

| 命令 | 作用 |
| --- | --- |
| `run_smoke.bat` | 无数据自检，30 秒验链路 |
| `run_train.bat --config configs/cnn.json` | 训练 |
| `python -m mnist_torch.cli eval --checkpoint runs/cnn/best.pt` | 只评估，不训练 |
| `python -m mnist_torch.cli eval --checkpoint runs/cnn/best.pt --misclassified out.png` | 评估 + 导出错例图 |
| `python -m mnist_torch.cli predict --checkpoint runs/cnn/best.pt --image 3.png` | 单图推理 |
| `python -m mnist_torch.cli export --checkpoint runs/cnn/best.pt --out model.pt` | 导出 TorchScript |
| `python -m mnist_torch.cli info` | 环境信息（torch 版本、CUDA、显卡） |
| `python examples/make_digit.py out.png 7` | 生成一张测试图（没数据时验证 predict 用） |

想用 `python -m mnist_torch.cli`，需要先设置 `set PYTHONPATH=src`（`run_*.bat` 已自动设好），
或者 `pip install -e .` 装成包。

---

## 4. 工程结构

```text
mnist-torch/
├─ configs/                 实验配置（JSON）
│  ├─ cnn.json
│  └─ mlp.json
├─ src/mnist_torch/
│  ├─ config.py             配置 dataclass + JSON 读写 + 按类型强转
│  ├─ utils.py              随机种子、日志、计时
│  ├─ data.py               数据集 / 增强 / DataLoader / 合成数据
│  ├─ models.py             MLP + SmallCNN + 注册表
│  ├─ engine.py             训练循环、评估、早停、调度器、AMP
│  ├─ metrics.py            混淆矩阵、每类 P/R/F1、Top-K
│  ├─ checkpoint.py         保存 / 加载 / 自还原模型
│  ├─ visualize.py          样本网格、错例拼图（只依赖 Pillow）
│  ├─ export.py             TorchScript 导出 + 一致性校验
│  ├─ predict.py            单图推理（自动处理黑白反转）
│  └─ cli.py                命令行入口
├─ tests/                   23 个单元测试（unittest，无额外依赖）
├─ run_train.bat
└─ run_smoke.bat
```

---

## 5. 几个刻意的设计决策

| 决策 | 为什么 |
| --- | --- |
| **验证集用两份 Dataset 实例切分** | torchvision 的 transform 绑在 Dataset 上，用 `Subset` 切会让验证集也带数据增强，等于作弊 |
| **按验证集选最优，不按训练集** | 按训练集选一定会选出过拟合的那个 |
| **checkpoint 里存 config** | 还原模型时不用手填结构参数；半年后还能复现 |
| **早停** | MNIST 5 轮就收敛，再多是浪费；早停对真实项目能省一半算力 |
| **不用 matplotlib，只用 Pillow** | 少一个重依赖，工位机上装得上 |
| **`seed_everything` 连 cuDNN 一起固定** | 结果可复现，出问题能对比。代价是慢一点点 |
| **smoke 用随机张量** | 把"能不能跑"和"准不准"解耦，改代码后 30 秒回归 |
| **`predict` 自动判断黑白反转** | 手机拍的是黑字白底，MNIST 是白字黑底，这是最常见的翻车点 |

---

## 6. 和你座舱诊断项目的关系

**这套骨架可以直接搬过去，只换 Dataset。**

```python
# MNIST 版
ds = MNIST(root="data", train=True, transform=ToTensor())

# 你的座舱版（伪代码）
class ProbeDataset(Dataset):
    def __init__(self, samples):  # samples 来自 cockpit-diag 的 probe
        self.samples = samples
    def __len__(self): return len(self.samples)
    def __getitem__(self, i):
        s = self.samples[i]
        return torch.tensor(feature_vector(s), dtype=torch.float32), label_index(s.label)
```

然后把 `models.py` 里的输入维度从 `1×28×28` 改成你的特征维度，`engine.py`、`metrics.py`、
`checkpoint.py`、`export.py` 一行都不用动。

**但注意一个判断**：你的样本可能只有几百条，这时候**不要用这个 CNN**，用
`cockpit-diag` 里的逻辑回归就够，而且更可解释。这套 PyTorch 工程更适合
"以后数据涨到几千上万条、有图像/时序输入"的阶段。

---

## 7. 排错

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `DataError: MNIST 数据不可用` | 下载被墙 | 按 2.1 手动放文件 |
| 准确率一直在 10% | 忘了 `zero_grad`、标签错位、lr 太大爆掉 | 先看 train loss 是否下降 |
| CUDA out of memory | batch_size 太大 | 降到 64 / 32 |
| 中文乱码 | Windows 控制台 GBK | `utils.configure_stdio()` 已处理；仍乱码就 `chcp 65001` |
| `ModuleNotFoundError: mnist_torch` | 没设 PYTHONPATH | 用 `run_*.bat`，或 `pip install -e .` |
| 结果每次不一样 | 没固定种子 | `seed_everything()` 已固定；注意 `num_workers>0` 仍可能引入不固定性 |

---

## 8. 环境

本机验证环境：

```text
Python      3.10.1
PyTorch     2.7.1+cu118
torchvision 0.22.1+cu118
CUDA        True（NVIDIA GeForce GTX 1070 Ti, 8 GB）
```

CPU 也能跑，CNN 5 轮大概 5~10 分钟；GPU 上一分钟以内。
