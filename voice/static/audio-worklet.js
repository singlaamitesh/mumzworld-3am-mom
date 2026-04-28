// PCM capture worklet: emits Float32 frames at the AudioContext's native sample rate.
// The main thread resamples to 16kHz and converts to Int16 before sending over the WS.
class PCMCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    // ~100ms at 48kHz = 4800 samples. Smaller buffer = lower latency but more WS frames.
    this.bufferSize = 4800;
    this.buffer = new Float32Array(this.bufferSize);
    this.idx = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const samples = input[0];
    for (let i = 0; i < samples.length; i++) {
      this.buffer[this.idx++] = samples[i];
      if (this.idx >= this.bufferSize) {
        this.port.postMessage(this.buffer.slice());
        this.idx = 0;
      }
    }
    return true;
  }
}

registerProcessor('pcm-capture', PCMCapture);
