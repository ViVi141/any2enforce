"""AI 训练实验室 POC —— 游戏内现场学会"追目标"。

纯脚本虚拟沙盒（无需实体/prefab）：目标在虚拟平面上做之字形运动，
学员（4->8->4 MLP）通过模仿 teacher 规则（向主导轴方向追击）在线学习，
实时打印三类指标：loss 下降、准确率上升、追击误差缩小。
跑通后接入真实实体只需把 lab_predict / lab_train_step 的输入换成实体坐标
（见 training_lab_glue.c）。

运行：转换后 execCode lab_run()。
全部使用 any2enforce v0.1 子集；全局函数统一 lab_ 前缀（扁平命名空间）。
"""


def lab_relu(x: float) -> float:
    return x if x > 0.0 else 0.0


def lab_exp(x: float) -> float:
    # ANNA 惯例：Math.Pow(Math.E, x) + 钳制（引擎无 Math.Exp）
    if x < -20.0:
        return 0.0
    if x > 20.0:
        return 2.718281828459045 ** 20.0
    return 2.718281828459045 ** x


def lab_softmax(logits: list[float]) -> list[float]:
    count = len(logits)
    max_logit = logits[0]
    for idx in range(1, count):
        if logits[idx] > max_logit:
            max_logit = logits[idx]
    probs: list[float] = []
    total = 0.0
    for idx in range(count):
        value = lab_exp(logits[idx] - max_logit)
        probs.append(value)
        total = total + value
    for idx in range(count):
        probs[idx] = probs[idx] / total
    return probs


def lab_init(w1: list[float], b1: list[float],
             w2: list[float], b2: list[float]) -> None:
    """LCG 伪随机初始化（float 取模，跨语言数值一致）。"""
    seed = 0.5
    for i in range(32):
        seed = (seed * 1.732 + 3.14159) % 97.0
        w1.append((seed / 97.0) - 0.5)
    for i in range(8):
        seed = (seed * 1.732 + 3.14159) % 97.0
        b1.append((seed / 97.0) - 0.5)
    for i in range(32):
        seed = (seed * 1.732 + 3.14159) % 97.0
        w2.append((seed / 97.0) - 0.5)
    for i in range(4):
        seed = (seed * 1.732 + 3.14159) % 97.0
        b2.append((seed / 97.0) - 0.5)


def lab_forward(x: list[float], w1: list[float], b1: list[float],
                w2: list[float], b2: list[float]) -> list[float]:
    """4 特征 -> 8 隐层 -> 4 类 softmax 概率。"""
    h: list[float] = []
    for hi in range(8):
        z = b1[hi]
        wbase = hi * 4
        for fi in range(4):
            z = z + w1[wbase + fi] * x[fi]
        h.append(lab_relu(z))
    z2: list[float] = []
    for ci in range(4):
        z = b2[ci]
        wbase = ci * 8
        for hi in range(8):
            z = z + w2[wbase + hi] * h[hi]
        z2.append(z)
    return lab_softmax(z2)


def lab_train_step(x: list[float], y: list[float], w1: list[float], b1: list[float],
                   w2: list[float], b2: list[float], lr: float) -> float:
    """单样本：前向 + MSE + 反向传播 + SGD。返回样本 loss。"""
    z1: list[float] = []
    h1: list[float] = []
    for hi in range(8):
        z = b1[hi]
        wbase = hi * 4
        for fi in range(4):
            z = z + w1[wbase + fi] * x[fi]
        z1.append(z)
        h1.append(lab_relu(z))
    z2: list[float] = []
    for ci in range(4):
        z = b2[ci]
        wbase = ci * 8
        for hi in range(8):
            z = z + w2[wbase + hi] * h1[hi]
        z2.append(z)
    probs = lab_softmax(z2)

    err: list[float] = []
    loss = 0.0
    for ci in range(4):
        e = probs[ci] - y[ci]
        err.append(e)
        loss = loss + e * e

    dh: list[float] = []
    for hi in range(8):
        g = 0.0
        for ci in range(4):
            g = g + w2[ci * 8 + hi] * err[ci]
        dh.append(g)

    for ci in range(4):
        b2[ci] = b2[ci] - lr * err[ci]
        wbase = ci * 8
        for hi in range(8):
            w2[wbase + hi] = w2[wbase + hi] - lr * err[ci] * h1[hi]

    for hi in range(8):
        g = dh[hi]
        if z1[hi] <= 0.0:
            g = 0.0
        # 梯度裁剪 ±1（防爆炸，游戏内训练必备）
        if g > 1.0:
            g = 1.0
        if g < -1.0:
            g = -1.0
        b1[hi] = b1[hi] - lr * g
        wbase = hi * 4
        for fi in range(4):
            w1[wbase + fi] = w1[wbase + fi] - lr * g * x[fi]

    return loss


