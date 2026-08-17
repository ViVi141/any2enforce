"""numpy-free MLP 前向 —— ANNA_DrivePolicyModel.c 的 round-trip 演示。

架构与 ANNA 的 Hybrid Brain M2 完全同构：
    features -> Standardize -> W1+B1 -> ReLU -> W2+B2 -> Softmax -> argmax
此处规模取 4->8->3 便于阅读；维度只是常量（ANNA 为 13->16->6，真实权重由
其 tools/sim/export_policy_constants.py 生成）。权重为占位示意值。
本文件全部使用 any2enforce v0.1 子集（纯循环 / list / 类型注解），
用于验证工具能把"算法层"代码转成与 ANNA 同风格的 EnforceScript。
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
    means = [0.05, -0.02, 0.30, 0.10]
    scales = [0.15, 0.10, 0.20, 0.13]
    w1 = [
        -0.05, 0.43, -0.12, -0.36,
        0.17, 0.25, 0.02, 0.08,
        -0.29, -0.29, -0.13, -0.02,
        0.12, -0.03, 0.21, 0.05,
        -0.64, -0.17, 0.12, 0.43,
        -0.18, 0.22, 0.00, 0.33,
        -0.36, 0.44, -0.51, -0.45,
        -0.21, -0.33, 0.12, 0.13,
    ]
    b1 = [-0.19, 0.56, 0.04, 0.66, -0.15, 0.23, 1.06, -0.07]
    w2 = [
        -0.61, 0.95, 0.09, 0.92, -0.13, 0.56, 1.37, -0.38,
        0.03, -0.27, 0.79, 0.30, 0.39, -0.01, -0.40, -0.00,
        0.40, 0.11, -0.67, -0.04, 0.33, 0.55, 0.11, 0.41,
    ]
    b2 = [1.20, -0.18, -0.28]
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
