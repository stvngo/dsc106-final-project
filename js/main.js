/* Fire After Dark: prototype.
   Everything comes from data/la_fires.json (built by scripts/build_web_data.py).
   Times in the data are Pacific Standard Time written without a zone, so they are parsed
   and formatted as UTC: the clock values shown are PST whatever the viewer's time zone. */

const parseTime = d3.utcParse("%Y-%m-%dT%H:%M");
const fmtDay = d3.utcFormat("%b %-d");
const ampm = (s) => s.replace("AM", "a.m.").replace("PM", "p.m.");
const fmtClock = (t) => ampm(d3.utcFormat("%-I:%M %p")(t)).replace(":00 ", " ");
const fmtWhen = (t) => `${fmtDay(t)}, ${fmtClock(t)}`;
const fmtHour = (h) => `${h % 12 || 12} ${h < 12 ? "a.m." : "p.m."}`;
const fmtInt = d3.format(",.0f");
const MAIN = ["palisades", "eaton", "hughes"];
const MIN = 60 * 1000;

let DATA = null;
const NAME = {};
const renders = [];

const fireColor = (id) => (MAIN.includes(id) ? `var(--${id})` : id === "none" ? "var(--unmatched)" : "var(--other)");
const width = (el) => Math.max(280, Math.floor(el.getBoundingClientRect().width));

/* ------------------------------------------------------------------ tooltip */

const tooltip = (() => {
  const el = document.getElementById("tooltip");
  return {
    show(event, title, rows) {
      el.replaceChildren();
      const t = document.createElement("div");
      t.className = "t-title";
      t.textContent = title;
      el.append(t);
      for (const [k, v] of rows) {
        const r = document.createElement("div");
        r.className = "t-row";
        const a = document.createElement("span");
        a.textContent = k;
        const b = document.createElement("b");
        b.textContent = v;
        r.append(a, b);
        el.append(r);
      }
      el.hidden = false;
      const pad = 14;
      const { innerWidth: vw, innerHeight: vh } = window;
      const box = el.getBoundingClientRect();
      let x = event.clientX + pad;
      let y = event.clientY + pad;
      if (x + box.width > vw - 8) x = event.clientX - box.width - pad;
      if (y + box.height > vh - 8) y = event.clientY - box.height - pad;
      el.style.left = `${Math.max(8, x)}px`;
      el.style.top = `${Math.max(8, y)}px`;
    },
    hide() { el.hidden = true; },
  };
})();

/* ------------------------------------------------------------------ shared helpers */

function svgFor(el, w, h) {
  d3.select(el).selectAll("*").remove();
  return d3.select(el).append("svg").attr("viewBox", `0 0 ${w} ${h}`).attr("width", w).attr("height", h);
}

/* Planar path: d3's spherical paths care about ring winding, shapely's output does not match it. */
function planarPath(proj) {
  return d3.geoPath(d3.geoTransform({
    point(x, y) { const p = proj([x, y]); this.stream.point(p[0], p[1]); },
  }));
}

function pixelPath(proj) {
  return (px) => `M${px.p.map((c) => proj(c).map((v) => v.toFixed(1)).join(",")).join("L")}Z`;
}

function fitProjection(bounds, w, h, pad = 0) {
  const [[x0, y0], [x1, y1]] = bounds;
  return d3.geoMercator().fitExtent([[pad, pad], [w - pad, h - pad]],
    { type: "MultiPoint", coordinates: [[x0, y0], [x1, y1], [x0, y1], [x1, y0]] });
}

function geomBounds(geometries) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  const visit = (c) => {
    if (typeof c[0] === "number") {
      x0 = Math.min(x0, c[0]); x1 = Math.max(x1, c[0]);
      y0 = Math.min(y0, c[1]); y1 = Math.max(y1, c[1]);
    } else c.forEach(visit);
  };
  geometries.forEach(visit);
  return [[x0, y0], [x1, y1]];
}

function segmented(id, initial, onChange) {
  const buttons = d3.selectAll(`#${id} button`);
  const set = (k) => buttons.attr("aria-pressed", function () { return String(this.dataset.k === k); });
  buttons.on("click", function () { set(this.dataset.k); onChange(this.dataset.k); });
  set(initial);
}

function legend(id, items) {
  const box = d3.select(`#${id}`);
  box.selectAll("*").remove();
  for (const it of items) {
    const el = box.append(it.onClick ? "button" : "span").attr("class", "item");
    if (it.onClick) el.attr("type", "button").attr("aria-pressed", String(!!it.pressed)).on("click", it.onClick);
    el.append("span").attr("class", `swatch ${it.kind || ""}`).style("background", it.color || null);
    el.append("span").text(it.label);
  }
}

function hourTicks(axis, scale) {
  // Hour labels, with the date under each midnight.
  axis.selectAll(".tick text").each(function (t) {
    const text = d3.select(this).text(null);
    text.append("tspan").attr("x", 0).attr("dy", "0.71em").text(fmtHour(t.getUTCHours()));
    if (t.getUTCHours() === 0) text.append("tspan").attr("x", 0).attr("dy", "1.2em").text(fmtDay(t));
  });
}

