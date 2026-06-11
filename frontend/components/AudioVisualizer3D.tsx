"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";

interface AudioVisualizer3DProps {
    audioStream: MediaStream | null;
    isActive: boolean;
}

interface Ripple { birthTime: number; group: THREE.Group; }

const clamp01 = (value: number): number => Math.min(1, Math.max(0, value));

const smoothAsymmetric = (
    current: number,
    target: number,
    dt: number,
    attackRate: number,
    releaseRate: number
): number => {
    const rate = target > current ? attackRate : releaseRate;
    const alpha = 1 - Math.exp(-rate * dt);
    return current + (target - current) * alpha;
};

const applyNoiseGate = (value: number, threshold: number): number => {
    if (value <= threshold) return 0;
    return clamp01((value - threshold) / (1 - threshold));
};

const noiseGLSL = `
    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
    vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

    float snoise(vec3 v) {
        const vec2 C = vec2(1.0/6.0, 1.0/3.0);
        const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);

        vec3 i  = floor(v + dot(v, C.yyy));
        vec3 x0 = v - i + dot(i, C.xxx);

        vec3 g = step(x0.yzx, x0.xyz);
        vec3 l = 1.0 - g;
        vec3 i1 = min(g.xyz, l.zxy);
        vec3 i2 = max(g.xyz, l.zxy);

        vec3 x1 = x0 - i1 + C.xxx;
        vec3 x2 = x0 - i2 + C.yyy;
        vec3 x3 = x0 - D.yyy;

        i = mod289(i);
        vec4 p = permute(permute(permute(
                            i.z + vec4(0.0, i1.z, i2.z, 1.0))
                        + i.y + vec4(0.0, i1.y, i2.y, 1.0))
                        + i.x + vec4(0.0, i1.x, i2.x, 1.0));

        float n_ = 0.142857142857;
        vec3 ns = n_ * D.wyz - D.xzx;

        vec4 j = p - 49.0 * floor(p * ns.z * ns.z);

        vec4 x_ = floor(j * ns.z);
        vec4 y_ = floor(j - 7.0 * x_);

        vec4 x = x_ * ns.x + ns.yyyy;
        vec4 y = y_ * ns.x + ns.yyyy;
        vec4 h = 1.0 - abs(x) - abs(y);

        vec4 b0 = vec4(x.xy, y.xy);
        vec4 b1 = vec4(x.zw, y.zw);

        vec4 s0 = floor(b0)*2.0 + 1.0;
        vec4 s1 = floor(b1)*2.0 + 1.0;
        vec4 sh = -step(h, vec4(0.0));

        vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
        vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;

        vec3 p0 = vec3(a0.xy,h.x);
        vec3 p1 = vec3(a0.zw,h.y);
        vec3 p2 = vec3(a1.xy,h.z);
        vec3 p3 = vec3(a1.zw,h.w);

        vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
        p0 *= norm.x;
        p1 *= norm.y;
        p2 *= norm.z;
        p3 *= norm.w;

        vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
        m = m * m;
        return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
    }
`;

