import { useEffect, useMemo, useRef, useState } from "react";

import { logout as logoutAuth, restoreSession, signIn, signUp } from "./authClient";

const P = {
  eye: ["M2 12s4-8 10-8 10 8 10 8-4 8-10 8S2 12 2 12z", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"],
  edit: ["M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7", "M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"],
  files: ["M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z", "M13 2v7h7"],
  brief: ["M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z", "M14 2v6h6", "M16 13H8", "M16 17H8", "M10 9H8"],
  search: ["M21 21l-4.35-4.35", "M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15z"],
  up: ["M12 19V5", "M5 12l7-7 7 7"],
  upload: ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "M17 8l-5-5-5 5", "M12 3v12"],
  more: ["M12 12h.01", "M7 12h.01", "M17 12h.01"],
  link: ["M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71", "M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"],
  export: ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "M7 10l5 5 5-5", "M12 15V3"],
  logout: ["M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4", "M16 17l5-5-5-5", "M21 12H9"],
  collapse: "M15 18l-6-6 6-6",
  plug: ["M12 2v6m4-2h6m0 0v2a2 2 0 0 1-2 2h-2m-8 0H4a2 2 0 0 1-2-2V8m0-4h6M6 18v3m6 0v3m6-3v3M6 18h12", "M9 22h6"],
  clock: ["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "M12 6v6l4 2"],
};

const PROMPT_GUIDE_ITEMS = [
  {
    title: "Бриф мероприятия",
    text: "Опиши формат, дату, город, гостей и бюджет. ARGUS соберёт структуру брифа.",
  },
  {
    title: "Поиск в каталоге",
    text: "Спроси про позиции, стиль, количество или ограничения, чтобы найти подходящие строки.",
  },
  {
    title: "Уточнение ответа",
    text: "Попроси сократить, разложить по шагам или добавить риски и следующие действия.",
  },
];

function Icon({ d, size = 16, strokeWidth = 1.8 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      {Array.isArray(d) ? d.map((path, index) => <path key={index} d={path} />) : <path d={d} />}
    </svg>
  );
}