function nightRects(g, spans, x, h) {
  g.selectAll("rect.night").data(spans).join("rect").attr("class", "night")
    .attr("x", (d) => x(parseTime(d[0]))).attr("width", (d) => Math.max(0, x(parseTime(d[1])) - x(parseTime(d[0]))))
    .attr("y", 0).attr("height", h);
}

/* ------------------------------------------------------------------ 1. overview map */

const overview = { focus: null };

function renderOverview() {
  const el = document.getElementById("overview-map");
  const W = width(el);
  const H = Math.round(W * 0.6);
  const proj = fitProjection([[-119.27, 33.93], [-117.85, 34.72]], W, H);
  const path = planarPath(proj);
  const svg = svgFor(el, W, H).style("overflow", "hidden");
  svg.append("rect").attr("width", W).attr("height", H).style("fill", "var(--surface)");
  svg.append("path").datum(DATA.land).attr("class", "land").attr("d", path);

  const group = (f) => (MAIN.includes(f) ? f : f === "none" ? "none" : "other");
  const pix = svg.append("g").selectAll("path").data(DATA.pixels).join("path")
    .attr("class", "pixel").attr("d", pixelPath(proj)).style("fill", (d) => fireColor(d.f))
    .on("pointermove", (event, d) => tooltip.show(event, NAME[d.f] || "Not matched to a fire", [
      ["First seen", fmtWhen(parseTime(d.first))],
      ["Scans flagged", fmtInt(d.n)],
      ["Peak power", d.mw == null ? "n/a" : `${fmtInt(d.mw)} MW`],
    ]))
    .on("pointerleave", tooltip.hide);

  svg.append("g").selectAll("path").data(DATA.perimeters.features).join("path").attr("class", "perimeter").attr("d", path);

  // Labels beside each fire, on the side with open space.
  const side = { palisades: "below", eaton: "below", hughes: "left", kenneth: "left", hurst: "left",
                 lidia: "right", sunset: "below", auto: "right", laguna: "right" };
  const labels = svg.append("g");
  for (const f of DATA.fires) {
    if (!side[f.id]) continue;
    const pts = DATA.pixels.filter((p) => p.f === f.id).flatMap((p) => p.p.map(proj));
    if (!pts.length) continue;
    const [xs, ys] = [pts.map((p) => p[0]), pts.map((p) => p[1])];
    const [x0, x1, y0, y1] = [d3.min(xs), d3.max(xs), d3.min(ys), d3.max(ys)];
    const pos = { below: [(x0 + x1) / 2, y1 + 14, "middle"], left: [x0 - 6, (y0 + y1) / 2, "end"],
                  right: [x1 + 6, (y0 + y1) / 2, "start"] }[side[f.id]];
    const big = MAIN.includes(f.id);
    const t = labels.append("text").attr("class", `label map-label ${big ? "strong" : ""}`)
      .attr("x", pos[0]).attr("y", pos[1]).attr("text-anchor", pos[2]);
    t.append("tspan").attr("x", pos[0]).text(f.name);
    if (W > 520) {
      t.append("tspan").attr("x", pos[0]).attr("dy", "1.15em").attr("class", "small")
        .text(f.acres ? `${fmtInt(f.acres)} acres` : "no official perimeter");
    }
  }

  const apply = () => pix.classed("dimmed", (d) => overview.focus && group(d.f) !== overview.focus);
  apply();
  const pick = (k) => () => { overview.focus = overview.focus === k ? null : k; renderOverviewLegend(); apply(); };
  function renderOverviewLegend() {
    legend("overview-legend", [
      ...MAIN.map((k) => ({ label: NAME[k], color: fireColor(k), onClick: pick(k), pressed: overview.focus === k })),
      { label: "Smaller fires", color: "var(--other)", onClick: pick("other"), pressed: overview.focus === "other" },
      { label: "Not matched to a fire", color: "var(--unmatched)", onClick: pick("none"), pressed: overview.focus === "none" },
      { label: "Final perimeter", kind: "outline" },
    ]);
  }
  renderOverviewLegend();
}

/* ------------------------------------------------------------------ 2. detection time */