def lab_teacher(dx: float, dy: float) -> int:
    """规则 teacher：向相对位移的主导轴方向追击。
    类：0=-x, 1=+x, 2=-y, 3=+y。"""
    ax = dx
    if ax < 0.0:
        ax = -dx
    ay = dy
    if ay < 0.0:
        ay = -dy
    if ax > ay:
        if dx > 0.0:
            return 1
        return 0
    if dy > 0.0:
        return 3
    return 2


def lab_run() -> None:
    lr = 0.1
    buf_x: list[float] = []
    buf_y: list[float] = []
    labels: list[int] = []
    w1: list[float] = []
    b1: list[float] = []
    w2: list[float] = []
    b2: list[float] = []
    lab_init(w1, b1, w2, b2)

    cx = 0.0
    cy = 0.0
    tx = 30.0
    ty = -20.0

    for step in range(400):
        # 目标之字形运动（无三角函数的纯算术路径）
        tx = tx + 1.2
        if tx > 50.0:
            tx = -50.0
        ty = ty - 0.8
        if ty < -40.0:
            ty = 40.0

        dx = tx - cx
        dy = ty - cy
        feat: list[float] = []
        feat.append(dx / 100.0)
        feat.append(dy / 100.0)
        feat.append(1.0)
        feat.append(0.0)

        # 前 200 步 teacher 开车（收集干净数据，避免闭环分布偏移）；
        # 后 200 步换学员开车（评估真实学习效果）。
        if step < 200:
            best = lab_teacher(dx, dy)
        else:
            probs = lab_forward(feat, w1, b1, w2, b2)
            best = 0
            bestp = probs[0]
            for ci in range(1, 4):
                if probs[ci] > bestp:
                    bestp = probs[ci]
                    best = ci

        if best == 0:
            cx = cx - 2.0
        elif best == 1:
            cx = cx + 2.0
        elif best == 2:
            cy = cy - 2.0
        else:
            cy = cy + 2.0
        # 学员位置钳制在目标活动范围（保持特征有界，避免失控漂移）
        if cx > 55.0:
            cx = 55.0
        if cx < -55.0:
            cx = -55.0
        if cy > 45.0:
            cy = 45.0
        if cy < -45.0:
            cy = -45.0

        # teacher 标签（基于当前相对位置）入缓冲
        label = lab_teacher(dx, dy)
        buf_x.append(dx / 100.0)
        buf_x.append(dy / 100.0)
        buf_x.append(1.0)
        buf_x.append(0.0)
        buf_y.append(0.0)
        buf_y.append(0.0)
        buf_y.append(0.0)
        buf_y.append(0.0)
        buf_y[len(buf_y) - 4 + label] = 1.0
        labels.append(label)

        # 每 20 步：8 轮 SGD 扫全缓冲 + 遥测
        if step > 0 and step % 20 == 0:
            n = len(labels)
            loss_sum = 0.0
            acc = 0
            for s in range(n):
                smp: list[float] = []
                smp.append(buf_x[s * 4 + 0])
                smp.append(buf_x[s * 4 + 1])
                smp.append(buf_x[s * 4 + 2])
                smp.append(buf_x[s * 4 + 3])
                yoh: list[float] = []
                yoh.append(buf_y[s * 4 + 0])
                yoh.append(buf_y[s * 4 + 1])
                yoh.append(buf_y[s * 4 + 2])
                yoh.append(buf_y[s * 4 + 3])
                for e in range(16):
                    loss_sum = loss_sum + lab_train_step(smp, yoh, w1, b1, w2, b2, lr)
                p2 = lab_forward(smp, w1, b1, w2, b2)
                bp = 0
                bv = p2[0]
                for ci in range(1, 4):
                    if p2[ci] > bv:
                        bv = p2[ci]
                        bp = ci
                if bp == labels[s]:
                    acc = acc + 1
            err = dx
            if err < 0.0:
                err = -dx
            ey = dy
            if ey < 0.0:
                ey = -dy
            print(step, loss_sum / (n * 8), acc * 100 / n, err + ey)