function AnimatedBg() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas?.getContext("webgl", { antialias: false, alpha: true });
    if (!canvas || !gl) return undefined;

    const vertexSource = `
      attribute vec2 a_position;
      void main() {
        gl_Position = vec4(a_position, 0.0, 1.0);
      }
    `;
    const fragmentSource = `
      precision highp float;
      uniform vec2 u_resolution;
      uniform vec2 u_pointer;
      uniform float u_time;
      uniform float u_click;

      float hash(vec2 p) {
        return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
      }

      float noise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        vec2 u = f * f * (3.0 - 2.0 * f);
        return mix(
          mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
          mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
          u.y
        );
      }

      float fbm(vec2 p) {
        float value = 0.0;
        float amp = 0.5;
        for (int i = 0; i < 5; i++) {
          value += amp * noise(p);
          p = mat2(1.62, -1.18, 1.18, 1.62) * p + 0.21;
          amp *= 0.52;
        }
        return value;
      }

      void main() {
        vec2 uv = gl_FragCoord.xy / u_resolution.xy;
        vec2 p = (gl_FragCoord.xy * 2.0 - u_resolution.xy) / min(u_resolution.x, u_resolution.y);
        vec2 pointer = (u_pointer * 2.0 - 1.0) * vec2(u_resolution.x / min(u_resolution.x, u_resolution.y), 1.0);
        pointer.y *= -1.0;

        float t = u_time * 0.18;
        float d = distance(p, pointer);
        float pull = exp(-d * 3.2) * 0.55;
        vec2 flow = vec2(
          fbm(p * 1.25 + vec2(t, -t) + pull),
          fbm(p * 1.35 + vec2(-t * 1.1, t * 0.8) - pull)
        );
        vec2 warped = p + (flow - 0.5) * 0.36 + normalize(p - pointer + 0.001) * pull * 0.06;

        float waves = sin(warped.x * 3.2 + fbm(warped * 1.45 + t) * 3.4 + t * 4.0);
        waves += sin((warped.x + warped.y) * 4.1 - t * 2.8) * 0.25;
        float metal = smoothstep(-0.92, 1.08, waves);
        float edge = pow(abs(waves), 10.0) * 0.22;

        float pulse = exp(-u_click * 1.7) * (1.0 - smoothstep(2.0, 3.1, u_click));
        float ripple = sin(d * 42.0 - u_click * 7.0) * exp(-d * 5.2) * pulse;
        metal += ripple * 0.08;

        vec3 deep = vec3(0.018, 0.036, 0.058);
        vec3 steel = vec3(0.20, 0.29, 0.38);
        vec3 chrome = vec3(0.50, 0.60, 0.68);
        vec3 violet = vec3(0.18, 0.16, 0.28);
        vec3 color = mix(deep, steel, metal);
        color = mix(color, chrome, edge + pull * 0.06);
        color += violet * (0.10 + 0.04 * sin(uv.y * 5.0 + t * 1.3));
        color += vec3(0.20, 0.34, 0.42) * ripple * 0.10;
        color *= 0.72 + 0.12 * smoothstep(0.0, 1.25, length(p));

        float vignette = smoothstep(1.7, 0.25, length(p * vec2(0.82, 1.0)));
        gl_FragColor = vec4(color * vignette, 0.78);
      }
    `;

    const makeShader = (type, source) => {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        gl.deleteShader(shader);
        return null;
      }
      return shader;
    };

    const vertexShader = makeShader(gl.VERTEX_SHADER, vertexSource);
    const fragmentShader = makeShader(gl.FRAGMENT_SHADER, fragmentSource);
    const program = gl.createProgram();
    if (!vertexShader || !fragmentShader || !program) return undefined;
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return undefined;

    const position = gl.getAttribLocation(program, "a_position");
    const resolution = gl.getUniformLocation(program, "u_resolution");
    const pointer = gl.getUniformLocation(program, "u_pointer");
    const time = gl.getUniformLocation(program, "u_time");
    const click = gl.getUniformLocation(program, "u_click");
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

    const pointerState = { x: 0.5, y: 0.5, clickAt: -10 };
    let frameId = 0;
    let start = performance.now();

    const resize = () => {
      const scale = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, Math.floor(canvas.clientWidth * scale));
      const height = Math.max(1, Math.floor(canvas.clientHeight * scale));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      gl.viewport(0, 0, width, height);
    };

    const movePointer = (event) => {
      pointerState.x = event.clientX / window.innerWidth;
      pointerState.y = event.clientY / window.innerHeight;
    };

    const triggerRipple = (event) => {
      movePointer(event);
      pointerState.clickAt = (performance.now() - start) / 1000;
    };

    const render = (now) => {
      const elapsed = (now - start) / 1000;
      resize();
      gl.useProgram(program);
      gl.enableVertexAttribArray(position);
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      gl.uniform2f(resolution, canvas.width, canvas.height);
      gl.uniform2f(pointer, pointerState.x, pointerState.y);
      gl.uniform1f(time, elapsed);
      gl.uniform1f(click, Math.max(0, elapsed - pointerState.clickAt));
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      frameId = window.requestAnimationFrame(render);
    };

    window.addEventListener("pointermove", movePointer);
    window.addEventListener("pointerdown", triggerRipple);
    frameId = window.requestAnimationFrame((now) => {
      start = now;
      render(now);
    });

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("pointermove", movePointer);
      window.removeEventListener("pointerdown", triggerRipple);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      gl.deleteShader(vertexShader);
      gl.deleteShader(fragmentShader);
    };
  }, []);

  return (
    <div className="bg-layer" aria-hidden="true">
      <canvas ref={canvasRef} className="liquid-chrome" />
      <div className="chrome-sheen" />
    </div>
  );
}