function renderDetection() {
  const el = document.getElementById("detection");
  const rows = DATA.fires.filter((f) => f.firstSeenMin != null)
    .map((f) => ({ ...f, a: parseTime(f.reported[0]), b: parseTime(f.reported[1]) }))
    .sort((p, q) => p.a - q.a);
  const W = width(el);
  const m = { top: 8, right: 56, bottom: 40, left: W < 480 ? 92 : 130 };
  const rowH = 34;
  const H = m.top + m.bottom + rows.length * rowH;
  const svg = svgFor(el, W, H);
  const g = svg.append("g").attr("transform", `translate(${m.left},${m.top})`);
  const iw = W - m.left - m.right;
  const ih = rows.length * rowH;
  const x = d3.scaleLinear().domain([-5, Math.max(70, d3.max(rows, (d) => d.firstSeenMin) + 10)]).range([0, iw]);
  const y = d3.scaleBand().domain(rows.map((d) => d.id)).range([0, ih]).padding(0.4);

  g.append("g").attr("class", "grid").call(d3.axisBottom(x).ticks(W < 480 ? 4 : 8).tickSize(ih).tickFormat(""));
  g.append("g").attr("class", "axis x").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x).ticks(W < 480 ? 4 : 8));
  g.append("text").attr("class", "label").attr("x", iw / 2).attr("y", ih + 34).attr("text-anchor", "middle")
    .text("Minutes after the earliest reported start");
  g.append("line").attr("class", "annot").attr("x1", x(0)).attr("x2", x(0)).attr("y1", 0).attr("y2", ih);

  const row = g.selectAll("g.row").data(rows).join("g").attr("class", "row")
    .attr("transform", (d) => `translate(0,${y(d.id) + y.bandwidth() / 2})`);
  row.append("rect").attr("class", "hit").attr("x", -m.left).attr("y", -rowH / 2).attr("width", iw + m.left + m.right).attr("height", rowH)
    .on("pointermove", (event, d) => tooltip.show(event, d.name, [
      ["Reported start", d.b - d.a > 0 ? `${fmtWhen(d.a)} to ${fmtClock(d.b)}` : fmtWhen(d.a)],
      ["First satellite scan", fmtWhen(parseTime(d.firstSeen))],
      ["Gap", `${d.firstSeenMin} min after the earliest report`],
    ]))
    .on("pointerleave", tooltip.hide);
  row.append("line").attr("x1", x(0)).attr("x2", (d) => x(Math.max(0.6, (d.b - d.a) / MIN)))
    .style("stroke", "var(--range)").attr("stroke-width", 8).attr("stroke-linecap", "round").attr("pointer-events", "none");
  row.append("circle").attr("cx", (d) => x(d.firstSeenMin)).attr("r", 6).style("fill", (d) => fireColor(d.id))
    .style("stroke", "var(--surface)").attr("stroke-width", 2).attr("pointer-events", "none");
  row.append("text").attr("class", "label").attr("x", (d) => x(d.firstSeenMin) + 10).attr("dy", "0.35em")
    .attr("pointer-events", "none").text((d) => `+${d.firstSeenMin} min`);
  row.append("text").attr("class", (d) => `label ${MAIN.includes(d.id) ? "strong" : ""}`).attr("x", -10).attr("dy", "0.35em")
    .attr("text-anchor", "end").attr("pointer-events", "none").text((d) => `${d.name} (${fmtDay(d.a)})`);
}

/* ------------------------------------------------------------------ 3. guess the hour */

const hours = { guess: null, period: "winds" };

