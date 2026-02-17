"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface AudioVisualizer3DProps {
    audioStream: MediaStream | null;
    isActive: boolean;
}

// ── 3D Noise ──────────────────────────────────────────────────────────
function mod289(x: number) { return x - Math.floor(x / 289) * 289; }
function permute(x: number) { return mod289((x * 34 + 1) * x); }
function fade(t: number) { return t * t * t * (t * (t * 6 - 15) + 10); }

function noise3D(x: number, y: number, z: number): number {
    const X = Math.floor(x) & 255, Y = Math.floor(y) & 255, Z = Math.floor(z) & 255;
    x -= Math.floor(x); y -= Math.floor(y); z -= Math.floor(z);
    const u = fade(x), v = fade(y), w = fade(z);
    const grad = (hash: number, gx: number, gy: number, gz: number) => {
        const h = hash & 15;
        const a = h < 8 ? gx : gy;
        const b = h < 4 ? gy : h === 12 || h === 14 ? gx : gz;
        return ((h & 1) === 0 ? a : -a) + ((h & 2) === 0 ? b : -b);
    };
    const p = (n: number) => permute(n);
    const A = p(X) + Y, AA = p(A) + Z, AB = p(A + 1) + Z;
    const B = p(X + 1) + Y, BA = p(B) + Z, BB = p(B + 1) + Z;
    const lerp = (t: number, a: number, b: number) => a + t * (b - a);
    return lerp(w,
        lerp(v, lerp(u, grad(p(AA), x, y, z), grad(p(BA), x - 1, y, z)),
            lerp(u, grad(p(AB), x, y - 1, z), grad(p(BB), x - 1, y - 1, z))),
        lerp(v, lerp(u, grad(p(AA + 1), x, y, z - 1), grad(p(BA + 1), x - 1, y, z - 1)),
            lerp(u, grad(p(AB + 1), x, y - 1, z - 1), grad(p(BB + 1), x - 1, y - 1, z - 1)))
    );
}

function fbm(x: number, y: number, z: number, octaves = 4): number {
    let value = 0, amplitude = 0.5, frequency = 1;
    for (let i = 0; i < octaves; i++) {
        value += amplitude * noise3D(x * frequency, y * frequency, z * frequency);
        amplitude *= 0.5;
        frequency *= 2.0;
    }
    return value;
}

// ── Types ─────────────────────────────────────────────────────────────
interface Ripple { birthTime: number; group: THREE.Group; }

interface FlareLayer {
    mesh: THREE.Mesh;
    origPositions: THREE.BufferAttribute;
    baseRadius: number;
    noiseOffset: number;
}