function ArgusOrb({ loading = false }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const startRef = useRef(null);
  const loadingRef = useRef(loading);
  loadingRef.current = loading;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const cx = width / 2;
    const cy = height / 2;
    const blobRadius = width * 0.2;
    const particleRadius = width * 0.4;
    const controlPoints = 12;
    const particles = [];

    for (let index = 0; index < 300; index += 1) {
      const u = Math.random();
      let radius;
      if (u < 0.18) radius = Math.pow(Math.random(), 0.6) * 0.38;
      else if (u < 0.55) radius = 0.38 + Math.random() * 0.48;
      else if (u < 0.8) radius = 0.86 + Math.random() * 0.5;
      else radius = 1.36 + Math.random() * 0.7;

      const phi = Math.random() * Math.PI * 2;
      const theta = Math.acos(Math.random() * 2 - 1);
      particles.push({
        bx: radius * Math.sin(theta) * Math.cos(phi),
        by: radius * Math.sin(theta) * Math.sin(phi),
        bz: radius * Math.cos(theta),
        radius,
        phase: Math.random() * Math.PI * 2,
        speed: 0.14 + Math.random() * 0.38,
        size: radius < 0.38 ? 0.55 + Math.random() * 0.9 : radius < 0.86 ? 0.85 + Math.random() * 1.3 : 1.1 + Math.random() * 1.9,
      });
    }

    const blobPoints = (time, active) => {
      const speed = active ? 2.1 : 1;
      const amplitude = active ? 1.5 : 1;
      const points = [];
      for (let index = 0; index < controlPoints; index += 1) {
        const angle = (index / controlPoints) * Math.PI * 2 - Math.PI / 2;
        const radius = blobRadius * (
          1 +
          amplitude * 0.1 * Math.sin(2 * angle + time * 0.55 * speed) +
          amplitude * 0.08 * Math.sin(3 * angle - time * 0.82 * speed) +
          amplitude * 0.06 * Math.cos(4 * angle + time * 0.47 * speed) +
          amplitude * 0.04 * Math.sin(5 * angle - time * 1.1 * speed) +
          (active ? amplitude * 0.04 * Math.cos(7 * angle + time * 1.85) : 0)
        );
        points.push({ x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) });
      }
      return points;
    };

    const drawBlobPath = (points) => {
      ctx.beginPath();
      points.forEach((point, index) => {
        const prev = points[(index - 1 + points.length) % points.length];
        const next = points[(index + 1) % points.length];
        const next2 = points[(index + 2) % points.length];
        const cp1x = point.x + (next.x - prev.x) / 6;
        const cp1y = point.y + (next.y - prev.y) / 6;
        const cp2x = next.x - (next2.x - point.x) / 6;
        const cp2y = next.y - (next2.y - point.y) / 6;
        if (index === 0) ctx.moveTo(point.x, point.y);
        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, next.x, next.y);
      });
      ctx.closePath();
    };

    const particleColor = (radius, depth) => {
      let rgb;
      let base;
      if (radius < 0.32) {
        rgb = "238,236,252";
        base = 0.95;
      } else if (radius < 0.68) {
        rgb = "200,198,228";
        base = 0.78;
      } else if (radius < 1.05) {
        rgb = "158,156,195";
        base = 0.6;
      } else if (radius < 1.4) {
        rgb = "120,118,162";
        base = 0.42;
      } else {
        rgb = "88,86,130";
        base = 0.26;
      }
      return `rgba(${rgb},${Math.min(1, base * (0.32 + 0.68 * depth)).toFixed(3)})`;
    };

    const drawParticle = (x, y, size, radius, depth) => {
      const glow = ctx.createRadialGradient(x, y, 0, x, y, size * 3.2);
      glow.addColorStop(0, particleColor(radius, depth * 0.4));
      glow.addColorStop(1, "rgba(120,118,162,0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(x, y, size * 3.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = particleColor(radius, depth);
      ctx.beginPath();
      ctx.arc(x, y, Math.max(0.3, size), 0, Math.PI * 2);
      ctx.fill();
    };

    const draw = (timestamp) => {
      if (!startRef.current) startRef.current = timestamp;
      const time = (timestamp - startRef.current) * 0.001;
      const active = loadingRef.current;
      ctx.clearRect(0, 0, width, height);

      const floatY = Math.sin(time * 0.75) * 7;
      const rotationSpeed = active ? 0.44 : 0.13;
      const cos = Math.cos(time * rotationSpeed);
      const sin = Math.sin(time * rotationSpeed);
      const transformed = particles.map((particle) => {
        const wobble = Math.sin(time * particle.speed + particle.phase) * (active ? 0.055 : 0.022);
        const rx = particle.bx * (1 + wobble) * cos + particle.bz * sin;
        const ry = particle.by * (1 + wobble);
        const rz = -(particle.bx * (1 + wobble)) * sin + particle.bz * cos;
        const scale = 3.8 / (3.8 + rz * 0.55);
        return {
          x: cx + rx * particleRadius * scale,
          y: cy + ry * particleRadius * scale + floatY,
          rz,
          radius: particle.radius,
          size: particle.size * scale,
          depth: (rz + 2.3) / 4.6,
        };
      }).sort((a, b) => a.rz - b.rz);

      transformed.filter((particle) => particle.rz < -0.05).forEach((particle) => {
        drawParticle(particle.x, particle.y, particle.size, particle.radius, particle.depth);
      });

      const nebula = ctx.createRadialGradient(cx, cy + floatY, 0, cx, cy + floatY, blobRadius * 3);
      nebula.addColorStop(0, "rgba(188,186,225,0.26)");
      nebula.addColorStop(0.4, "rgba(158,156,200,0.10)");
      nebula.addColorStop(0.75, "rgba(128,126,172,0.04)");
      nebula.addColorStop(1, "rgba(128,126,172,0)");
      ctx.fillStyle = nebula;
      ctx.beginPath();
      ctx.arc(cx, cy + floatY, blobRadius * 3, 0, Math.PI * 2);
      ctx.fill();

      ctx.save();
      ctx.translate(0, floatY);
      const points = blobPoints(time, active);
      drawBlobPath(points);
      const base = ctx.createRadialGradient(cx - blobRadius * 0.22, cy - blobRadius * 0.25, 0, cx, cy, blobRadius * 1.1);
      base.addColorStop(0, "#f2f0ff");
      base.addColorStop(0.18, "#c8c6e0");
      base.addColorStop(0.52, "#9896b8");
      base.addColorStop(0.8, "#7a78a0");
      base.addColorStop(1, "#565478");
      ctx.fillStyle = base;
      ctx.fill();

      drawBlobPath(points);
      const shade = ctx.createRadialGradient(cx + blobRadius * 0.28, cy + blobRadius * 0.34, 0, cx, cy, blobRadius * 0.92);
      shade.addColorStop(0, "rgba(12,10,30,0.60)");
      shade.addColorStop(1, "rgba(12,10,30,0)");
      ctx.fillStyle = shade;
      ctx.fill();

      drawBlobPath(points);
      const shine = ctx.createRadialGradient(cx - blobRadius * 0.26 + Math.sin(time * 0.55) * 2.8, cy - blobRadius * 0.33 + Math.cos(time * 0.42) * 2.2, 0, cx - blobRadius * 0.26, cy - blobRadius * 0.33, blobRadius * 0.66);
      shine.addColorStop(0, "rgba(255,255,255,0.92)");
      shine.addColorStop(0.28, "rgba(255,255,255,0.30)");
      shine.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = shine;
      ctx.fill();

      drawBlobPath(points);
      const glint = ctx.createRadialGradient(cx + blobRadius * 0.32, cy - blobRadius * 0.38, 0, cx + blobRadius * 0.32, cy - blobRadius * 0.38, blobRadius * 0.12);
      glint.addColorStop(0, "rgba(255,255,255,0.46)");
      glint.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = glint;
      ctx.fill();
      ctx.restore();

      transformed.filter((particle) => particle.rz >= -0.05).forEach((particle) => {
        drawParticle(particle.x, particle.y, particle.size, particle.radius, particle.depth);
      });

      if (active) {
        const progress = (timestamp % 1900) / 1900;
        [0, 0.33, 0.66].forEach((offset) => {
          const value = (progress + offset) % 1;
          const radius = blobRadius * (1.18 + value * 1.25);
          const alpha = Math.max(0, 0.5 * (1 - value * 1.44));
          ctx.beginPath();
          ctx.arc(cx, cy + floatY, radius, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(185,183,220,${alpha.toFixed(3)})`;
          ctx.lineWidth = 1.4;
          ctx.stroke();
        });
      }

      rafRef.current = window.requestAnimationFrame(draw);
    };

    rafRef.current = window.requestAnimationFrame(draw);
    return () => {
      if (rafRef.current) window.cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <div className="orb-wrap" aria-hidden="true">
      <canvas ref={canvasRef} className="orb-canvas" width={260} height={260} />
      {loading && <div className="orb-dots"><span /><span /><span /></div>}
    </div>
  );
}

function Sidebar({ status, userEmail, view, onViewChange, onReset, onLogout }) {
  const initials = (userEmail || "ARGUS")
    .split("@")[0]
    .slice(0, 2)
    .toUpperCase();

  const startNewSession = () => {
    onViewChange("chat");
    onReset();
  };

  return (
    <aside className="sidebar">
      <div className="s-head">
        <div className="brand">
          <div className="brand-mark"><Icon d={P.eye} size={15} strokeWidth={2.2} /></div>
          <span className="brand-name">ARGUS</span>
        </div>
        <button className="icon-btn" type="button" aria-label="Свернуть">
          <Icon d={P.collapse} size={16} />
        </button>
      </div>

      <nav className="s-nav">
        <button className={`nav-link ${view === "chat" ? "active" : ""}`} onClick={startNewSession}>
          <span className="nav-icon"><Icon d={P.edit} size={15} /></span>
          <span className="nav-label">Новая сессия</span>
        </button>
        <button className="nav-link" type="button" disabled>
          <span className="nav-icon"><Icon d={P.search} size={15} /></span>
          <span className="nav-label">Поиск</span>
        </button>
        <button
          className={`nav-link ${view === "catalog" ? "active" : ""}`}
          type="button"
          disabled={!status.ready}
          onClick={() => onViewChange("catalog")}
        >
          <span className="nav-icon"><Icon d={P.plug} size={15} /></span>
          <span className="nav-label">Каталог</span>
          <span className={`status-dot ${status.ready ? "status-ok" : ""}`} />
        </button>
        <button className="nav-link" type="button" disabled>
          <span className="nav-icon"><Icon d={P.clock} size={15} /></span>
          <span className="nav-label">Документы</span>
        </button>
      </nav>

      <div className="s-divider" />

      <div className="s-scroll">
        <div className="s-pinned-label">СОСТОЯНИЕ</div>
        <div className="catalog-mini">
          <div className="catalog-mini-row">
            <span>Статус</span>
            <strong>{status.stage}</strong>
          </div>
          <div className="catalog-mini-row">
            <span>Строк</span>
            <strong>{status.row_count || 0}</strong>
          </div>
          <div className="catalog-mini-row">
            <span>Векторов</span>
            <strong>{status.embedded_count || 0}</strong>
          </div>
          <div className="catalog-mini-row">
            <span>Размерность</span>
            <strong>{status.vector_size || "—"}</strong>
          </div>
        </div>
      </div>

      <div className="s-user">
        <div className="u-avatar">{initials}</div>
        <div className="u-info">
          <div className="u-name">ARGUS MVP</div>
          <div className="u-email">{userEmail}</div>
        </div>
        <button className="logout-btn" type="button" onClick={onLogout} aria-label="Выйти">
          <Icon d={P.logout} size={15} />
        </button>
      </div>
    </aside>
  );
}

function Header({ status, view, onViewChange }) {
  const [guideOpen, setGuideOpen] = useState(false);

  return (
    <div className="m-hdr">
      {status.ready && (
        <div className="mobile-view-switch" aria-label="Переключить раздел">
          <button
            className={`mobile-view-btn ${view === "chat" ? "mobile-view-btn-active" : ""}`}
            type="button"
            onClick={() => onViewChange("chat")}
          >
            <Icon d={P.brief} size={14} />
            Чат
          </button>
          <button
            className={`mobile-view-btn ${view === "catalog" ? "mobile-view-btn-active" : ""}`}
            type="button"
            onClick={() => onViewChange("catalog")}
          >
            <Icon d={P.plug} size={14} />
            Каталог
          </button>
        </div>
      )}
      <div className="m-hdr-r">
        <button
          className={`h-ico-btn ${guideOpen ? "h-ico-btn-active" : ""}`}
          type="button"
          aria-label="Гайд по промптам"
          aria-expanded={guideOpen}
          onClick={() => setGuideOpen((open) => !open)}
        >
          <Icon d={P.brief} size={15} />
        </button>
        {guideOpen && (
          <div className="prompt-guide" role="dialog" aria-label="Гайд по промптам">
            <div className="prompt-guide-title">Гайд по промптам</div>
            {PROMPT_GUIDE_ITEMS.map((item) => (
              <div className="prompt-guide-item" key={item.title}>
                <strong>{item.title}</strong>
                <span>{item.text}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function UploadGate({ status, onUpload }) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);
  const busy = ["queued", "parsing", "embedding", "postgres", "uploading"].includes(status.stage);

  const progress = useMemo(() => {
    if (status.row_count && status.embedded_count) return Math.round((status.embedded_count / status.row_count) * 100);
    if (status.stage === "ready") return 100;
    if (status.stage === "parsing") return 10;
    if (status.stage === "postgres") return 85;
    if (status.stage === "uploading") return 94;
    return 0;
  }, [status]);

  const acceptFile = (file) => {
    if (file) onUpload(file);
  };

  return (
    <div className="upload-area">
      <ArgusOrb loading={busy} />
      <div
        className={`upload-panel ${drag ? "upload-panel-drag" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDrag(false);
          acceptFile(event.dataTransfer.files[0]);
        }}
      >
        <div className="upload-kicker">Каталог цен</div>
        <h1>Загрузить каталог</h1>
        <p>Выберите CSV с позициями прайса. MVP возьмёт готовые embeddings из файла и загрузит каталог в PostgreSQL/pgvector.</p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(event) => acceptFile(event.target.files?.[0])}
        />
        <button className="upload-btn" type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
          <Icon d={P.upload} size={17} />
          Выбрать CSV
        </button>

        <div className="progress-card">
          <div className="progress-meta">
            <span>{status.message || "Ожидание файла"}</span>
            <strong>{progress}%</strong>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          {status.error && <div className="error-text">{status.error}</div>}
        </div>
      </div>
    </div>
  );
}

function ChatMessage({ role, content }) {
  return (
    <div className={`msg ${role === "user" ? "msg-user" : "msg-asst"}`}>
      <div className="msg-role">{role === "user" ? "Вы" : "ARGUS"}</div>
      <div className="msg-bubble">{content}</div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="msg msg-asst">
      <div className="msg-role">ARGUS</div>
      <div className="typing"><span /><span /><span /></div>
    </div>
  );
}

function InputComposer({ mode, modeLocked, onModeChange, onSend, loading }) {
  const [value, setValue] = useState("");
  const taRef = useRef(null);
  const placeholder = mode === "search" ? "Найти позиции в каталоге..." : "Составить план мероприятия шаг за шагом...";

  const resize = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 180)}px`;
  };

  const submit = () => {
    const message = value.trim();
    if (!message || loading) return;
    setValue("");
    if (taRef.current) taRef.current.style.height = "auto";
    onSend(message);
  };

  return (
    <div className="composer-wrap">
      <div className="composer-box composer-row">
        <textarea
          ref={taRef}
          className="composer-ta"
          placeholder={placeholder}
          value={value}
          rows={1}
          disabled={loading}
          onChange={(event) => {
            setValue(event.target.value);
            resize();
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <div className="composer-send-wrap">
          <button className="send-btn" onClick={submit} disabled={!value.trim() || loading} aria-label="Отправить">
            <Icon d={P.up} size={15} />
          </button>
        </div>
      </div>

      <div className="mode-bar">
        <button
          className={`mode-tab ${mode === "brief" ? "mode-tab-active" : ""}`}
          type="button"
          disabled={modeLocked || loading}
          title={modeLocked ? "Чтобы сменить режим, начните новый чат" : undefined}
          onClick={() => onModeChange("brief")}
        >
          <span className="mode-tab-icon"><Icon d={P.brief} size={13} /></span>
          <span className="mode-tab-label">Планирование брифа</span>
        </button>
        <button
          className={`mode-tab ${mode === "search" ? "mode-tab-active" : ""}`}
          type="button"
          disabled={modeLocked || loading}
          title={modeLocked ? "Чтобы сменить режим, начните новый чат" : undefined}
          onClick={() => onModeChange("search")}
        >
          <span className="mode-tab-icon"><Icon d={P.search} size={13} /></span>
          <span className="mode-tab-label">Семантический поиск</span>
        </button>
      </div>
    </div>
  );
}

function ChatArea({ mode, messages, loading, onModeChange, onSend }) {
  const threadRef = useRef(null);
  const modeLocked = messages.some((message) => message.role === "user");

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages.length, loading]);

  return (
    <div className="chat-area">
      <div className="chat-thread" ref={threadRef}>
        {messages.length === 0 && (
          <div className="empty-chat">
            <ArgusOrb loading={false} />
            <div className="greeting-name">Привет!</div>
            <div className="greeting-q">{mode === "search" ? "Введите запрос для поиска по каталогу." : "Опишите мероприятие, и я соберу бриф."}</div>
          </div>
        )}
        {messages.map((message, index) => <ChatMessage key={`${message.role}-${index}`} role={message.role} content={message.content} />)}
        {loading && <TypingIndicator />}
      </div>
      <InputComposer mode={mode} modeLocked={modeLocked} onModeChange={onModeChange} onSend={onSend} loading={loading} />
    </div>
  );
}

function formatMoney(value) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽`;
}