function renderHours() {
  const el = document.getElementById("hours");
  const H24 = DATA.hourOfDay;
  const W = width(el);
  const H = Math.round(Math.min(360, Math.max(240, W * 0.45)));
  const m = { top: 28, right: 12, bottom: 38, left: 44 };
  const iw = W - m.left - m.right;
  const ih = H - m.top - m.bottom;
  const svg = svgFor(el, W, H);
  const g = svg.append("g").attr("transform", `translate(${m.left},${m.top})`);
  const xl = d3.scaleLinear().domain([0, 24]).range([0, iw]);
  const xb = d3.scaleBand().domain(d3.range(24)).range([0, iw]).padding(0.18);
  const ymax = d3.max([...H24.summer, ...H24.winds, ...H24.after]) * 100 * 1.15;
  const y = d3.scaleLinear().domain([0, ymax]).range([ih, 0]).nice();

  // January night in Los Angeles
  g.append("rect").attr("class", "night").attr("x", 0).attr("width", xl(H24.sunrise)).attr("height", ih);
  g.append("rect").attr("class", "night").attr("x", xl(H24.sunset)).attr("width", iw - xl(H24.sunset)).attr("height", ih);
  g.append("g").attr("class", "grid").call(d3.axisLeft(y).ticks(5).tickSize(-iw).tickFormat(""));
  g.append("g").attr("class", "axis y").call(d3.axisLeft(y).ticks(5).tickFormat((v) => `${v}%`));
  g.append("g").attr("class", "axis x").attr("transform", `translate(0,${ih})`)
    .call(d3.axisBottom(xb).tickValues(d3.range(0, 24, W < 520 ? 6 : 3)).tickFormat(fmtHour));
  g.append("text").attr("class", "label small").attr("x", 0).attr("y", -12).text("Share of the day's fire power in each hour");

  const revealed = hours.guess != null;
  document.getElementById("hours-reveal").hidden = !revealed;

  if (!revealed) {
    g.append("text").attr("class", "label strong").attr("x", iw / 2).attr("y", ih / 2).attr("text-anchor", "middle")
      .text("Click the hour you think fires burn hardest");
  } else {
    g.append("g").selectAll("rect").data(H24.summer).join("rect")
      .attr("x", (_, i) => xb(i)).attr("width", xb.bandwidth())
      .attr("y", (v) => y(v * 100)).attr("height", (v) => ih - y(v * 100))
      .attr("rx", 2).style("fill", "var(--summer)");
    const la = H24[hours.period];
    const line = d3.line().x((_, i) => xb(i) + xb.bandwidth() / 2).y((v) => y(v * 100)).curve(d3.curveMonotoneX);
    g.append("path").datum(la).attr("d", line).style("fill", "none").style("stroke", "var(--la)").attr("stroke-width", 2.5);
    g.append("g").selectAll("circle").data(la).join("circle")
      .attr("cx", (_, i) => xb(i) + xb.bandwidth() / 2).attr("cy", (v) => y(v * 100)).attr("r", 3)
      .style("fill", "var(--la)");
    const peak = (arr) => d3.maxIndex(arr);
    const laPeak = peak(la), suPeak = peak(H24.summer);
    g.append("text").attr("class", "label strong").attr("x", xb(laPeak) + xb.bandwidth() / 2).attr("y", y(la[laPeak] * 100) - 10)
      .attr("text-anchor", laPeak > 20 ? "end" : "middle").text(`LA peak ${fmtHour(laPeak)}`);
    g.append("text").attr("class", "label").attr("x", xb(suPeak) + xb.bandwidth() / 2).attr("y", y(H24.summer[suPeak] * 100) - 8)
      .attr("text-anchor", "middle").text(`Summer peak ${fmtHour(suPeak)}`);
    const gx = xb(hours.guess) + xb.bandwidth() / 2;
    g.append("line").attr("class", "guess-mark").attr("x1", gx).attr("x2", gx).attr("y1", 0).attr("y2", ih);
    g.append("text").attr("class", "label").attr("x", gx + (hours.guess > 18 ? -6 : 6)).attr("y", 12)
      .attr("text-anchor", hours.guess > 18 ? "end" : "start").style("fill", "var(--accent)")
      .text(`Your guess: ${fmtHour(hours.guess)}`);
  }

  // Clickable columns (before the guess) and hover readouts (after)
  g.append("g").selectAll("rect").data(d3.range(24)).join("rect")
    .attr("class", revealed ? "hit" : "guess-col").attr("x", (h) => xl(h)).attr("width", xl(1)).attr("height", ih)
    .on("click", (_, h) => { if (hours.guess == null) { hours.guess = h; renderHours(); } })
    .on("pointermove", (event, h) => {
      if (!revealed) return;
      tooltip.show(event, fmtHour(h), [
        ["Summer 2026, western US", `${(H24.summer[h] * 100).toFixed(1)}%`],
        [hours.period === "winds" ? "Palisades + Eaton, winds" : "Palisades + Eaton, after", `${(H24[hours.period][h] * 100).toFixed(1)}%`],
      ]);
    })
    .on("pointerleave", tooltip.hide);

  legend("hours-legend", revealed ? [
    { label: "Summer 2026 fires, western US (Project 3)", color: "var(--summer)" },
    { label: hours.period === "winds" ? "Palisades + Eaton, Jan 7–9" : "Palisades + Eaton, Jan 9–12", color: "var(--la)", kind: "line" },
    { label: "Night in LA in January", color: "var(--night)" },
  ] : [{ label: "Night in LA in January", color: "var(--night)" }]);
}

/* ------------------------------------------------------------------ 4. first 48 hours */

const first48 = { mode: "fires" };