const vertexShader = `
    ${noiseGLSL}

    uniform float uTime;
    uniform float uBassFrequency;
    uniform float uMidFrequency;
    uniform float uTrebleFrequency;
    uniform float uAverageFrequency;
    uniform float uActivity;
    uniform float uRadiusOffset;

    varying float vDisplacement;
    varying vec3 vNormal;
    varying vec3 vPosition;

    void main() {
        vNormal = normalize(normalMatrix * normal);
        vec3 pos = position;

        // Localized spike momentum (surface crawl), independent from mesh rotation
        float flowTime = uTime * mix(0.25, 0.38, uActivity);

        // Directional flow vectors keep motion on the surface detail itself
        vec3 flow1 = vec3(0.17, -0.11, 0.08) * flowTime;
        vec3 flow2 = vec3(-0.09, 0.14, -0.12) * flowTime;
        vec3 flow3 = vec3(0.13, 0.07, -0.15) * flowTime;

        // Per-vertex phase offset creates crawling/snail-like movement
        float phase = dot(normalize(position), vec3(0.6, 0.2, 0.75));
        float phaseWave = sin(flowTime * 1.95 + phase * 4.0) * 0.095;

        // Idle warp keeps visible movement even when input is inactive
        float idleWarp = (1.0 - uActivity) * sin(uTime * 1.2 + phase * 3.2) * 0.085;

        // Audio-driven amplitude with higher frequency sensitivity
        float bassN = uBassFrequency / 255.0;
        float midN  = uMidFrequency / 255.0;
        float trebN = uTrebleFrequency / 255.0;

        // Multi-octave noise with frequency-responsive spread (including low/mid widening)
        float baseSpread = 0.8;
        float lowMidN = (bassN * 0.55 + midN * 0.45);
        float freqSpreadBoost = (trebN * 0.34) + (midN * 0.24) + (bassN * 0.18);
        float lowMidWidthBoost = lowMidN * 0.32;

        float n1 = snoise(pos * (baseSpread - freqSpreadBoost - lowMidWidthBoost * 0.25) + flow1 + vec3(phaseWave + idleWarp));
        float n2 = snoise(pos * (1.6 - freqSpreadBoost * 0.6 - lowMidWidthBoost * 0.45) + flow2 + vec3(phaseWave * 0.8 + idleWarp * 0.8)) * 0.5;
        float n3 = snoise(pos * (3.6 - freqSpreadBoost * 0.4) + flow3 + vec3(phaseWave * 0.6 + idleWarp * 0.5)) * 0.25 * (0.28 + 0.72 * uActivity);
        float combined = n1 + n2 + n3;

        // Shaping: round hills (idle) -> sharp spikes (active)
        float expo = mix(1.0, 0.4, uActivity);
        float shaped = pow(abs(combined), expo) * sign(combined);

        // Higher frequency boost for much better sensitivity
        float highFreqBoost = trebN * trebN * 2.0;  // Increased from 1.5
        float totalFreqSensitivity = bassN * 0.68 + midN * 0.88 + trebN * 1.0 + highFreqBoost;

        // Idle: much smaller and calmer spikes
        float idleAmp = 0.14 + sin(uTime * 0.68) * 0.045;

        // Active: enhanced response with high frequency sensitivity
        float audioAmp = totalFreqSensitivity;
        // Dynamic boost based on frequency content - increased for better active response
        float sensitivityMultiplier = 2.55 + (trebN * 1.05) + (lowMidN * 0.35);
        float boostedAudio = audioAmp * sensitivityMultiplier + uActivity * 0.25;  // Increased activity boost

        float amplitude = mix(idleAmp, boostedAudio, uActivity);

        // Dynamic max height based on frequency content - much better active response
        float dynamicMaxH = mix(0.3, 1.05 + (trebN * 0.55), uActivity);
        float displacement = tanh(shaped * amplitude * (2.2 + trebN * 0.6)) * dynamicMaxH;  // Increased multipliers

        // Hard cap: normal voices stretch clearly, high-frequency content reaches full top extension
        float hardCap = mix(0.9 + lowMidN * 0.2, 1.42, trebN);
        displacement = min(displacement, hardCap);

        // Allow only tiny inward dimples
        displacement = max(displacement, -0.03);

        pos += normal * (displacement + uRadiusOffset);

        vDisplacement = displacement;
        vPosition = (modelViewMatrix * vec4(pos, 1.0)).xyz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
    }
`;

const fragmentShader = `
    uniform float uTime;
    uniform float uAverageFrequency;
    uniform float uActivity;
    uniform vec3 uBaseColor;
    uniform vec3 uGlowColor;
    uniform vec3 uPeakColor;

    varying float vDisplacement;
    varying vec3 vNormal;
    varying vec3 vPosition;

    void main() {
        float height = smoothstep(0.0, 0.45, abs(vDisplacement));
        float avgN = uAverageFrequency / 255.0;

        vec3 viewDir = normalize(-vPosition);
        float fresnel = 1.0 - max(dot(viewDir, vNormal), 0.0);
        fresnel = pow(fresnel, 3.0);

        // More cohesive color blending
        vec3 color = mix(uBaseColor, uGlowColor, height * 0.8);
        color = mix(color, uPeakColor, pow(height, 2.5) * 0.4);
        color += uGlowColor * fresnel * (0.1 + uActivity * 0.12);
        color *= 0.92 + uActivity * 0.08;

        // Neon glow rim border for cohesive appearance
        float neonRim = pow(fresnel, 2.2);
        vec3 neonColor = uGlowColor * 1.4;
        color += neonColor * neonRim * (0.25 + avgN * 0.2);

        // Saturation-preserving clamp
        float maxChannel = max(color.r, max(color.g, color.b));
        if (maxChannel > 1.1) {
            color = mix(color, color / maxChannel, 0.65);
        }

        float alpha = 0.6 - fresnel * 0.12;
        gl_FragColor = vec4(color, alpha);
    }
`;