function CatalogView({ accessToken }) {
  const [suppliers, setSuppliers] = useState([]);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [selectedSupplier, setSelectedSupplier] = useState(null);
  const [listLoading, setListLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const detailRequestRef = useRef(0);

  const loadSuppliers = async (nextQuery = appliedQuery) => {
    setListLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (nextQuery.trim()) params.set("query", nextQuery.trim());
      const body = await fetchJson(`/api/catalog/suppliers?${params.toString()}`, {}, accessToken);
      setSuppliers(body.suppliers || []);
      if (selectedId && !body.suppliers?.some((supplier) => supplier.id === selectedId)) {
        setSelectedId(null);
        setSelectedSupplier(null);
      }
    } catch (loadError) {
      setError(loadError.message || "Не удалось загрузить поставщиков.");
    } finally {
      setListLoading(false);
    }
  };

  useEffect(() => {
    loadSuppliers("");
  }, [accessToken]);

  const openSupplier = async (supplierId) => {
    const requestId = detailRequestRef.current + 1;
    detailRequestRef.current = requestId;
    setSelectedId(supplierId);
    setDetailLoading(true);
    setError("");
    try {
      const body = await fetchJson(`/api/catalog/suppliers/${encodeURIComponent(supplierId)}`, {}, accessToken);
      if (detailRequestRef.current !== requestId) return;
      setSelectedSupplier(body.supplier);
    } catch (loadError) {
      if (detailRequestRef.current !== requestId) return;
      setSelectedSupplier(null);
      setError(loadError.message || "Не удалось загрузить поставщика.");
    } finally {
      if (detailRequestRef.current === requestId) {
        setDetailLoading(false);
      }
    }
  };

  const submitSearch = (event) => {
    event.preventDefault();
    const nextQuery = query.trim();
    setAppliedQuery(nextQuery);
    loadSuppliers(nextQuery);
  };

  return (
    <div className="catalog-view">
      <div className="catalog-toolbar">
        <div>
          <div className="catalog-title">Каталог поставщиков</div>
          <div className="catalog-subtitle">{listLoading ? "Загрузка..." : `${suppliers.length} поставщиков`}</div>
        </div>
        <form className="catalog-search" onSubmit={submitSearch}>
          <Icon d={P.search} size={14} />
          <input
            type="search"
            value={query}
            placeholder="Название, ИНН или город"
            onChange={(event) => setQuery(event.target.value)}
          />
        </form>
      </div>

      {error && <div className="catalog-error">{error}</div>}

      <div className="catalog-layout">
        <div className="supplier-list" aria-busy={listLoading}>
          {suppliers.map((supplier) => (
            <button
              key={supplier.id}
              type="button"
              className={`supplier-row ${selectedId === supplier.id ? "supplier-row-active" : ""}`}
              onClick={() => openSupplier(supplier.id)}
            >
              <span className="supplier-main">
                <span className="supplier-name">{supplier.name}</span>
                <span className="supplier-meta">
                  {supplier.city || "Город не указан"} · {supplier.status || "Без статуса"}
                </span>
              </span>
              <span className="supplier-facts">
                <span>{supplier.item_count || 0} поз.</span>
                <span>от {formatMoney(supplier.min_price)}</span>
              </span>
              <span className="service-chips">
                {(supplier.service_types || []).slice(0, 4).map((serviceType) => (
                  <span className="service-chip" key={serviceType}>{serviceType}</span>
                ))}
              </span>
            </button>
          ))}
          {!listLoading && suppliers.length === 0 && (
            <div className="catalog-empty">Поставщики не найдены.</div>
          )}
        </div>

        <aside className="supplier-detail">
          {!selectedId && <div className="detail-empty">Выберите поставщика в списке.</div>}
          {selectedId && detailLoading && <div className="detail-empty">Загрузка карточки...</div>}
          {selectedSupplier && !detailLoading && (
            <>
              <div className="detail-head">
                <div>
                  <div className="detail-title">{selectedSupplier.name}</div>
                  <div className="detail-meta">{selectedSupplier.city || "Город не указан"} · {selectedSupplier.status || "Без статуса"}</div>
                </div>
                <div className="detail-count">{selectedSupplier.items?.length || 0} поз.</div>
              </div>
              <div className="detail-contacts">
                <span>ИНН {selectedSupplier.inn || "—"}</span>
                <span>{selectedSupplier.phone || "—"}</span>
                <span>{selectedSupplier.email || "—"}</span>
              </div>
              <div className="item-table">
                {(selectedSupplier.items || []).map((item) => (
                  <div className="item-row" key={item.id}>
                    <div className="item-name">
                      <strong>{item.name || "Без названия"}</strong>
                      <span>{[item.service_type, item.category].filter(Boolean).join(" · ") || "Без категории"}</span>
                    </div>
                    <div className="item-price">
                      <strong>{formatMoney(item.unit_price)}</strong>
                      <span>{item.unit || "—"}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

function AuthGate({ onSession }) {
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    if (loading) return;

    setLoading(true);
    setError("");
    setMessage("");
    const credentials = { email: email.trim(), password };
    try {
      const session = mode === "signup" ? await signUp(credentials) : await signIn(credentials);
      onSession(session);
    } catch (authError) {
      setError(authError.message || "Не удалось выполнить запрос авторизации.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <AnimatedBg />
      <form className="auth-card" onSubmit={submit}>
        <h1 className="auth-title">ARGUS</h1>
        <label className="auth-field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            autoComplete="email"
            required
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className="auth-field">
          <span>Пароль</span>
          <input
            type="password"
            value={password}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            required
            minLength={mode === "signup" ? 6 : undefined}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error && <div className="auth-error">{error}</div>}
        {message && <div className="auth-message">{message}</div>}
        <button className="auth-submit" type="submit" disabled={loading}>
          {loading ? "Проверка..." : mode === "signin" ? "Войти" : "Создать аккаунт"}
        </button>
        <button
          className="auth-switch"
          type="button"
          onClick={() => {
            setMode((current) => current === "signin" ? "signup" : "signin");
            setError("");
            setMessage("");
          }}
        >
          {mode === "signin" ? "Зарегистрироваться" : "Уже есть аккаунт"}
        </button>
      </form>
    </div>
  );
}

async function fetchJson(url, options = {}, accessToken) {
  const headers = new Headers(options.headers || {});
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  let response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (error) {
    throw new Error("Backend недоступен: проверьте, что FastAPI запущен командой make backend на http://localhost:8000.");
  }
  const text = await response.text();
  let body = {};
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text };
    }
  }
  if (!response.ok) {
    throw new Error(body.detail || body.error || response.statusText);
  }
  return body;
}

export default function App() {
  const [authReady, setAuthReady] = useState(false);
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState({ ready: false, stage: "idle", row_count: 0, embedded_count: 0 });
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("brief");
  const [view, setView] = useState("chat");
  const accessToken = session?.access_token;
  const userEmail = session?.user?.email || "user";

  useEffect(() => {
    let active = true;
    restoreSession()
      .then((storedSession) => {
        if (!active) return;
        setSession(storedSession);
        setAuthReady(true);
      })
      .catch(() => {
        if (active) setAuthReady(true);
      });

    return () => {
      active = false;
    };
  }, []);

  const resetSession = () => {
    setMessages([]);
    setMode("brief");
    setView("chat");
    fetchJson("/api/chat/reset", { method: "POST" }, accessToken).catch(() => {});
  };

  const logout = async () => {
    await logoutAuth(accessToken);
    setSession(null);
    setMessages([]);
    setMode("brief");
    setView("chat");
    setStatus({ ready: false, stage: "idle", row_count: 0, embedded_count: 0 });
  };

  const loadStatus = async () => {
    const body = await fetchJson("/api/catalog/status", {}, accessToken);
    setStatus(body);
  };

  useEffect(() => {
    if (!accessToken) return undefined;
    loadStatus().catch(() => {});
    return undefined;
  }, [accessToken]);

  useEffect(() => {
    if (status.ready || status.stage === "idle" || status.stage === "error") return undefined;
    const timer = window.setInterval(() => {
      loadStatus().catch(() => {});
    }, 900);
    return () => window.clearInterval(timer);
  }, [status.ready, status.stage, accessToken]);

  const uploadCatalog = async (file) => {
    const form = new FormData();
    form.append("file", file);
    setStatus((prev) => ({ ...prev, ready: false, stage: "queued", message: `Файл ${file.name} принят` }));
    setMessages([]);
    setMode("brief");
    setView("chat");
    try {
      const body = await fetchJson("/api/catalog/upload", { method: "POST", body: form }, accessToken);
      setStatus(body);
    } catch (error) {
      setStatus((prev) => ({ ...prev, ready: false, stage: "error", message: "Ошибка загрузки", error: error.message }));
    }
  };

  const sendMessage = async (message) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setLoading(true);
    try {
      const body = await fetchJson("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "brief", message }),
      }, accessToken);
      setMessages((prev) => [...prev, { role: "assistant", content: body.message }]);
    } catch (error) {
      setMessages((prev) => [...prev, { role: "assistant", content: `Не удалось обработать запрос: ${error.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const searchCatalog = async (message) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setLoading(true);
    try {
      const body = await fetchJson("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: message, limit: 3 }),
      }, accessToken);
      setMessages((prev) => [...prev, { role: "assistant", content: body.message || "Ничего не найдено." }]);
    } catch (error) {
      setMessages((prev) => [...prev, { role: "assistant", content: `Не удалось выполнить поиск: ${error.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = (message) => {
    if (mode === "search") {
      searchCatalog(message);
      return;
    }
    sendMessage(message);
  };

  if (!authReady) {
    return (
      <div className="auth-shell">
        <AnimatedBg />
        <div className="auth-card auth-card-loading">Проверка сессии...</div>
      </div>
    );
  }

  if (!session) {
    return <AuthGate onSession={setSession} />;
  }

  return (
    <>
      <AnimatedBg />
      <div className="app">
        <Sidebar
          status={status}
          userEmail={userEmail}
          view={view}
          onViewChange={setView}
          onReset={resetSession}
          onLogout={logout}
        />
        <main className="main">
          <Header status={status} view={view} onViewChange={setView} />
          {status.ready && view === "catalog" ? (
            <CatalogView accessToken={accessToken} />
          ) : status.ready ? (
            <ChatArea mode={mode} messages={messages} loading={loading} onModeChange={setMode} onSend={handleSend} />
          ) : (
            <UploadGate status={status} onUpload={uploadCatalog} />
          )}
          <div className="m-footer">ARGUS MVP · PostgreSQL/pgvector · LM Studio · локальная демонстрация</div>
        </main>
      </div>
    </>
  );
}
