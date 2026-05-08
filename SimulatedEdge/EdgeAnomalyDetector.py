import statistics
MIN_TEMP_THRESHOLD = 2.0
MIN_VIB_THRESHOLD = 0.1
MIN_CURR_THRESHOLD = 0.5

class EdgeAnomalyDetector:
    def __init__(self, window_size=20, sigma_threshold=2.5):
        self.__window_size = window_size
        self.__sigma_threshold = sigma_threshold
        self.__temp_window = []
        self.__vib_window = []
        self.__current_window = []

    def _update_window(self, window, value):
        window.append(value)
        if len(window) > self.__window_size:
            window.pop(0)

    def _is_anomaly(self, value, window, threshold):
        if len(window) < self.__window_size:
            return False

        mean = statistics.mean(window)
        std = statistics.stdev(window)

        if std == 0:
            return False

        return abs(value - mean) > max(self.__sigma_threshold * std, threshold)
    
    def update_current_window(self, value):
        self._update_window(self.__current_window, value)
    def update_temperature_window(self, value):
        self._update_window(self.__temp_window, value)
    def update_vibration_window(self, value):
        self._update_window(self.__vib_window, value)

    def reset(self):
        self.__temp_window = []
        self.__vib_window = []
        self.__current_window = []

    def check_current_anomaly(self, current):
        return self._is_anomaly(current, self.__current_window, MIN_CURR_THRESHOLD)
    def check_temperature_anomaly(self, temp):
        return self._is_anomaly(temp, self.__temp_window, MIN_TEMP_THRESHOLD)
    def check_vibration_anomaly(self, vib):    
        return self._is_anomaly(vib, self.__vib_window, MIN_VIB_THRESHOLD)