export function AudioVisualizer3D({ audioStream, isActive }: AudioVisualizer3DProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const isActiveRef = useRef(isActive);
    const sceneRef = useRef<{
        scene: THREE.Scene;
        camera: THREE.PerspectiveCamera;
        renderer: THREE.WebGLRenderer;
        sphere: THREE.Mesh;
        innerFill: THREE.Mesh;
        innerCore: THREE.Mesh;
        flareLayers: FlareLayer[];
        ripples: Ripple[];
        lastRippleTime: number;
        analyser: AnalyserNode | null;
        dataArray: Uint8Array | null;
        audioContext: AudioContext | null;
        smoothedAudio: number;
        smoothedBass: number;
        smoothedMid: number;
        smoothedHigh: number;
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
        renderer.toneMappingExposure = 1.0;
        containerRef.current.appendChild(renderer.domElement);
        camera.position.z = 16;

        // ── Constants ─────────────────────────────────────────────────
        const RADIUS = 4;
        const VIOLET = 0x8b5cf6;

        // ── 1. Main wireframe sphere (lower poly for performance) ─────
        const sphereGeo = new THREE.IcosahedronGeometry(RADIUS, 20);
        const sphereMat = new THREE.MeshBasicMaterial({
            color: VIOLET,
            wireframe: true,
            transparent: true,
            opacity: 0.85,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
        });
        const sphere = new THREE.Mesh(sphereGeo, sphereMat);
        scene.add(sphere);

        // ── 2. Solid inner fill (opaque violet energy) ────────────────
        const innerFillGeo = new THREE.IcosahedronGeometry(RADIUS * 0.92, 3);
        const innerFillMat = new THREE.MeshBasicMaterial({
            color: 0x6d28d9,
            transparent: true,
            opacity: 0.55,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
        });
        const innerFill = new THREE.Mesh(innerFillGeo, innerFillMat);
        scene.add(innerFill);

        const innerCoreGeo = new THREE.IcosahedronGeometry(RADIUS * 0.6, 2);
        const innerCoreMat = new THREE.MeshBasicMaterial({
            color: 0x7c3aed,
            transparent: true,
            opacity: 0.7,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
        });
        const innerCore = new THREE.Mesh(innerCoreGeo, innerCoreMat);
        scene.add(innerCore);

        // ── 3. Flare layers (distorted wireframe shells — NOT perfect
        //    spheres). Each gets its own noise displacement so they
        //    look like energy flares emanating from the surface. ────────
        const flareLayers: FlareLayer[] = [];
        const flareCount = 3;
        for (let i = 0; i < flareCount; i++) {
            const depth = (i + 1) / flareCount;
            const r = RADIUS * (1.1 + depth * 0.5);
            const detail = Math.max(12 - i * 3, 5);
            const geo = new THREE.IcosahedronGeometry(r, detail);
            const opacity = 0.35 * Math.pow(1 - depth, 1.4);
            const mat = new THREE.MeshBasicMaterial({
                color: VIOLET,
                wireframe: true,
                transparent: true,
                opacity,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
            });
            const mesh = new THREE.Mesh(geo, mat);
            scene.add(mesh);
            flareLayers.push({
                mesh,
                origPositions: geo.attributes.position.clone(),
                baseRadius: r,
                noiseOffset: i * 7.3, // unique phase
            });
        }

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
                color: 0xc4b5fd,
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
            scene, camera, renderer, sphere, innerFill, innerCore,
            flareLayers, ripples: ripplePool, lastRippleTime: -5,
            analyser: null, dataArray: null, audioContext: null,
            smoothedAudio: 0, smoothedBass: 0, smoothedMid: 0, smoothedHigh: 0,
        };

        // ── Animation ─────────────────────────────────────────────────
        let animId: number;
        const clock = new THREE.Clock();
        const origPos = sphereGeo.attributes.position.clone();
        const RIPPLE_INTERVAL = 5.0;
        const RIPPLE_DURATION = 3.5;
        const RIPPLE_MAX_SCALE = 3.5;

        // Helper: displace any icosahedron shell with noise + audio
        const displaceShell = (
            positions: THREE.BufferAttribute,
            orig: THREE.BufferAttribute,
            baseR: number,
            t: number,
            noiseOff: number,
            idleAmp: number,
            audioAmp: number,
            audio: number,
            bass: number,
            mid: number,
            high: number,
            dataArr: Uint8Array | null,
            active: boolean,
        ) => {
            const count = positions.count;
            for (let i = 0; i < count; i++) {
                const ox = orig.getX(i), oy = orig.getY(i), oz = orig.getZ(i);
                const len = Math.sqrt(ox * ox + oy * oy + oz * oz);
                const nx = ox / len, ny = oy / len, nz = oz / len;

                // Organic idle noise — very subtle when silent
                const n = fbm(
                    nx * 2.0 + t * 0.12 + noiseOff,
                    ny * 2.0 + t * 0.08 + noiseOff,
                    nz * 2.0,
                    2
                );
                let disp = n * idleAmp;

                // Audio-driven sharp mountain spikes
                if (active && dataArr) {
                    const bin = i % (dataArr.length - 1);
                    const freq = dataArr[bin] / 255;

                    // Sharp spikes from frequency data (mountains!)
                    const spike = Math.pow(freq, 1.5) * audio * audioAmp * 1.4;
                    // Bass creates broad terrain bumps
                    const bassBump = Math.pow(Math.max(0, Math.sin(t * 1.8 + ny * 6 + nx * 4)), 2.0) * bass * audioAmp * 0.5;
                    // Mid ridges — higher frequency noise
                    const midRidge = fbm(
                        nx * 5 + t * 0.7 + noiseOff,
                        ny * 5 + t * 0.5,
                        nz * 5, 2
                    ) * mid * audioAmp * 0.6;
                    // High-freq micro spikes
                    const hiSpk = noise3D(
                        nx * 8 + t * 1.2,
                        ny * 8 + t * 0.9,
                        nz * 8 + noiseOff
                    ) * high * audioAmp * 0.3;
                    // Only additive — spikes outward, never inward
                    disp += Math.max(0, spike + bassBump) + midRidge + hiSpk;
                }

                const r = baseR + disp;
                positions.setXYZ(i, nx * r, ny * r, nz * r);
            }
            positions.needsUpdate = true;
        };

        const animate = () => {
            animId = requestAnimationFrame(animate);
            const t = clock.getElapsedTime();
            const ctx = sceneRef.current;
            if (!ctx) return;

            const { analyser, dataArray, sphere, innerFill, innerCore, flareLayers, ripples } = ctx;

            // ── Audio analysis ────────────────────────────────────────
            let rawAudio = 0, rawBass = 0, rawMid = 0, rawHigh = 0;
            if (analyser && dataArray && isActiveRef.current) {
                analyser.getByteFrequencyData(dataArray as Uint8Array<ArrayBuffer>);
                const len = dataArray.length;
                let sum = 0;
                for (let i = 0; i < len; i++) sum += dataArray[i];
                rawAudio = Math.min((sum / len / 255) * 3.5, 1.0);
                const bassEnd = Math.floor(len * 0.12);
                let bs = 0; for (let i = 0; i < bassEnd; i++) bs += dataArray[i];
                rawBass = Math.min((bs / bassEnd / 255) * 2.5, 1.0);
                const midStart = Math.floor(len * 0.12), midEnd = Math.floor(len * 0.55);
                let ms = 0; for (let i = midStart; i < midEnd; i++) ms += dataArray[i];
                rawMid = Math.min((ms / (midEnd - midStart) / 255) * 3.0, 1.0);
                const hiStart = Math.floor(len * 0.55), hiEnd = Math.floor(len * 0.85);
                let hs = 0; for (let i = hiStart; i < hiEnd; i++) hs += dataArray[i];
                rawHigh = Math.min((hs / (hiEnd - hiStart) / 255) * 2.8, 1.0);
            }

            const sf = 0.14;
            ctx.smoothedAudio += (rawAudio - ctx.smoothedAudio) * sf;
            ctx.smoothedBass += (rawBass - ctx.smoothedBass) * sf;
            ctx.smoothedMid += (rawMid - ctx.smoothedMid) * sf;
            ctx.smoothedHigh += (rawHigh - ctx.smoothedHigh) * sf;
            const audio = ctx.smoothedAudio;
            const bass = ctx.smoothedBass;
            const mid = ctx.smoothedMid;
            const high = ctx.smoothedHigh;
            const active = isActiveRef.current;

            // ── Rotation (near-still when silent) ───────────────────────
            const rSpeed = 0.0004 + audio * 0.006;
            sphere.rotation.y += rSpeed;
            sphere.rotation.x += rSpeed * 0.15;

            // ── Inner fill energy ──────────────────────────────────────
            const breath = Math.sin(t * 0.7) * 0.02 + 1;
            innerCore.scale.setScalar(breath);
            innerFill.scale.setScalar(breath * 0.99);
            (innerFillMat as THREE.MeshBasicMaterial).opacity =
                THREE.MathUtils.lerp(0.5, 0.75, audio);
            (innerCoreMat as THREE.MeshBasicMaterial).opacity =
                THREE.MathUtils.lerp(0.6, 0.85, audio);

            // ── Main sphere displacement (MOUNTAINS) ──────────────────
            displaceShell(
                sphere.geometry.attributes.position as THREE.BufferAttribute,
                origPos, RADIUS, t, 0,
                0.15,    // idle amplitude — near-still when silent
                4.5,     // audio amplitude — sharp mountain spikes
                audio, bass, mid, high,
                dataArray, active,
            );
            sphere.geometry.computeVertexNormals();

            // ── Flare layer displacement (organic energy wisps) ───────
            //    Each flare shell gets its own noise displacement so
            //    it deforms independently — NOT a perfect sphere.
            //    Amplitude increases with distance → outer shells are
            //    more wild and distorted like solar plasma tendrils.
            for (let i = 0; i < flareLayers.length; i++) {
                const fl = flareLayers[i];
                const depth = (i + 1) / flareLayers.length;
                const flareIdleAmp = 0.2 + depth * 0.5;    // minimal idle
                const flareAudioAmp = 3.0 + depth * 3.5;   // outer = wilder with audio

                displaceShell(
                    fl.mesh.geometry.attributes.position as THREE.BufferAttribute,
                    fl.origPositions, fl.baseRadius, t, fl.noiseOffset,
                    flareIdleAmp, flareAudioAmp,
                    audio, bass, mid, high,
                    dataArray, active,
                );

                // Slow counter-rotation for depth
                fl.mesh.rotation.y += 0.0004 * (i % 2 === 0 ? 1 : -1);
                fl.mesh.rotation.z += 0.0002 * (i % 2 === 0 ? -1 : 1);

                // Opacity responds to audio
                const baseOp = 0.35 * Math.pow(1 - depth, 1.4);
                (fl.mesh.material as THREE.MeshBasicMaterial).opacity =
                    THREE.MathUtils.lerp(baseOp, baseOp + 0.12, audio);
            }

            // ── Shell scale (minimal stretch) ──────────────────────────
            const shellTarget = 1 + bass * 0.04;
            sphere.scale.setScalar(THREE.MathUtils.lerp(sphere.scale.x, shellTarget, 0.06));

            // ── Color (single violet) ─────────────────────────────────
            const sMat = sphere.material as THREE.MeshBasicMaterial;
            const baseCol = new THREE.Color(VIOLET);
            const hotCol = new THREE.Color(0xc4b5fd);
            sMat.color.copy(baseCol).lerp(hotCol, Math.min(audio * 1.5, 1));
            sMat.opacity = THREE.MathUtils.lerp(0.7, 0.92, audio);

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

            renderer.render(scene, camera);
        };

        animate();

        const handleResize = () => {
            if (!sceneRef.current) return;
            const { camera: cam, renderer: rnd } = sceneRef.current;
            cam.aspect = window.innerWidth / window.innerHeight;
            cam.updateProjectionMatrix();
            rnd.setSize(window.innerWidth, window.innerHeight);
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
                sceneRef.current.renderer.dispose();
                sceneRef.current.scene.clear();
                if (sceneRef.current.audioContext) {
                    sceneRef.current.audioContext.close();
                }
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
        }

        return () => { source.disconnect(); audioContext.close(); };
    }, [audioStream]);

    return <div ref={containerRef} className="w-full h-full" />;
}