function renderFirst48() {
  const el = document.getElementById("first48");
  const F = DATA.first48;
  const t0 = parseTime(F.start);
  const n = F.palisades.length;
  const times = d3.range(n).map((i) => new Date(+t0 + (i + 0.5) * F.stepMin * MIN));
  const series = first48.mode === "fires"
    ? [{ key: "palisades", label: "Palisades", values: F.palisades, color: "var(--palisades)" },
       { key: "eaton", label: "Eaton", values: F.eaton, color: "var(--eaton)" }]
    : [{ key: "g18", label: "GOES-18, west of LA", values: F.g18, color: "var(--ink)" },
       { key: "g16", label: "GOES-16, east of LA", values: F.g16, color: "var(--muted)" }];
  const W = width(el);
  const H = Math.round(Math.min(380, Math.max(240, W * 0.48)));
  const m = { top: 24, right: 16, bottom: 44, left: 40 };
  const iw = W - m.left - m.right;
  const ih = H - m.top - m.bottom;
  const svg = svgFor(el, W, H);
  const g = svg.append("g").attr("transform", `translate(${m.left},${m.top})`);
  const x = d3.scaleUtc().domain([t0, new Date(+t0 + n * F.stepMin * MIN)]).range([0, iw]);
  const y = d3.scaleLinear().domain([0, d3.max(series, (s) => d3.max(s.values)) * 1.15]).range([ih, 0]).nice();

  nightRects(g, F.nights, x, ih);
  g.append("g").attr("class", "grid").call(d3.axisLeft(y).ticks(5).tickSize(-iw).tickFormat(""));
  g.append("g").attr("class", "axis y").call(d3.axisLeft(y).ticks(5));
  const xa = g.append("g").attr("class", "axis x").attr("transform", `translate(0,${ih})`)
    .call(d3.axisBottom(x).ticks(d3.utcHour.every(W < 520 ? 12 : 6)));
  hourTicks(xa, x);
  g.append("text").attr("class", "label small").attr("x", 0).attr("y", -10)
    .text(first48.mode === "fires" ? "Fire radiative power, GW, 30-minute averages" : "All fires in the area, GW, reported power only");

  if (first48.mode === "fires") {
    for (const k of ["palisades", "eaton"]) {
      const f = DATA.fires.find((d) => d.id === k);
      const t = parseTime(f.reported[0]);
      g.append("line").attr("class", "annot").attr("x1", x(t)).attr("x2", x(t)).attr("y1", 0).attr("y2", ih);
      g.append("text").attr("class", "label small").attr("x", x(t) + 4).attr("y", k === "palisades" ? 10 : 24)
        .text(`${f.name} reported ${fmtClock(t)}`);
    }
  }

  const line = d3.line().defined((v) => v != null).x((_, i) => x(times[i])).y((v) => y(v));
  for (const s of series) {
    g.append("path").datum(s.values).attr("d", line).style("fill", "none").style("stroke", s.color).attr("stroke-width", 2);
    const i = d3.maxIndex(s.values);
    if (first48.mode === "fires") {
      g.append("text").attr("class", "label strong").attr("x", x(times[i]) + 6).attr("y", y(s.values[i]) - 4)
        .text(`${s.label}, ${s.values[i].toFixed(0)} GW`);
    }
  }

  const cross = g.append("line").attr("class", "crosshair").attr("y1", 0).attr("y2", ih).style("opacity", 0);
  g.append("rect").attr("class", "hit").attr("width", iw).attr("height", ih)
    .on("pointermove", (event) => {
      const i = Math.max(0, Math.min(n - 1, Math.floor((x.invert(d3.pointer(event)[0]) - t0) / (F.stepMin * MIN))));
      cross.attr("x1", x(times[i])).attr("x2", x(times[i])).style("opacity", 1);
      const a = new Date(+t0 + i * F.stepMin * MIN);
      tooltip.show(event, `${fmtWhen(a)} to ${fmtClock(new Date(+a + F.stepMin * MIN))}`,
        series.map((s) => [s.label, s.values[i] == null ? "no scan" : `${s.values[i].toFixed(1)} GW`]));
    })
    .on("pointerleave", () => { cross.style("opacity", 0); tooltip.hide(); });

  legend("first48-legend", [...series.map((s) => ({ label: s.label, color: s.color, kind: "line" })),
    { label: "Night", color: "var(--night)" }]);
}

/* ------------------------------------------------------------------ 5. growth replay */

const growth = { fire: "palisades", step: 0, timer: null, update: null };

function growthFrames() {
  const G = DATA.growth[growth.fire];
  if (!G.firstStep) {
    // First step at which each pixel burns, for the "burned earlier" state.
    G.firstStep = new Map();
    G.frames.forEach((fr, k) => fr.forEach(([p]) => { if (!G.firstStep.has(p)) G.firstStep.set(p, k); }));
  }
  return G;
}

