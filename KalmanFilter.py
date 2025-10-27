class KalmanFilter:
    """
    Single-dimensional Kalman filter.

    This class implements a simple 1D Kalman filter to estimate a scalar state from noisy
    measurements. It maintains an internal set of parameters (stored in the `parameter`
    dictionary) representing the current estimate, error covariances, Kalman gain, and
    noise covariances.

    Attributes (in `parameter` dict):

        last_P (float) : Posterior error covariance from the previous update (default 0.02).
        now_P  (float) : Predicted error covariance for the current step.
        output (float) : Current state estimate (filtered value), initialized to 0.
        Kg     (float) : Current Kalman gain.
        Q      (float) : Process (model) noise covariance, controls trust in model (default 0.001).
        R      (float) : Measurement noise covariance, controls trust in measurements (default 0.543).

    Notes:

        - This implementation is intended for scalar signals only.
        - Initial state and covariances are simple defaults; tune Q and R to match the
          characteristics of your process and sensors for best results.
        - The class is not inherently thread-safe; use separate instances or external
          synchronization if updating from multiple threads.
    """
    
    parameter = {
        "last_P": 0.02,     
        "now_P": 0,         
        "output": 0,       
        "Kg": 0,            
        "Q": 0.001,         
        "R": 0.543   
    }
    def kalman_filter(self, measurement):
        """
        A single-dimensional Kalman filter algorithm, this function needs to be called every time a new value is measured

        :param measurement: the measured value
        :return: the filtered output
        """

        self.parameter["now_P"] = self.parameter["last_P"] + self.parameter["Q"]
        self.parameter["Kg"] = self.parameter["now_P"] / (self.parameter["now_P"] + self.parameter["R"])
        self.parameter["output"] = self.parameter["output"] + self.parameter["Kg"] * (measurement - self.parameter["output"])
        self.parameter["last_P"] = (1 - self.parameter["Kg"]) * self.parameter["now_P"]
        return self.parameter["output"]