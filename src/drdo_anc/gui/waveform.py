import numpy as np

class WaveformProcessor:
    """Reduces high-resolution audio samples into a smaller format for GUI rendering."""
    
    def __init__(self, target_points: int = 1000):
        self.target_points = target_points
        self._last_input = np.zeros(self.target_points)
        self._last_output = np.zeros(self.target_points)

    def process(self, input_chunk: np.ndarray, output_chunk: np.ndarray):
        """Downsamples audio chunks for visualization.
        
        Uses max pooling (peak detection) or simple decimation to preserve visual envelope.
        """
        # If chunks are 1D arrays
        if input_chunk is not None and len(input_chunk) > 0:
            self._last_input = self._reduce(input_chunk)
            
        if output_chunk is not None and len(output_chunk) > 0:
            self._last_output = self._reduce(output_chunk)
            
        return self._last_input, self._last_output

    def _reduce(self, data: np.ndarray) -> np.ndarray:
        """Reduces the data to self.target_points length."""
        if len(data) <= self.target_points:
            # Pad if too short
            padded = np.zeros(self.target_points)
            padded[:len(data)] = data
            return padded
            
        # Downsample by picking max in each window (peak envelope)
        window_size = len(data) // self.target_points
        truncated_len = window_size * self.target_points
        
        # Reshape and take max of absolute values to show envelope
        reshaped = data[:truncated_len].reshape(self.target_points, window_size)
        
        # We can keep the sign of the max absolute value for a nicer visual
        max_idx = np.argmax(np.abs(reshaped), axis=1)
        reduced = reshaped[np.arange(self.target_points), max_idx]
        return reduced