function renderGrowth() {
  const G = growthFrames();
  const elMap = document.getElementById("growth-map");
  const elStrip = document.getElementById("growth-strip");
  const slider = document.getElementById("growth-slider");
  slider.max = G.frames.length - 1;
  growth.step = Math.min(growth.step, G.frames.length - 1);

  const ids = [...G.firstStep.keys()];
  const pixels = ids.map((i) => ({ ...DATA.pixels[i], i }));
  const perim = DATA.perimeters.features.filter((f) => f.properties.fire === growth.fire);
  const [[x0, y0], [x1, y1]] = geomBounds([...pixels.map((p) => p.p), ...perim.map((f) => f.geometry.coordinates)]);
  const pad = 0.01;
  const W = width(elMap);
  const H = Math.round(Math.min(460, Math.max(260, W * 0.62)));
  const proj = fitProjection([[x0 - pad, y0 - pad], [x1 + pad, y1 + pad]], W, H, 12);
  const path = planarPath(proj);
  const svg = svgFor(elMap, W, H).style("overflow", "hidden");
  svg.append("rect").attr("width", W).attr("height", H).style("fill", "var(--surface)");
  svg.append("path").datum(DATA.land).attr("class", "land").attr("d", path);
  const pix = svg.append("g").selectAll("path").data(pixels).join("path").attr("class", "pixel").attr("d", pixelPath(proj))
    .on("pointermove", (event, d) => {
      const now = new Map(G.frames[growth.step]).get(d.i);
      tooltip.show(event, `${NAME[growth.fire]} pixel`, [
        ["First seen", fmtWhen(parseTime(d.first))],
        ["Power in this half hour", now == null ? "not burning" : `${fmtInt(now)} MW`],
      ]);
    })
    .on("pointerleave", tooltip.hide);
  svg.append("g").selectAll("path").data(perim).join("path").attr("class", "perimeter").attr("d", path);
  const fire = DATA.fires.find((f) => f.id === growth.fire);
  if (fire.origin) {
    const [ox, oy] = proj(fire.origin);
    svg.append("circle").attr("class", "origin").attr("cx", ox).attr("cy", oy).attr("r", 5);
  }
  // 2 km scale bar
  const kmPerDeg = 111.32 * Math.cos(((y0 + y1) / 2) * Math.PI / 180);
  const a = proj([x0, y0]), b = proj([x0 + 2 / kmPerDeg, y0]);
  const bar = svg.append("g").attr("transform", `translate(${16},${H - 18})`);
  bar.append("line").attr("x2", b[0] - a[0]).style("stroke", "var(--ink)").attr("stroke-width", 2);
  bar.append("text").attr("class", "label small").attr("x", (b[0] - a[0]) / 2).attr("y", -6).attr("text-anchor", "middle").text("2 km");

  // Power strip under the map: click or drag to jump.
  const SW = width(elStrip);
  const SH = 72;
  const sm = { top: 6, right: 8, bottom: 22, left: 8 };
  const siw = SW - sm.left - sm.right;
  const sih = SH - sm.top - sm.bottom;
  const strip = svgFor(elStrip, SW, SH).append("g").attr("transform", `translate(${sm.left},${sm.top})`);
  const start = parseTime(G.start);
  const end = new Date(+start + G.frames.length * G.stepMin * MIN);
  const sx = d3.scaleUtc().domain([start, end]).range([0, siw]);
  const sy = d3.scaleLinear().domain([0, d3.max(G.gw) || 1]).range([sih, 0]);
  nightRects(strip, G.nights, sx, sih);
  strip.append("path").datum(G.gw).style("fill", fireColor(growth.fire)).style("fill-opacity", 0.35)
    .style("stroke", fireColor(growth.fire)).attr("stroke-width", 1.2)
    .attr("d", d3.area().defined((v) => v != null).x((_, i) => sx(new Date(+start + (i + 0.5) * G.stepMin * MIN))).y0(sih).y1((v) => sy(v)));
  strip.append("g").attr("class", "axis x").attr("transform", `translate(0,${sih})`)
    .call(d3.axisBottom(sx).ticks(d3.utcDay.every(1)).tickFormat(fmtDay).tickSizeOuter(0));
  const marker = strip.append("line").attr("y1", 0).attr("y2", sih).style("stroke", "var(--accent)").attr("stroke-width", 2);
  const seek = (event) => {
    const t = sx.invert(Math.max(0, Math.min(siw, d3.pointer(event, strip.node())[0])));
    setGrowthStep(Math.min(G.frames.length - 1, Math.floor((t - start) / (G.stepMin * MIN))));
  };
  strip.append("rect").attr("class", "hit").attr("width", siw).attr("height", sih + sm.bottom)
    .on("pointerdown", (event) => { stopGrowth(); seek(event); })
    .on("pointermove", (event) => { if (event.buttons) seek(event); });

  const opacity = d3.scaleSqrt().domain([0, d3.max(G.frames.flat(), (d) => d[1]) || 1]).range([0.35, 1]);
  const isNight = (t) => G.nights.some(([p, q]) => t >= parseTime(p) && t < parseTime(q));
  growth.update = () => {
    const k = growth.step;
    const now = new Map(G.frames[k]);
    pix.style("fill", (d) => (now.has(d.i) ? fireColor(growth.fire) : "var(--burned)"))
      .style("opacity", (d) => (now.has(d.i) ? opacity(now.get(d.i)) : G.firstStep.get(d.i) < k ? 1 : 0))
      .style("pointer-events", (d) => (G.firstStep.get(d.i) <= k ? null : "none"));
    const t = new Date(+start + k * G.stepMin * MIN);
    marker.attr("x1", sx(t)).attr("x2", sx(t));
    slider.value = k;
    const h = (k * G.stepMin) / 60;
    document.getElementById("growth-clock").value =
      `${fmtWhen(t)} · ${h < 1 ? "start" : `+${h % 1 ? h.toFixed(1) : h} h`}${isNight(t) ? " · night" : ""}`;
  };
  growth.update();

  legend("growth-legend", [
    { label: "Burning in this half hour (darker = more power)", color: fireColor(growth.fire) },
    { label: "Burned earlier", color: "var(--burned)" },
    { label: "Final perimeter", kind: "outline" },
    ...(fire.origin ? [{ label: "Reported origin", kind: "ring" }] : []),
  ]);
}

function setGrowthStep(k) {
  growth.step = k;
  if (growth.update) growth.update();
}

function stopGrowth() {
  if (growth.timer) growth.timer.stop();
  growth.timer = null;
  document.getElementById("growth-play").setAttribute("aria-pressed", "false");
  document.getElementById("growth-play").setAttribute("aria-label", "Play");
}

function playGrowth() {
  const G = DATA.growth[growth.fire];
  if (growth.step >= G.frames.length - 1) setGrowthStep(0);
  const btn = document.getElementById("growth-play");
  btn.setAttribute("aria-pressed", "true");
  btn.setAttribute("aria-label", "Pause");
  growth.timer = d3.interval(() => {
    if (growth.step >= G.frames.length - 1) { stopGrowth(); return; }
    setGrowthStep(growth.step + 1);
  }, 120);
}

