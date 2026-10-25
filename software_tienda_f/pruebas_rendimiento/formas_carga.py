from locust import LoadTestShape


class CargaSostenida(LoadTestShape):
    def tick(self):
        if self.get_run_time() < 180:
            return (30, 1)
        return None


class EstresEscalonado(LoadTestShape):
    def tick(self):
        paso = int(self.get_run_time() // 45)
        if paso >= 10:
            return None
        return ((paso + 1) * 20, 5)
