import time
from typing import Any, Dict
from video_ai_system.modules.module_interface import VideoModule

class BenchmarkModule(VideoModule):
    """
    A simple module to simulate processing work for benchmarking purposes.
    """
    def __init__(self):
        self.delay_seconds = 0.01

    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initializes the module with a configured simulation delay.
        """
        self.delay_seconds = config.get("simulation_delay_seconds", 0.01)
        print(f"BenchmarkModule initialized with delay: {self.delay_seconds}s")

    def process(self, frame: Any) -> Any:
        """
        Simulates a processing delay.
        """
        time.sleep(self.delay_seconds)
        return frame

    def teardown(self) -> None:
        """
        No-op for this simple module.
        """
        print("BenchmarkModule torn down.")
        pass