/* ------------------------------------------------------------------ 6. day one */

const day1 = { mode: "cum" };

function renderDay1() {
  const el = document.getElementById("day1");
  const W = width(el);
  const H = Math.round(Math.min(360, Math.max(240, W * 0.45)));
  const m = { top: 24, right: 16, bottom: 40, left: 44 };
  const iw = W - m.left - m.right;
  const ih = H - m.top - m.bottom;
  const svg = svgFor(el, W, H);
  const g = svg.append("g").attr("transform", `translate(${m.left},${m.top})`);
  const series = MAIN.map((k) => ({ key: k, values: DATA.daily[k][day1.mode] }));
  const n = d3.max(series, (s) => s.values.length);
  const x = d3.scaleLinear().domain([0, 10]).range([0, iw]);
  const y = day1.mode === "cum"
    ? d3.scaleLinear().domain([0, 100]).range([ih, 0])
    : d3.scaleLinear().domain([0, d3.max(series, (s) => d3.max(s.values)) * 1.1]).range([ih, 0]).nice();

  g.append("g").attr("class", "grid").call(d3.axisLeft(y).ticks(5).tickSize(-iw).tickFormat(""));
  g.append("g").attr("class", "axis y").call(d3.axisLeft(y).ticks(5).tickFormat((v) => (day1.mode === "cum" ? `${v}%` : v)));
  g.append("g").attr("class", "axis x").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x).ticks(10));
  g.append("text").attr("class", "label").attr("x", iw / 2).attr("y", ih + 34).attr("text-anchor", "middle").text("Days after the reported start");
  g.append("text").attr("class", "label small").attr("x", 0).attr("y", -10)
    .text(day1.mode === "cum" ? "Share of the fire's total energy released so far" : "Fire radiative power, GW, hourly average");
  g.append("line").attr("class", "annot").attr("x1", x(1)).attr("x2", x(1)).attr("y1", 0).attr("y2", ih);
  g.append("text").attr("class", "label small").attr("x", x(1) + 4).attr("y", ih - 6).text("end of day 1");

  const xi = (i) => x((i + (day1.mode === "gw" ? 0.5 : 1)) / 24);
  const line = d3.line().defined((v) => v != null).x((_, i) => xi(i)).y((v) => y(v));
  for (const s of series) {
    g.append("path").datum(s.values).attr("d", line).style("fill", "none").style("stroke", fireColor(s.key)).attr("stroke-width", 2);
    if (day1.mode === "cum") {
      const v = s.values[23];
      g.append("circle").attr("cx", x(1)).attr("cy", y(v)).attr("r", 4.5).style("fill", fireColor(s.key)).style("stroke", "var(--surface)").attr("stroke-width", 1.5);
      g.append("text").attr("class", "label strong").attr("x", x(1) + 9).attr("y", y(v)).attr("dy", s.key === "hughes" ? "1em" : "0.35em")
        .text(`${NAME[s.key]} ${v.toFixed(0)}%`);
    } else {
      const i = d3.maxIndex(s.values);
      g.append("text").attr("class", "label strong").attr("x", xi(i) + 6).attr("y", y(s.values[i]) - 4).text(`${NAME[s.key]}`);
    }
  }

  const cross = g.append("line").attr("class", "crosshair").attr("y1", 0).attr("y2", ih).style("opacity", 0);
  g.append("rect").attr("class", "hit").attr("width", iw).attr("height", ih)
    .on("pointermove", (event) => {
      const i = Math.max(0, Math.min(n - 1, Math.floor(x.invert(d3.pointer(event)[0]) * 24)));
      cross.attr("x1", xi(i)).attr("x2", xi(i)).style("opacity", 1);
      tooltip.show(event, `Day ${(i / 24 + 1).toFixed(0)}, hour ${(i % 24) + 1}`, series.map((s) => [NAME[s.key],
        s.values[i] == null ? "n/a" : day1.mode === "cum" ? `${s.values[i].toFixed(0)}% released` : `${s.values[i].toFixed(1)} GW`]));
    })
    .on("pointerleave", () => { cross.style("opacity", 0); tooltip.hide(); });

  legend("day1-legend", MAIN.map((k) => ({ label: NAME[k], color: fireColor(k), kind: "line" })));
}

/* ------------------------------------------------------------------ 7. energy bars */

const energy = { key: "energyTJ" };

