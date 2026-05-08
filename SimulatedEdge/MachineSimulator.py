import random

# -----------------------Machine Simulation --------------------------
class MachineSimulator:
    def __init__(self):
        self.step = 0

    def simulate_machine(self, switch_state):
        self.step += 1

        if switch_state == "OFF":
            temp = 31 + random.uniform(-0.5, 0.5)
            vib = random.uniform(0.0, 0.01)
            current = random.uniform(0.0, 0.08)
            return round(temp, 2), round(vib, 3), round(current, 2)

        # Normal operation
        if self.step < 10:
            temp = 40 + random.uniform(-1, 1)
            vib = 0.15 + random.uniform(-0.02, 0.02)
            current = 3 + random.uniform(-0.2, 0.2)

        elif self.step < 20:
            progress = (self.step - 10) / 10
            temp = 40 + 5 * progress + random.uniform(-1, 1)
            vib = 0.15 + 0.2 * progress + random.uniform(-0.02, 0.02)
            current = 3 + 0.5 * progress + random.uniform(-0.2, 0.2)

        # Overload phase
        elif self.step < 25:
            temp = 50 + random.uniform(-1, 1)
            vib = 0.35 + random.uniform(-0.05, 0.05)
            current = 5 + random.uniform(-0.5, 0.5)

        # Recovery phase
        else:
            temp = 42 + random.uniform(-1, 1)
            vib = 0.18 + random.uniform(-0.02, 0.02)
            current = 3.2 + random.uniform(-0.2, 0.2)

        if self.step > 30:
            self.step = 0

        return round(temp, 2), round(vib, 3), round(current, 2)
#--------------------------------------------------------------------------------------------
