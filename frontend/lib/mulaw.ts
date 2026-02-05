/**
 * Mu-Law (G.711u) to Linear PCM decoder.
 * Twilio streams 8000Hz, 8-bit Mu-Law.
 */

// G.711 u-law to 16-bit PCM lookup table
// Generated from standard algorithm
const MU_LAW_LOOKUP = new Int16Array(256);

(function generateMuLawTable() {
    const BIAS = 0x84;
    for (let i = 0; i < 256; i++) {
        let mu = ~i;
        let sign = (mu & 0x80);
        let exponent = (mu & 0x70) >> 4;
        let mantissa = mu & 0x0f;
        let sample = ((mantissa << 3) + 0x84) << exponent;
        sample -= 0x84;
        if (sign !== 0) sample = -sample;
        MU_LAW_LOOKUP[i] = sample;
    }
})();

/**
 * Decodes a Mu-Law byte buffer (Uint8Array) to Float32Array (PCM).
 * Normalizes 16-bit PCM (-32768 to 32767) to Float32 (-1.0 to 1.0).
 */
export function decodeMuLaw(data: Uint8Array): Float32Array {
    const length = data.length;
    const result = new Float32Array(length);

    for (let i = 0; i < length; i++) {
        // Lookup 16-bit value and normalize to -1..1
        const pcm16 = MU_LAW_LOOKUP[data[i]];
        result[i] = pcm16 / 32768.0;
    }

    return result;
}
