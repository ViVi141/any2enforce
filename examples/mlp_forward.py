"""numpy-free MLP 前向 —— ANNA_DrivePolicyModel.c 的 round-trip 演示。

架构与 ANNA 的 Hybrid Brain M2 完全同构：
    features -> Standardize -> W1+B1 -> ReLU -> W2+B2 -> Softmax -> argmax
此处规模取 4->8->3 便于阅读；维度只是常量（ANNA 为 13->16->6，真实权重由
其 tools/sim/export_policy_constants.py 生成）。

权重为**手工设计的判别式占位值**（保证不同输入命中不同类别，便于跨类别
数值对拍）：
  hidden[0..7] = relu(±x0), relu(±x1), relu(±x2), relu(±x3)   （W1 为符号选择矩阵）
  class0 = h0+h2+h4+h6（输入全正）、class1 = h1+h2（x0 负 x1 正）、
  class2 = h5+h6（x2 负 x3 正）
期望（Python 参考已算好）：
  [ 1, 1, 1, 1] -> 0     [-1, 1, 0, 0] -> 1     [ 0, 0,-1, 1] -> 2
  [-1,-1,-1,-1] -> 1     [ 1,-1, 1,-1] -> 0     [ 0.5,-0.5,0,0] -> 0

本文件全部使用 any2enforce v0.1 子集（纯循环 / list / 类型注解）。
"""


def relu(x: float) -> float:
    return x if x > 0.0 else 0.0


def approx_exp(x: float) -> float:
    # ANNA 惯例：引擎无 Math.Exp -> Math.Pow(Math.E, x) + 钳制
    if x < -20.0:
        return 0.0
    if x > 20.0:
        return 2.718281828459045 ** 20.0
    return 2.718281828459045 ** x


def softmax(logits: list[float]) -> list[float]:
    count = len(logits)
    max_logit = logits[0]
    for idx in range(1, count):
        if logits[idx] > max_logit:
            max_logit = logits[idx]
    probs: list[float] = []
    total = 0.0
    for idx in range(count):
        value = approx_exp(logits[idx] - max_logit)
        probs.append(value)
        total = total + value
    for idx in range(count):
        probs[idx] = probs[idx] / total
    return probs


def predict_behavior(features: list[float]) -> int:
    means = [0.0, 0.0, 0.0, 0.0]
    scales = [1.0, 1.0, 1.0, 1.0]
    w1 = [
        1.0, 0.0, 0.0, 0.0,
        -1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, -1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, -1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
        0.0, 0.0, 0.0, -1.0,
    ]
    b1 = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    w2 = [
        1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0,
        0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0,
    ]
    b2 = [0.0, 0.0, 0.0]
    feature_count = 4
    hidden_size = 8
    class_count = 3

    # standardize
    x_norm: list[float] = []
    for fi in range(feature_count):
        scale = scales[fi]
        if scale < 0.001:
            scale = 0.001
        x_norm.append((features[fi] - means[fi]) / scale)

    # hidden: h = ReLU(W1 * x + B1), W1 layout [hi * feature_count + fi]
    hidden: list[float] = []
    for hi in range(hidden_size):
        z = b1[hi]
        wbase = hi * feature_count
        for fi in range(feature_count):
            z = z + w1[wbase + fi] * x_norm[fi]
        hidden.append(relu(z))

    # logits: W2 * hidden + B2, W2 layout [ci * hidden_size + hi]
    logits: list[float] = []
    for ci in range(class_count):
        z = b2[ci]
        wbase = ci * hidden_size
        for hi in range(hidden_size):
            z = z + w2[wbase + hi] * hidden[hi]
        logits.append(z)

    probs = softmax(logits)
    best_idx = 0
    best_prob = probs[0]
    for idx in range(1, class_count):
        if probs[idx] > best_prob:
            best_prob = probs[idx]
            best_idx = idx
    return best_idx
