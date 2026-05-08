import * as THREE from "three";
import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.158/examples/jsm/controls/OrbitControls.js";

(() => {

    const POLL_MS = 1200;
    const MACHINE_ID = machine_id;
    const BASE_URL = "";

    const hud = document.getElementById("hud");
    const alertBar = document.getElementById("alertBar");

    /* ---------------- SCENE ---------------- */

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf3f6fb);
    scene.fog = new THREE.Fog(0xf3f6fb, 10, 80);

    /* ---------------- CAMERA ---------------- */

    const camera = new THREE.PerspectiveCamera(
        60,
        window.innerWidth / window.innerHeight,
        0.1,
        200
    );

    camera.position.set(7, 4, 7);
    camera.lookAt(0, 0, 0);

    /* ---------------- RENDERER ---------------- */

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = true;

    document.body.appendChild(renderer.domElement);

    /* ---------------- CONTROLS ---------------- */

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    /* ---------------- LIGHTS ---------------- */

    const hemi = new THREE.HemisphereLight(0xffffff, 0xc9d4e8, 1.1);
    scene.add(hemi);

    const dir = new THREE.DirectionalLight(0xffffff, 1);
    dir.position.set(8, 12, 6);
    dir.castShadow = true;
    scene.add(dir);

    const fill = new THREE.DirectionalLight(0xffffff, 0.5);
    fill.position.set(-5, 5, -5);
    scene.add(fill);

    /* ---------------- FLOOR ---------------- */

    const floor = new THREE.Mesh(
        new THREE.PlaneGeometry(60, 60),
        new THREE.MeshStandardMaterial({ color: 0xffffff })
    );

    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -2.2;
    floor.receiveShadow = true;
    scene.add(floor);

    const grid = new THREE.GridHelper(40, 40, 0xd8e0ee, 0xeff3fb);
    grid.position.y = -2.19;
    scene.add(grid);

    /* ---------------- MOTOR GROUP ---------------- */

    const motorGroup = new THREE.Group();
    scene.add(motorGroup);

    motorGroup.position.set(0, -0.6, 0);
    motorGroup.rotation.z = Math.PI / 2;
    motorGroup.rotation.y = Math.PI / 6;

    /* ---------------- MOTOR MATERIAL ---------------- */

    const motorMat = new THREE.MeshStandardMaterial({
        color: 0x6f7f92,
        roughness: 0.5,
        metalness: 0.4
    });

    const motorBody = new THREE.Group();

    /* ----- Main cylindrical body ----- */

    const motorCore = new THREE.Mesh(
        new THREE.CylinderGeometry(1.2, 1.2, 2, 64),
        motorMat
    );

    motorCore.castShadow = true;
    motorBody.add(motorCore);


    /* ----- Front hemispherical cap ----- */

    const frontCap = new THREE.Mesh(
        new THREE.SphereGeometry(1.2, 64, 64, 0, Math.PI * 2, 0, Math.PI / 2),
        motorMat
    );

    frontCap.position.y = -0.8;
    frontCap.rotation.x = Math.PI;

    motorBody.add(frontCap);


    /* ----- Rear hemispherical cap ----- */

    const rearCap = new THREE.Mesh(
        new THREE.SphereGeometry(1.2, 64, 64, 0, Math.PI * 2, 0, Math.PI / 2),
        motorMat
    );

    rearCap.position.y = 0.8;

    motorBody.add(rearCap);


    /* ----- Add motor body to group ----- */

    motorGroup.add(motorBody);

    /* ---------------- COOLING FINS ---------------- */

    for (let i = -1.24; i <= 1.24; i += 0.18) {

        const fin = new THREE.Mesh(
            new THREE.BoxGeometry(0.08, 2, Math.sqrt(2.8 * 2.8 - i * i * 4)),
            new THREE.MeshStandardMaterial({
                color: 0x7a8798,
                roughness: 0.7,
                metalness: 0.2
            })
        );

        fin.position.x = i;
        motorGroup.add(fin);

    }

    /* ---------------- SHAFT ---------------- */

    const shaft = new THREE.Mesh(
        new THREE.CylinderGeometry(0.18, 0.18, 6.6, 32, 32, false, Math.PI / 2, 1.9 * Math.PI),
        new THREE.MeshStandardMaterial({
            color: 0xbfc7d1,
            metalness: 0.9,
            roughness: 0.2
        })
    );

    // align shaft with motor axis
    shaft.rotation.z = Math.PI;

    // position outside motor
    shaft.position.x = 0.1;
    shaft.position.y = 1;

    motorGroup.add(shaft);

    /* ---------------- VIBRATION RING ---------------- */

    const vibrationRing = new THREE.Mesh(
        new THREE.RingGeometry(1.8, 2.2, 64),
        new THREE.MeshBasicMaterial({
            color: 0xffaa00,
            transparent: true,
            opacity: 0.25,
            side: THREE.DoubleSide
        })
    );

    vibrationRing.rotation.x = -Math.PI / 2;
    vibrationRing.position.y = -2;

    scene.add(vibrationRing);

    /* ---------------- STATUS LIGHT ---------------- */

    const statusLight = new THREE.Mesh(
        new THREE.SphereGeometry(0.15, 32, 32),
        new THREE.MeshStandardMaterial({
            emissive: 0x00ff00,
            emissiveIntensity: 1
        })
    );

    statusLight.position.set(0, 1.6, 0);
    scene.add(statusLight);

    /* ---------------- STATE ---------------- */

    let vibrationStrength = 0;
    let currentIntensity = 0;

    /* ---------------- HELPERS ---------------- */

    function clamp01(x) {
        return Math.max(0, Math.min(1, x));
    }

    function formatNum(v, d) {
        if (v === undefined || v === null) return "NA";
        return Number(v).toFixed(d);
    }

    function healthToStatus(data) {

        const issues = Array.isArray(data.issues) ? data.issues : [];
        const operatingState = String(data.operating_state || "").toUpperCase();
        const health = String(data.health || "").toUpperCase();

        if (data.stopping_required === true) return "ANOMALY";
        if (issues.includes("ML_CRITICAL")) return "ANOMALY";
        if (issues.includes("OVERHEAT") || issues.includes("CURRENT_SPIKE")) return "ANOMALY";
        if (operatingState === "OFF" || health === "OFF") return "OFF";
        if (operatingState === "STARTING" || health === "STARTING" || health === "WARMUP") return "STARTING";

        return "HEALTHY";
    }

    /* ---------------- UPDATE TWIN ---------------- */

    function updateTwinFromBackend(data) {

        const temp = Number(data.temperature ?? data.temp ?? 0);
        const vib = Number(data.vibration ?? data.vib ?? 0);
        const curr = Number(data.current ?? data.curr ?? 0);

        vibrationStrength = vib * 0.4 * (data.switch_state == "ON" ? 1 : 0);
        currentIntensity = clamp01(curr / 6) * (data.switch_state == "ON" ? 1 : 0);

        const heat = clamp01((temp - 30) / 30);

        motorMat.color.setRGB(
            0.38 + heat * 0.6,
            0.54 - heat * 0.2,
            0.72 - heat * 0.6
        );

        const status = healthToStatus(data);

        if (status === "ANOMALY") {
            statusLight.material.emissive.set(0xff0000);
        } else if (status === "OFF") {
            statusLight.material.emissive.set(0x666666);
        } else if (status === "STARTING") {
            statusLight.material.emissive.set(0xffaa00);
        } else {
            statusLight.material.emissive.set(0x00ff00);
        }

        /* -------- ALERT BAR -------- */
        if (data.stopping_required) {

            alertBar.style.display = "block";
            alertBar.textContent = "⚠ MACHINE STOPPING REQUIRED, MACHINE WILL BE AUTOMATICALLY STOPPED";

        } else {

            alertBar.style.display = "none";

        }

    }

    /* ---------------- FETCH MACHINE ---------------- */

    async function fetchMachine(machineId) {

        const res = await fetch(`${BASE_URL}/machine/${encodeURIComponent(machineId)}`, { cache: "no-store" });
        const data = await res.json();

        updateTwinFromBackend(data);

        if (hud) {

            hud.textContent =
                `machine=${machineId}
temp=${formatNum(data.temperature, 2)}
vib=${formatNum(data.vibration, 3)}
current=${formatNum(data.current, 2)}
switch_state=${data.switch_state}
issues=${(data.issues || []).join(",")}`;

        }

    }

    /* ---------------- POLLING ---------------- */

    async function pollLoop() {

        try {
            await fetchMachine(MACHINE_ID);
        } catch (e) {
            console.error(e);
        }

        setTimeout(pollLoop, POLL_MS);

    }

    pollLoop();

    /* ---------------- ANIMATE ---------------- */

    function animate() {

        requestAnimationFrame(animate);

        controls.update();

        /* shaft rotation */

        shaft.rotation.y += 0.25 * currentIntensity;

        /* vibration */

        const vibPulse = Math.abs(Math.sin(Date.now() * 0.02)) * vibrationStrength;

        vibrationRing.scale.set(1 + vibPulse * 4, 1 + vibPulse * 4, 1);

        const shakeX = Math.sin(Date.now() * 0.012) * vibrationStrength;
        const shakeZ = Math.cos(Date.now() * 0.014) * vibrationStrength;

        motorGroup.position.x = shakeX;
        motorGroup.position.z = shakeZ;

        renderer.render(scene, camera);

    }

    animate();

    /* ---------------- RESIZE ---------------- */

    window.addEventListener("resize", () => {

        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);

    });

})();
