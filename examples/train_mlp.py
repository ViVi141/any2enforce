"""游戏内自训练 POC：4→8→3 MLP 在线训练（手写前向 + 反向传播 + SGD）。

全部使用 any2enforce v0.1 子集（纯循环 / list / 注解 / 全局函数）。
训练数据为内置 8 样本 3 类任务（one-hot）；权重用 LCG 伪随机初始化
（float 取模，Python 与 EnforceScript 的 IEEE 结果一致）。
运行：转换后用 execCode run_training()，应打印 30 轮单调下降的 loss。
验证：本文件在 Python 里先跑通（loss 下降），再转成 EnforceScript 对拍。

⚠ 命名空间教训：EnforceScript 无模块，全部脚本一起编译 —— 全局函数名
必须全项目唯一（与 mlp_forward.c 的 relu/softmax 撞名会报
"Multiple declaration of function"）。故辅助函数统一加 train_ 前缀；
工具侧可用 --prefix 选项统一加前缀。
"""


def train_relu(x: float) -> float:
    return x if x > 0.0 else 0.0


def train_relu_deriv(x: float) -> float:
    return 1.0 if x > 0.0 else 0.0


def train_approx_exp(x: float) -> float:
    # ANNA 惯例：Math.Pow(Math.E, x) + 钳制（引擎无 Math.Exp）
    if x < -20.0:
        return 0.0
    if x > 20.0:
        return 2.718281828459045 ** 20.0
    return 2.718281828459045 ** x


def train_softmax(logits: list[float]) -> list[float]:
    count = len(logits)
    max_logit = logits[0]
    for idx in range(1, count):
        if logits[idx] > max_logit:
            max_logit = logits[idx]
    probs: list[float] = []
    total = 0.0
    for idx in range(count):
        value = train_approx_exp(logits[idx] - max_logit)
        probs.append(value)
        total = total + value
    for idx in range(count):
        probs[idx] = probs[idx] / total
    return probs


def init_weights(w1: list[float], b1: list[float],
                 w2: list[float], b2: list[float]) -> None:
    """LCG 伪随机初始化（float 取模，跨语言数值一致）。"""
    seed = 0.5
    for i in range(32):
        seed = (seed * 1.732 + 3.14159) % 97.0
        w1.append((seed / 97.0) - 0.5)
    for i in range(8):
        seed = (seed * 1.732 + 3.14159) % 97.0
        b1.append((seed / 97.0) - 0.5)
    for i in range(24):
        seed = (seed * 1.732 + 3.14159) % 97.0
        w2.append((seed / 97.0) - 0.5)
    for i in range(3):
        seed = (seed * 1.732 + 3.14159) % 97.0
        b2.append((seed / 97.0) - 0.5)


def train_epoch(xs: list[float], ys: list[float], w1: list[float], b1: list[float],
                w2: list[float], b2: list[float], sample_count: int, lr: float,
                feature_count: int, hidden_size: int, class_count: int) -> float:
    """一个 epoch：前向 -> MSE loss -> 反向传播 -> SGD 更新。返回平均 loss。"""
    total_loss = 0.0
    for s in range(sample_count):
        # ---- forward ----
        x_norm: list[float] = []
        z1: list[float] = []
        h1: list[float] = []
        for fi in range(feature_count):
            x_norm.append(xs[s * feature_count + fi])
        for hi in range(hidden_size):
            z = b1[hi]
            wbase = hi * feature_count
            for fi in range(feature_count):
                z = z + w1[wbase + fi] * x_norm[fi]
            z1.append(z)
            h1.append(train_relu(z))
        z2: list[float] = []
        for ci in range(class_count):
            z = b2[ci]
            wbase = ci * hidden_size
            for hi in range(hidden_size):
                z = z + w2[wbase + hi] * h1[hi]
            z2.append(z)
        probs = train_softmax(z2)

        # ---- error (MSE 梯度) 与 loss ----
        err: list[float] = []
        for ci in range(class_count):
            e = probs[ci] - ys[s * class_count + ci]
            err.append(e)
            total_loss = total_loss + e * e

        # ---- 隐层梯度（必须在更新 w2 之前，用旧 w2）----
        dh: list[float] = []
        for hi in range(hidden_size):
            g = 0.0
            for ci in range(class_count):
                g = g + w2[ci * hidden_size + hi] * err[ci]
            dh.append(g)

        # ---- SGD 更新 w2 / b2 ----
        for ci in range(class_count):
            b2[ci] = b2[ci] - lr * err[ci]
            wbase = ci * hidden_size
            for hi in range(hidden_size):
                w2[wbase + hi] = w2[wbase + hi] - lr * err[ci] * h1[hi]

        # ---- SGD 更新 w1 / b1 ----
        for hi in range(hidden_size):
            g = dh[hi] * train_relu_deriv(z1[hi])
            b1[hi] = b1[hi] - lr * g
            wbase = hi * feature_count
            for fi in range(feature_count):
                w1[wbase + fi] = w1[wbase + fi] - lr * g * x_norm[fi]

    return total_loss / sample_count


def run_training() -> None:
    feature_count = 4
    hidden_size = 8
    class_count = 3
    sample_count = 8
    lr = 0.5
    epochs = 30

    xs = [
        1.0, 1.0, 1.0, 1.0,   -1.0, 1.0, 0.0, 0.0,
        0.0, 0.0, -1.0, 1.0,  -1.0, -1.0, -1.0, -1.0,
        1.0, -1.0, 1.0, -1.0,  0.5, -0.5, 0.0, 0.0,
        0.1, -0.05, 0.4, 0.2,  0.9, -0.8, 0.7, 0.3,
    ]
    ys = [
        1.0, 0.0, 0.0,  0.0, 1.0, 0.0,  0.0, 0.0, 1.0,
        0.0, 1.0, 0.0,  1.0, 0.0, 0.0,  1.0, 0.0, 0.0,
        1.0, 0.0, 0.0,  1.0, 0.0, 0.0,
    ]

    w1: list[float] = []
    b1: list[float] = []
    w2: list[float] = []
    b2: list[float] = []
    init_weights(w1, b1, w2, b2)

    for epoch in range(epochs):
        loss = train_epoch(xs, ys, w1, b1, w2, b2, sample_count, lr,
                           feature_count, hidden_size, class_count)
        print(epoch, loss)