export function AudioVisualizer3D({ audioStream, isActive }: AudioVisualizer3DProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const isActiveRef = useRef(isActive);
    const sceneRef = useRef<{
        scene: THREE.Scene;
        camera: THREE.PerspectiveCamera;
        renderer: THREE.WebGLRenderer;
        composer: EffectComposer;
        solidSphere: THREE.Mesh;
        wireSphere: THREE.Mesh;
        solidMaterial: THREE.ShaderMaterial;
        wireMaterial: THREE.ShaderMaterial;
        ripples: Ripple[];
        lastRippleTime: number;
        analyser: AnalyserNode | null;
        dataArray: Uint8Array | null;
        audioContext: AudioContext | null;
        smoothedAudio: number;
        smoothedBass: number;
        smoothedMid: number;
        smoothedHigh: number;
        smoothedActivity: number;
        noiseFloorAudio: number;
        noiseFloorBass: number;
        noiseFloorMid: number;
        noiseFloorHigh: number;
        runtime: number;
        visualTime: number;
        rotationY: number;
        rotationXPhase: number;
        idleBreathPhase: number;
    } | null>(null);

    useEffect(() => { isActiveRef.current = isActive; }, [isActive]);

    useEffect(() => {
        if (!containerRef.current) return;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(
            50, window.innerWidth / window.innerHeight, 0.1, 1000
        );
        const renderer = new THREE.WebGLRenderer({
            antialias: true, alpha: true, powerPreference: "high-performance",
        });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 0.92;
        containerRef.current.appendChild(renderer.domElement);
        camera.position.z = 16;
        scene.background = new THREE.Color(0x030515);

        const composer = new EffectComposer(renderer);
        composer.addPass(new RenderPass(scene, camera));
        const bloomPass = new UnrealBloomPass(
            new THREE.Vector2(window.innerWidth, window.innerHeight),
            0.65,
            0.72,
            0.22
        );
        composer.addPass(bloomPass);

        const RADIUS = 4;
        const solidUniforms = {
            uTime: { value: 0 },
            uBassFrequency: { value: 0 },
            uMidFrequency: { value: 0 },
            uTrebleFrequency: { value: 0 },
            uAverageFrequency: { value: 0 },
            uActivity: { value: 0 },
            uRadiusOffset: { value: 0 },
            uBaseColor: { value: new THREE.Color(0x5b21b6) },
            uGlowColor: { value: new THREE.Color(0x8b5cf6) },
            uPeakColor: { value: new THREE.Color(0xa78bfa) },
        };

        const wireUniforms = {
            uTime: { value: 0 },
            uBassFrequency: { value: 0 },
            uMidFrequency: { value: 0 },
            uTrebleFrequency: { value: 0 },
            uAverageFrequency: { value: 0 },
            uActivity: { value: 0 },
            uRadiusOffset: { value: 0.003 },  // Reduced for more cohesive appearance
            uBaseColor: { value: new THREE.Color(0x7c3aed) },
            uGlowColor: { value: new THREE.Color(0xa855f7) },
            uPeakColor: { value: new THREE.Color(0xc084fc) },
        };

        const solidGeometry = new THREE.IcosahedronGeometry(RADIUS * 0.98, 42);
        const solidMaterial = new THREE.ShaderMaterial({
            vertexShader,
            fragmentShader,
            uniforms: solidUniforms,
            transparent: true,
            depthWrite: true,
            side: THREE.FrontSide,
        });
        const solidSphere = new THREE.Mesh(solidGeometry, solidMaterial);
        scene.add(solidSphere);

        const wireGeometry = new THREE.IcosahedronGeometry(RADIUS, 42);
        const wireMaterial = new THREE.ShaderMaterial({
            vertexShader,
            fragmentShader,
            uniforms: wireUniforms,
            wireframe: true,
            transparent: true,
            depthWrite: false,
            side: THREE.FrontSide,  // Changed from DoubleSide for better cohesion
            blending: THREE.AdditiveBlending,
        });
        const wireSphere = new THREE.Mesh(wireGeometry, wireMaterial);
        scene.add(wireSphere);

        const starsGeo = new THREE.BufferGeometry();
        const starCount = 1400;
        const starPositions = new Float32Array(starCount * 3);
        for (let i = 0; i < starCount; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            const r = 7 + Math.random() * 18;
            starPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            starPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
            starPositions[i * 3 + 2] = r * Math.cos(phi);
        }
        starsGeo.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
        const stars = new THREE.Points(
            starsGeo,
            new THREE.PointsMaterial({
                color: 0xc084fc,
                size: 0.02,
                transparent: true,
                opacity: 0.35,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
            })
        );
        scene.add(stars);

        // ── 4. Ripple arcs (thin sharp lines, left + right) ───────────
        const MAX_RIPPLES = 4;
        const ripplePool: Ripple[] = [];

        const createRippleArc = (startAngle: number, arcLength: number, segments: number): THREE.Line => {
            const points: THREE.Vector3[] = [];
            for (let j = 0; j <= segments; j++) {
                const angle = startAngle + (j / segments) * arcLength;
                points.push(new THREE.Vector3(
                    Math.cos(angle) * RADIUS,
                    Math.sin(angle) * RADIUS,
                    0
                ));
            }
            const geo = new THREE.BufferGeometry().setFromPoints(points);
            const mat = new THREE.LineBasicMaterial({
                color: 0xc4b5fd, // Light violet ripples
                transparent: true,
                opacity: 0,
                blending: THREE.AdditiveBlending,
            });
            return new THREE.Line(geo, mat);
        };

        const createRippleGroup = (): THREE.Group => {
            const group = new THREE.Group();
            // Left arc (~70% of semicircle)
            const arcLen = Math.PI * 0.7;
            const leftArc = createRippleArc(Math.PI * 0.65, arcLen, 48);
            group.add(leftArc);
            // Right arc (~70% of semicircle)
            const rightArc = createRippleArc(-Math.PI * 0.35, arcLen, 48);
            group.add(rightArc);
            return group;
        };

        sceneRef.current = {
            scene,
            camera,
            renderer,
            composer,
            solidSphere,
            wireSphere,
            solidMaterial,
            wireMaterial,
            ripples: ripplePool,
            lastRippleTime: -5,
            analyser: null, dataArray: null, audioContext: null,
            smoothedAudio: 0, smoothedBass: 0, smoothedMid: 0, smoothedHigh: 0,
            smoothedActivity: 0,
            noiseFloorAudio: 0,
            noiseFloorBass: 0,
            noiseFloorMid: 0,
            noiseFloorHigh: 0,
            runtime: 0,
            visualTime: 0,
            rotationY: 0,
            rotationXPhase: 0,
            idleBreathPhase: 0,
        };

        // ── Animation ─────────────────────────────────────────────────
        let animId: number;
        const clock = new THREE.Clock();
        const RIPPLE_INTERVAL = 5.0;
        const RIPPLE_DURATION = 3.5;
        const RIPPLE_MAX_SCALE = 3.5;

        const animate = () => {
            animId = requestAnimationFrame(animate);
            const dt = Math.min(clock.getDelta(), 0.05);
            const ctx = sceneRef.current;
            if (!ctx) return;

            ctx.runtime += dt;
            ctx.visualTime = (ctx.visualTime + dt) % 10000;
            const t = ctx.runtime;

            const { analyser, dataArray, solidSphere, wireSphere, solidMaterial, wireMaterial, ripples } = ctx;

            // ── Audio analysis ────────────────────────────────────────
            let rawAudio = 0, rawBass = 0, rawMid = 0, rawHigh = 0;
            if (analyser && dataArray && isActiveRef.current) {
                analyser.getByteFrequencyData(dataArray as Uint8Array<ArrayBuffer>);
                const len = dataArray.length;
                let sum = 0;
                for (let i = 0; i < len; i++) sum += dataArray[i];
                rawAudio = clamp01((sum / len / 255) * 3.5);
                const bassEnd = Math.floor(len * 0.12);
                let bs = 0; for (let i = 0; i < bassEnd; i++) bs += dataArray[i];
                rawBass = clamp01((bs / bassEnd / 255) * 2.5);
                const midStart = Math.floor(len * 0.12), midEnd = Math.floor(len * 0.55);
                let ms = 0; for (let i = midStart; i < midEnd; i++) ms += dataArray[i];
                rawMid = clamp01((ms / (midEnd - midStart) / 255) * 3.0);
                const hiStart = Math.floor(len * 0.55), hiEnd = Math.floor(len * 0.85);
                let hs = 0; for (let i = hiStart; i < hiEnd; i++) hs += dataArray[i];
                rawHigh = clamp01((hs / (hiEnd - hiStart) / 255) * 2.8);

                // Adaptive noise floor counters prolonged mic auto-gain drift/hyper-sensitivity
                const floorFollow = 1 - Math.exp(-0.55 * dt);
                ctx.noiseFloorAudio += (rawAudio - ctx.noiseFloorAudio) * floorFollow;
                ctx.noiseFloorBass += (rawBass - ctx.noiseFloorBass) * floorFollow;
                ctx.noiseFloorMid += (rawMid - ctx.noiseFloorMid) * floorFollow;
                ctx.noiseFloorHigh += (rawHigh - ctx.noiseFloorHigh) * floorFollow;

                const audioFloor = clamp01(ctx.noiseFloorAudio * 0.72 + 0.01);
                const bassFloor = clamp01(ctx.noiseFloorBass * 0.72 + 0.012);
                const midFloor = clamp01(ctx.noiseFloorMid * 0.72 + 0.01);
                const highFloor = clamp01(ctx.noiseFloorHigh * 0.72 + 0.01);

                rawAudio = applyNoiseGate(rawAudio, audioFloor);
                rawBass = applyNoiseGate(rawBass, bassFloor);
                rawMid = applyNoiseGate(rawMid, midFloor);
                rawHigh = applyNoiseGate(rawHigh, highFloor);
            }

            const isSampling = Boolean(analyser && dataArray && isActiveRef.current);
            const targetAudio = isSampling ? rawAudio : 0;
            const targetBass = isSampling ? rawBass : 0;
            const targetMid = isSampling ? rawMid : 0;
            const targetHigh = isSampling ? rawHigh : 0;

            ctx.smoothedAudio = clamp01(smoothAsymmetric(ctx.smoothedAudio, targetAudio, dt, 18, 9));
            ctx.smoothedBass = clamp01(smoothAsymmetric(ctx.smoothedBass, targetBass, dt, 16, 8));
            ctx.smoothedMid = clamp01(smoothAsymmetric(ctx.smoothedMid, targetMid, dt, 16, 8));
            ctx.smoothedHigh = clamp01(smoothAsymmetric(ctx.smoothedHigh, targetHigh, dt, 18, 9));

            const audio = ctx.smoothedAudio;
            const bass = ctx.smoothedBass;
            const mid = ctx.smoothedMid;
            const high = ctx.smoothedHigh;
            const active = isActiveRef.current;

            ctx.idleBreathPhase = (ctx.idleBreathPhase + dt * 0.4) % (Math.PI * 2);
            const idleBreath = active ? 0 : Math.sin(ctx.idleBreathPhase) * 12 + 18;
            const currentBass = active ? bass * 255 : idleBreath * 1.2;
            const currentMid = active ? mid * 255 : idleBreath * 0.8;
            const currentTreble = active ? high * 255 : idleBreath * 0.5;
            const currentAvg = active ? audio * 255 : idleBreath;

            const livingBreath = Math.sin(ctx.idleBreathPhase * 1.2) * 0.03 + Math.sin(ctx.idleBreathPhase * 0.65) * 0.014;
            const breathEnvelope = active ? 0.45 : 1.0;
            const solidRadiusOffset = livingBreath * breathEnvelope;
            const wireRadiusOffset = 0.003 + livingBreath * (breathEnvelope * 1.15);

            const combinedEnergy = active
                ? clamp01(audio * 0.45 + bass * 0.2 + mid * 0.25 + high * 0.35)
                : 0;
            const activityTarget = active ? clamp01((combinedEnergy - 0.02) * 2.8) : 0;
            ctx.smoothedActivity = clamp01(smoothAsymmetric(ctx.smoothedActivity, activityTarget, dt, 16, 7));
            const activityLevel = Math.min(ctx.smoothedActivity, 0.95);

            solidMaterial.uniforms.uTime.value = ctx.visualTime;
            solidMaterial.uniforms.uBassFrequency.value = currentBass;
            solidMaterial.uniforms.uMidFrequency.value = currentMid;
            solidMaterial.uniforms.uTrebleFrequency.value = currentTreble;
            solidMaterial.uniforms.uAverageFrequency.value = currentAvg;
            solidMaterial.uniforms.uActivity.value = activityLevel;
            solidMaterial.uniforms.uRadiusOffset.value = solidRadiusOffset;

            wireMaterial.uniforms.uTime.value = ctx.visualTime;
            wireMaterial.uniforms.uBassFrequency.value = currentBass;
            wireMaterial.uniforms.uMidFrequency.value = currentMid;
            wireMaterial.uniforms.uTrebleFrequency.value = currentTreble;
            wireMaterial.uniforms.uAverageFrequency.value = currentAvg;
            wireMaterial.uniforms.uActivity.value = activityLevel;
            wireMaterial.uniforms.uRadiusOffset.value = wireRadiusOffset;

            // Stable frame-rate independent rotation with bounded audio reactivity
            const baseRotationSpeed = 0.0048;
            const rotationAudioBoost = 0.0042;
            const baseOscillationSpeed = 0.014;
            const oscillationAudioBoost = 0.007;
            const baseOscillationAmplitude = 0.007;
            const oscillationAmplitudeBoost = 0.003;

            const dynamicRotationSpeed = baseRotationSpeed + activityLevel * rotationAudioBoost;
            const dynamicOscillationSpeed = baseOscillationSpeed + activityLevel * oscillationAudioBoost;
            const dynamicOscillationAmplitude = baseOscillationAmplitude + activityLevel * oscillationAmplitudeBoost;

            ctx.rotationY = (ctx.rotationY + dynamicRotationSpeed * dt) % (Math.PI * 2);
            ctx.rotationXPhase = (ctx.rotationXPhase + dynamicOscillationSpeed * dt) % (Math.PI * 2);

            const ry = ctx.rotationY;
            const rx = Math.sin(ctx.rotationXPhase) * dynamicOscillationAmplitude;
            
            solidSphere.rotation.y = ry;
            solidSphere.rotation.x = rx;
            wireSphere.rotation.y = ry;
            wireSphere.rotation.x = rx;

            // ── Ripple arcs (every ~5s) ───────────────────────────────
            if (t - ctx.lastRippleTime >= RIPPLE_INTERVAL) {
                ctx.lastRippleTime = t;
                if (ripples.length >= MAX_RIPPLES) {
                    const old = ripples.shift()!;
                    scene.remove(old.group);
                    old.group.traverse((child) => {
                        if ((child as THREE.Line).geometry) (child as THREE.Line).geometry.dispose();
                        if ((child as THREE.Line).material) ((child as THREE.Line).material as THREE.Material).dispose();
                    });
                }
                const group = createRippleGroup();
                // Slight random tilt
                group.rotation.z = (Math.random() - 0.5) * 0.3;
                scene.add(group);
                ripples.push({ birthTime: t, group });
            }

            for (let i = ripples.length - 1; i >= 0; i--) {
                const rp = ripples[i];
                const age = t - rp.birthTime;
                const life = age / RIPPLE_DURATION;
                if (life > 1) {
                    scene.remove(rp.group);
                    rp.group.traverse((child) => {
                        if ((child as THREE.Line).geometry) (child as THREE.Line).geometry.dispose();
                        if ((child as THREE.Line).material) ((child as THREE.Line).material as THREE.Material).dispose();
                    });
                    ripples.splice(i, 1);
                    continue;
                }
                const eased = 1 - Math.pow(1 - life, 2.5);
                const scale = 1 + eased * (RIPPLE_MAX_SCALE - 1);
                rp.group.scale.setScalar(scale);
                const fadeIn = Math.min(life * 10, 1);
                const fadeOut = Math.pow(1 - life, 1.8);
                const opacity = fadeIn * fadeOut * 0.8;
                rp.group.traverse((child) => {
                    if ((child as THREE.Line).material) {
                        ((child as THREE.Line).material as THREE.LineBasicMaterial).opacity = opacity;
                    }
                });
            }

            composer.render();
        };

        animate();

        const handleResize = () => {
            if (!sceneRef.current) return;
            const { camera: cam, renderer: rnd, composer: cmp } = sceneRef.current;
            cam.aspect = window.innerWidth / window.innerHeight;
            cam.updateProjectionMatrix();
            rnd.setSize(window.innerWidth, window.innerHeight);
            cmp.setSize(window.innerWidth, window.innerHeight);
        };
        window.addEventListener("resize", handleResize);

        return () => {
            window.removeEventListener("resize", handleResize);
            cancelAnimationFrame(animId);
            if (sceneRef.current) {
                for (const r of sceneRef.current.ripples) {
                    sceneRef.current.scene.remove(r.group);
                    r.group.traverse((child) => {
                        if ((child as THREE.Line).geometry) (child as THREE.Line).geometry.dispose();
                        if ((child as THREE.Line).material) ((child as THREE.Line).material as THREE.Material).dispose();
                    });
                }
                sceneRef.current.solidMaterial.dispose();
                sceneRef.current.wireMaterial.dispose();
                sceneRef.current.composer.dispose();
                sceneRef.current.renderer.dispose();
                sceneRef.current.scene.clear();
                if (sceneRef.current.audioContext) {
                    sceneRef.current.audioContext.close();
                }
                sceneRef.current.analyser = null;
                sceneRef.current.dataArray = null;
                sceneRef.current.audioContext = null;
                sceneRef.current.smoothedAudio = 0;
                sceneRef.current.smoothedBass = 0;
                sceneRef.current.smoothedMid = 0;
                sceneRef.current.smoothedHigh = 0;
                sceneRef.current.smoothedActivity = 0;
                sceneRef.current.noiseFloorAudio = 0;
                sceneRef.current.noiseFloorBass = 0;
                sceneRef.current.noiseFloorMid = 0;
                sceneRef.current.noiseFloorHigh = 0;
            }
        };
    }, []);

    // ── Audio setup ───────────────────────────────────────────────────
    useEffect(() => {
        if (!audioStream) return;
        const AudioContextClass =
            window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const audioContext = new AudioContextClass();
        if (audioContext.state === "suspended") audioContext.resume();

        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.6;
        analyser.minDecibels = -80;
        analyser.maxDecibels = -10;

        const source = audioContext.createMediaStreamSource(audioStream);
        source.connect(analyser);
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        if (sceneRef.current) {
            sceneRef.current.analyser = analyser;
            sceneRef.current.dataArray = dataArray;
            sceneRef.current.audioContext = audioContext;
            sceneRef.current.smoothedAudio = 0;
            sceneRef.current.smoothedBass = 0;
            sceneRef.current.smoothedMid = 0;
            sceneRef.current.smoothedHigh = 0;
            sceneRef.current.smoothedActivity = 0;
            sceneRef.current.noiseFloorAudio = 0;
            sceneRef.current.noiseFloorBass = 0;
            sceneRef.current.noiseFloorMid = 0;
            sceneRef.current.noiseFloorHigh = 0;
        }

        return () => {
            source.disconnect();
            audioContext.close();
            if (sceneRef.current && sceneRef.current.audioContext === audioContext) {
                sceneRef.current.analyser = null;
                sceneRef.current.dataArray = null;
                sceneRef.current.audioContext = null;
                sceneRef.current.smoothedAudio = 0;
                sceneRef.current.smoothedBass = 0;
                sceneRef.current.smoothedMid = 0;
                sceneRef.current.smoothedHigh = 0;
                sceneRef.current.smoothedActivity = 0;
                sceneRef.current.noiseFloorAudio = 0;
                sceneRef.current.noiseFloorBass = 0;
                sceneRef.current.noiseFloorMid = 0;
                sceneRef.current.noiseFloorHigh = 0;
            }
        };
    }, [audioStream]);

    return <div ref={containerRef} className="w-full h-full" />;
}
