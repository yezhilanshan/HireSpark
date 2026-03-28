/**
 * AudioWorklet 处理器 - 将音频数据转换为 PCM 格式
 * 用于阿里巴巴 DashScope ASR 实时识别
 */
class AudioProcessor extends AudioWorkletProcessor {
    constructor(options) {
        super()
        this.targetSampleRate = options?.processorOptions?.sampleRate || 16000
        this.inputSampleRate = sampleRate
        this.resampleRatio = this.inputSampleRate / this.targetSampleRate
        this.bufferSize = 3200 // 每次发送 3200 字节
        this.buffer = new Int16Array(1600)
        this.bufferIndex = 0
        this.pendingInput = []
        this.resampleOffset = 0

        this.port.postMessage({
            type: 'meta',
            inputSampleRate: this.inputSampleRate,
            targetSampleRate: this.targetSampleRate,
            resampleRatio: this.resampleRatio
        })
    }

    pushSample(sample) {
        const s = Math.max(-1, Math.min(1, sample))
        this.buffer[this.bufferIndex++] = s < 0 ? s * 0x8000 : s * 0x7FFF

        if (this.bufferIndex >= this.buffer.length) {
            let energy = 0
            for (let i = 0; i < this.buffer.length; i++) {
                const normalized = this.buffer[i] / 0x7FFF
                energy += normalized * normalized
            }
            const rms = Math.sqrt(energy / this.buffer.length)
            const pcmBuffer = new ArrayBuffer(this.buffer.length * 2)
            const view = new DataView(pcmBuffer)
            for (let i = 0; i < this.buffer.length; i++) {
                view.setInt16(i * 2, this.buffer[i], true)
            }
            this.port.postMessage({
                type: 'audio-chunk',
                audio: pcmBuffer,
                rms
            })
            this.bufferIndex = 0
        }
    }

    process(inputs) {
        const input = inputs[0]
        if (!input || !input.length) return true

        const channelData = input[0]

        for (let i = 0; i < channelData.length; i++) {
            this.pendingInput.push(channelData[i])
        }

        while (this.resampleOffset + this.resampleRatio <= this.pendingInput.length - 1) {
            const index = Math.floor(this.resampleOffset)
            const nextIndex = index + 1
            const fraction = this.resampleOffset - index
            const current = this.pendingInput[index]
            const next = this.pendingInput[nextIndex]
            const sample = current + (next - current) * fraction
            this.pushSample(sample)
            this.resampleOffset += this.resampleRatio
        }

        const consumed = Math.max(0, Math.floor(this.resampleOffset) - 1)
        if (consumed > 0) {
            this.pendingInput = this.pendingInput.slice(consumed)
            this.resampleOffset -= consumed
        }

        return true
    }
}

registerProcessor('audio-processor', AudioProcessor)
