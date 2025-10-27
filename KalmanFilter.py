class KalmanFilter:
    parameter = {
        "last_P": 0.02,     # 上次估计协方差
        "now_P": 0,         # 本次估计协方差
        "output": 0,        # 滤波输出
        "Kg": 0,            # kalman增益
        "Q": 0.001,         # 过程噪声协方差
        "R": 0.543          # 观测噪声协方差
    }
    def kalmanFilter(self, measurement):
        # 预测协方差：t时刻系统估算协方差 = t-1时刻的系统协方差 + 过程噪声协方差
        self.parameter["now_P"] = self.parameter["last_P"] + self.parameter["Q"]

        # Kalman增益：kalman增益 = t时刻系统估算协方差 / (t时刻系统估算协方差 + 观测噪声协方差)
        self.parameter["Kg"] = self.parameter["now_P"] / (self.parameter["now_P"] + self.parameter["R"])

        # 更新最优值：t时刻状态变量的最优值 = 状态变量的预测值 + 卡尔曼增益 * （测量值 - 状态变量的预测值）
        self.parameter["output"] = self.parameter["output"] + self.parameter["Kg"] * (measurement - self.parameter["output"])

        # 误差协方差更新
        self.parameter["last_P"] = (1 - self.parameter["Kg"]) * self.parameter["now_P"]
        return self.parameter["output"]