from kostalpiko.kostalpiko import Piko

import time


class PikoHolder(Piko):
    last_update = 0
    update_running = False

    def __init__(self, host=None, username="pvserver", password="pvwr") -> None:
        super().__init__(host, username, password)

    def update(self):
        if self.update_running:
            return
        if time.time() - self.last_update <= 30.0:
            return
        self.update_running = True
        self.last_update = time.time()
        try:
            super().update()
        finally:
            # Always release the flag, otherwise one failed request would
            # block all further updates until HA is restarted.
            self.update_running = False