function renderEnergy() {
  const el = document.getElementById("energy");
  const rows = DATA.fires.filter((f) => f.acres).sort((a, b) => b[energy.key] - a[energy.key]);
  const W = width(el);
  const m = { top: 8, right: 70, bottom: 30, left: 84 };
  const rowH = 34;
  const H = m.top + m.bottom + rows.length * rowH;
  const iw = W - m.left - m.right;
  const ih = rows.length * rowH;
  const svg = svgFor(el, W, H);
  const g = svg.append("g").attr("transform", `translate(${m.left},${m.top})`);
  const x = d3.scaleLinear().domain([0, d3.max(rows, (d) => d[energy.key])]).range([0, iw]).nice();
  const y = d3.scaleBand().domain(rows.map((d) => d.id)).range([0, ih]).padding(0.32);
  const bh = Math.min(24, y.bandwidth());
  const fmt = (v) => (v < 10 ? v.toFixed(1) : fmtInt(v));

  g.append("g").attr("class", "grid").call(d3.axisBottom(x).ticks(W < 480 ? 3 : 6).tickSize(ih).tickFormat(""));
  g.append("g").attr("class", "axis x").attr("transform", `translate(0,${ih})`).call(d3.axisBottom(x).ticks(W < 480 ? 3 : 5).tickFormat(d3.format(",")));
  // Bars with a rounded data end and a square baseline end.
  const bar = (d) => {
    const w = Math.max(1, x(d[energy.key]));
    const r = Math.min(4, w / 2, bh / 2);
    const y0 = y(d.id) + (y.bandwidth() - bh) / 2;
    return `M0,${y0}H${w - r}Q${w},${y0} ${w},${y0 + r}V${y0 + bh - r}Q${w},${y0 + bh} ${w - r},${y0 + bh}H0Z`;
  };
  g.selectAll("path.bar").data(rows).join("path").attr("class", "bar").attr("d", bar).style("fill", (d) => fireColor(d.id))
    .on("pointermove", (event, d) => tooltip.show(event, d.name, [
      ["Total energy", `${fmt(d.energyTJ)} TJ`], ["Per burned acre", `${fmtInt(d.mjPerAcre)} MJ`], ["Final size", `${fmtInt(d.acres)} acres`],
    ]))
    .on("pointerleave", tooltip.hide);
  g.selectAll("text.value").data(rows).join("text").attr("class", "label value")
    .attr("x", (d) => Math.max(1, x(d[energy.key])) + 6).attr("y", (d) => y(d.id) + y.bandwidth() / 2).attr("dy", "0.35em")
    .text((d) => `${fmt(d[energy.key])} ${energy.key === "energyTJ" ? "TJ" : "MJ"}`);
  g.selectAll("text.name").data(rows).join("text").attr("class", (d) => `label name ${MAIN.includes(d.id) ? "strong" : ""}`)
    .attr("x", -8).attr("y", (d) => y(d.id) + y.bandwidth() / 2).attr("dy", "0.35em").attr("text-anchor", "end").text((d) => d.name);
}

/* ------------------------------------------------------------------ boot */

function renderAll() {
  for (const r of renders) r();
}

function wire() {
  segmented("hours-toggle", hours.period, (k) => { hours.period = k; renderHours(); });
  document.getElementById("hours-reset").addEventListener("click", () => { hours.guess = null; renderHours(); });
  segmented("first48-toggle", first48.mode, (k) => { first48.mode = k; renderFirst48(); });
  segmented("growth-fire", growth.fire, (k) => { stopGrowth(); growth.fire = k; growth.step = 0; renderGrowth(); });
  segmented("day1-toggle", day1.mode, (k) => { day1.mode = k; renderDay1(); });
  segmented("energy-toggle", energy.key, (k) => { energy.key = k; renderEnergy(); });
  document.getElementById("growth-play").addEventListener("click", () => (growth.timer ? stopGrowth() : playGrowth()));
  document.getElementById("growth-slider").addEventListener("input", (e) => { stopGrowth(); setGrowthStep(+e.target.value); });

  let pending = null;
  let lastW = window.innerWidth;
  window.addEventListener("resize", () => {
    if (window.innerWidth === lastW) return;
    lastW = window.innerWidth;
    clearTimeout(pending);
    pending = setTimeout(renderAll, 150);
  });
}

function writeNotes() {
  const M = DATA.meta;
  document.getElementById("data-summary").textContent =
    `${M.satellite} ${M.product}, every scan from ${fmtWhen(parseTime(M.start))} to ${fmtWhen(parseTime(M.end))} ` +
    `(${fmtInt(M.scans)} scans) over 119.3°W to 117.6°W, 33.8°N to 34.8°N. ${fmtInt(M.rawPixels)} fire pixels, ` +
    `${fmtInt(M.keptPixels)} after dropping pixels that fired only once in two hours. Each pixel is about ` +
    `${M.pixelKm[0]} by ${M.pixelKm[1]} km here.`;
  document.getElementById("nopower-share").textContent = `${Math.round(M.noPowerShare * 100)}%`;
}

async function init() {
  try {
    DATA = await d3.json("data/la_fires.json");
  } catch (err) {
    const p = document.createElement("p");
    p.className = "load-error";
    p.textContent = "Could not load data/la_fires.json. Open this page through a web server (for example python3 -m http.server), not as a file.";
    document.querySelector("main").prepend(p);
    return;
  }
  for (const f of DATA.fires) NAME[f.id] = f.name;
  renders.push(renderOverview, renderDetection, renderHours, renderFirst48, renderGrowth, renderDay1, renderEnergy);
  wire();
  writeNotes();
  renderAll();
}

init();
