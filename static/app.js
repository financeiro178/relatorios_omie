/* Análise Financeira OMIE — frontend (JS puro, sem dependências) */
"use strict";

// ===================================================== ícones (SVG inline)
const P = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const ICONS = {
  grid: P('<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>'),
  list: P('<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/>'),
  flow: P('<path d="M3 17l5-5 4 4 8-8"/><path d="M17 8h4v4"/>'),
  tag: P('<path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0l-7-7A2 2 0 0 1 3 12.2V5a2 2 0 0 1 2-2h7.2a2 2 0 0 1 1.4.6l7 7a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.3"/>'),
  bank: P('<path d="M3 10h18"/><path d="M5 10v8M9 10v8M15 10v8M19 10v8"/><path d="M3 21h18"/><path d="M12 3l9 5H3z"/>'),
  users: P('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
  sync: P('<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>'),
  download: P('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>'),
  print: P('<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8" rx="1"/>'),
  search: P('<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/>'),
  menu: P('<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>'),
  inbox: P('<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.5L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.5A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.5z"/>'),
  receber: P('<path d="M12 3v14"/><path d="M6 11l6 6 6-6"/><path d="M5 21h14"/>'),
  pagar: P('<path d="M12 21V7"/><path d="M6 13l6-6 6 6"/><path d="M5 3h14"/>'),
  saldo: P('<path d="M12 3v18"/><path d="M5 7h14"/><path d="M5 7l-2.5 5a3 3 0 0 0 5 0L5 7z"/><path d="M19 7l-2.5 5a3 3 0 0 0 5 0L19 7z"/>'),
  clock: P('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
  shield: P('<path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z"/><path d="M9 12l2 2 4-4"/>'),
  logout: P('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>'),
  alvo: P('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="0.5"/>'),
  predio: P('<path d="M3 21h18"/><path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2"/>'),
};
const ic = (n) => ICONS[n] || "";

// ===================================================== utilidades
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const fmtBRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const moeda = (v) => fmtBRL.format(Number(v) || 0);
const STATUS_OK = new Set(["PAGO", "RECEBIDO", "LIQUIDADO", "BAIXADO", "CONCILIADO"]);

function unidade(v) { const a = Math.abs(v); if (a >= 1e6) return [1e6, " mi"]; if (a >= 1e3) return [1e3, " mil"]; return [1, ""]; }
function moedaCurta(v) {
  v = Number(v) || 0; const [f, s] = unidade(v);
  if (f === 1) return fmtBRL.format(v);
  return "R$ " + (v / f).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + s;
}
function esc(s) { return s == null ? "" : String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function dataBR(iso) { if (!iso) return "—"; const p = String(iso).split("-"); return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : iso; }
function mesBR(aaaamm) { if (!aaaamm) return "—"; const p = String(aaaamm).split("-"); const M = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]; return p.length >= 2 ? `${M[+p[1] - 1] || p[1]}/${p[0].slice(2)}` : aaaamm; }
function classeValor(v) { return (Number(v) || 0) < 0 ? "neg" : "pos"; }
function badgeStatus(s) {
  const up = (s || "").toUpperCase();
  let cls = "aberto";
  if (STATUS_OK.has(up)) cls = "ok";
  else if (up.includes("ATRAS") || up.includes("VENCID") || up.includes("CANCEL")) cls = "alerta";
  return `<span class="badge ${cls}">${esc(s || "—")}</span>`;
}

async function api(path, params = {}) {
  const todos = { ...coletarFiltros(), ...params };
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(todos)) if (v !== "" && v != null) qs.set(k, v);
  const r = await fetch(`${path}?${qs.toString()}`);
  if (r.status === 401) { window.location = "/login"; throw new Error("Sessão expirada."); }
  const j = await r.json();
  if (j && j.erro) throw new Error(j.erro);
  return j;
}
async function postJSON(url, payload, msgSel) {
  try {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const j = await r.json();
    if (!r.ok || j.erro) { const m = j.erro || "Erro ao salvar."; if (msgSel) $(msgSel).textContent = m; else alert(m); return null; }
    return j;
  } catch (e) { const m = "Falha de conexão."; if (msgSel) $(msgSel).textContent = m; else alert(m); return null; }
}

// ===================================================== tooltip
const tipEl = () => $("#tooltip");
let tipMap = {}, tipSeq = 0;
function tip(html) { const id = "t" + tipSeq++; tipMap[id] = html; return id; }
function posTip(x, y) {
  const el = tipEl(), r = el.getBoundingClientRect();
  let nx = x + 14, ny = y + 14;
  if (nx + r.width > innerWidth - 8) nx = x - r.width - 14;
  if (ny + r.height > innerHeight - 8) ny = y - r.height - 14;
  el.style.left = nx + "px"; el.style.top = ny + "px";
}

// ===================================================== estado
// Telas do app (a antiga seção "Análise" virou o app inteiro)
const VIEWS = [
  { id: "dashboard", nome: "Visão Geral", ico: "grid" },
  { id: "dre", nome: "DRE", ico: "saldo" },
  { id: "orcado", nome: "Previsto × Realizado", ico: "alvo" },
  { id: "fluxo", nome: "Fluxo de Caixa", ico: "flow" },
  { id: "categoria", nome: "Categorias", ico: "tag" },
  { id: "departamento", nome: "Departamentos", ico: "predio" },
  { id: "conta", nome: "Contas", ico: "bank" },
  { id: "cliente", nome: "Clientes", ico: "users" },
  { id: "titulos", nome: "Títulos", ico: "list" },
];
function viewInfo(id) { return VIEWS.concat([{ id: "admin", nome: "Administração" }]).find((v) => v.id === id) || { nome: "" }; }
const REL_ALVO = "#conteudo";

const state = {
  empresas: [], view: "dashboard", preset: "",
  titulos: { pagina: 1, por_pagina: 100, ordenar: "vencimento", dir: "desc" },
  pollTimer: null, usuario: null, admin: null,
};

// ===================================================== multiselect (com busca)
function criarMulti(container, placeholder) {
  let options = [], filtro = "";
  const selected = new Set();
  let onChange = () => {};
  container.classList.add("multi");
  container.innerHTML = `<div class="multi-botao"><span class="rotulo-multi">${placeholder}</span><span class="seta">${P('<path d="M6 9l6 6 6-6"/>')}</span></div><div class="multi-lista escondido"></div>`;
  const botao = $(".multi-botao", container), lista = $(".multi-lista", container), rotulo = $(".rotulo-multi", container);

  function rotuloDe(v) { const o = options.find((o) => String(o.value) === String(v)); return o ? o.label : v; }
  function atualizarRotulo() {
    rotulo.textContent = selected.size === 0 ? placeholder : selected.size === 1 ? rotuloDe([...selected][0]) : `${selected.size} selecionadas`;
  }
  function desenhar() {
    const f = filtro.toLowerCase();
    const itens = options.filter((o) => !f || o.label.toLowerCase().includes(f)).map((o) =>
      `<label><input type="checkbox" value="${esc(o.value)}" ${selected.has(String(o.value)) ? "checked" : ""}><span>${esc(o.label)}</span></label>`).join("");
    lista.innerHTML = `<div class="busca-mini"><input type="text" placeholder="filtrar…" value="${esc(filtro)}"></div>
      <div class="acoes"><a data-act="todos">Selecionar todos</a><a data-act="limpar">Limpar</a></div>
      ${itens || '<div style="padding:10px;color:#99a0a8">nenhum item</div>'}`;
    const bi = $(".busca-mini input", lista);
    bi.addEventListener("input", (e) => { filtro = e.target.value; const pos = e.target.selectionStart; desenhar(); const ni = $(".busca-mini input", lista); ni.focus(); ni.setSelectionRange(pos, pos); });
  }
  botao.addEventListener("click", (e) => {
    e.stopPropagation();
    const abrir = lista.classList.contains("escondido");
    $$(".multi-lista").forEach((l) => l.classList.add("escondido"));
    $$(".multi").forEach((m) => m.classList.remove("aberto"));
    if (abrir) { filtro = ""; desenhar(); lista.classList.remove("escondido"); container.classList.add("aberto"); }
  });
  lista.addEventListener("click", (e) => {
    e.stopPropagation();
    const act = e.target.dataset.act; if (!act) return;
    const visiveis = options.filter((o) => !filtro || o.label.toLowerCase().includes(filtro.toLowerCase()));
    if (act === "todos") visiveis.forEach((o) => selected.add(String(o.value)));
    else selected.clear();
    desenhar(); atualizarRotulo(); onChange();
  });
  lista.addEventListener("change", (e) => {
    if (e.target.matches("input[type=checkbox]")) {
      e.target.checked ? selected.add(e.target.value) : selected.delete(e.target.value);
      atualizarRotulo(); onChange();
    }
  });
  return {
    setOptions(novas) { options = novas; for (const v of [...selected]) if (!options.some((o) => String(o.value) === v)) selected.delete(v); atualizarRotulo(); },
    getSelected() { return [...selected]; },
    rotuloDe, limpar() { selected.clear(); atualizarRotulo(); },
    remover(v) { selected.delete(String(v)); atualizarRotulo(); },
    onChange(fn) { onChange = fn; },
  };
}
let mC, mS, mCat, mEmp;
document.addEventListener("click", () => { $$(".multi-lista").forEach((l) => l.classList.add("escondido")); $$(".multi").forEach((m) => m.classList.remove("aberto")); });

// ===================================================== filtros
function coletarFiltros() {
  const f = {
    empresas: mEmp ? mEmp.getSelected().join(",") : "",
    tipo: $("#fTipo").value, campo_data: $("#fCampoData").value,
    de: $("#fDe").value, ate: $("#fAte").value, busca: $("#fBusca").value.trim(),
  };
  if (mC) f.contas = mC.getSelected().join(",");
  if (mS) f.status = mS.getSelected().join(",");
  if (mCat) f.categorias = mCat.getSelected().join(",");
  return f;
}
function setPeriodo(p, redesenhar = true) {
  state.preset = p;
  $$("#segPeriodo button").forEach((b) => b.classList.toggle("ativa", b.dataset.p === p));
  $("#campoDe").style.display = p === "custom" ? "" : "none";
  $("#campoAte").style.display = p === "custom" ? "" : "none";
  const hoje = new Date(), iso = (d) => d.toISOString().slice(0, 10);
  const A = hoje.getFullYear(), M = hoje.getMonth();
  const prim = (a, m) => iso(new Date(a, m, 1)), ult = (a, m) => iso(new Date(a, m + 1, 0));
  if (p === "mes") { $("#fDe").value = prim(A, M); $("#fAte").value = ult(A, M); }
  else if (p === "mes_ant") { $("#fDe").value = prim(A, M - 1); $("#fAte").value = ult(A, M - 1); }
  else if (p === "ano") { $("#fDe").value = `${A}-01-01`; $("#fAte").value = `${A}-12-31`; }
  else if (p === "ano_ant") { $("#fDe").value = `${A - 1}-01-01`; $("#fAte").value = `${A - 1}-12-31`; }
  else if (p === "") { $("#fDe").value = ""; $("#fAte").value = ""; }
  if (redesenhar) aplicar();
}

function contexto() {
  const sel = mEmp ? mEmp.getSelected() : [];
  let emp;
  if (!sel.length) emp = `Todas as empresas (${state.empresas.length})`;
  else if (sel.length <= 3) emp = sel.map((id) => { const e = state.empresas.find((x) => x.empresa_id === id); return e ? (e.razao_social || e.nome) : id; }).join(" • ");
  else emp = `${sel.length} empresas`;
  let contas = "todas as contas";
  if (mC && mC.getSelected().length) contas = mC.getSelected().length === 1 ? mC.rotuloDe(mC.getSelected()[0]) : `${mC.getSelected().length} contas`;
  const de = $("#fDe").value, ate = $("#fAte").value;
  const periodo = de || ate ? `${de ? dataBR(de) : "início"} – ${ate ? dataBR(ate) : "hoje"}` : "todo o período";
  return { emp, contas, periodo };
}
function aplicarContexto() {
  $("#pageTitle").textContent = viewInfo(state.view).nome;
  if (state.view === "admin") {
    $("#pageContext").innerHTML = "Gerencie usuários, contas OMIE e permissões de acesso";
    return;
  }
  if (state.view === "orcado") {
    const c = contexto();
    $("#pageContext").innerHTML = `<b>${esc(c.emp)}</b> &nbsp;·&nbsp; Orçamento de caixa do OMIE × realizado da análise (por vencimento)`;
    return;
  }
  const c = contexto();
  $("#pageContext").innerHTML = `<b>${esc(c.emp)}</b> &nbsp;·&nbsp; Conta: ${esc(c.contas)} &nbsp;·&nbsp; ${esc(c.periodo)}`;
}

function desenharChipsAtivos() {
  const chips = [];
  const tipo = $("#fTipo").value;
  if (tipo !== "ambos") chips.push({ k: "Tipo", v: tipo === "pagar" ? "A Pagar" : "A Receber", rm: () => { $("#fTipo").value = "ambos"; } });
  const de = $("#fDe").value, ate = $("#fAte").value;
  if (de || ate) chips.push({ k: "Período", v: `${de ? dataBR(de) : "…"}–${ate ? dataBR(ate) : "…"}`, rm: () => setPeriodo("", false) });
  if (mC) mC.getSelected().forEach((v) => chips.push({ k: "Conta", v: mC.rotuloDe(v), rm: () => mC.remover(v) }));
  if (mS) mS.getSelected().forEach((v) => chips.push({ k: "Status", v, rm: () => mS.remover(v) }));
  if (mCat) mCat.getSelected().forEach((v) => chips.push({ k: "Categoria", v: mCat.rotuloDe(v), rm: () => mCat.remover(v) }));
  const b = $("#fBusca").value.trim();
  if (b) chips.push({ k: "Busca", v: b, rm: () => { $("#fBusca").value = ""; } });

  const box = $("#chipsAtivos");
  if (!chips.length) { box.innerHTML = ""; return; }
  box.innerHTML = chips.map((c, i) => `<span class="fchip"><span class="muted">${esc(c.k)}:</span> <b>${esc(c.v)}</b><button data-ci="${i}" title="remover">${P('<path d="M5 5l10 10M15 5L5 15"/>')}</button></span>`).join("")
    + `<a class="fchip" id="limparTudo" style="cursor:pointer"><b>Limpar tudo</b></a>`;
  $$("#chipsAtivos .fchip button").forEach((btn) => btn.addEventListener("click", () => { chips[+btn.dataset.ci].rm(); aplicar(); }));
  $("#limparTudo")?.addEventListener("click", limparFiltros);
}
function limparFiltros() {
  $("#fTipo").value = "ambos"; $("#fCampoData").value = "vencimento"; $("#fBusca").value = "";
  mC.limpar(); mS.limpar(); mCat.limpar(); setPeriodo("", false); aplicar();
}

// ===================================================== render (roteador)
function aplicar() { state.titulos.pagina = 1; render(); }
function render() {
  tipMap = {};
  const v = state.view;
  $$("#nav button").forEach((b) => b.classList.toggle("ativa", b.dataset.view === v));
  const ehAdmin = v === "admin";
  const semToolbar = ehAdmin || v === "orcado";   // orcado tem período próprio (ano/mês)
  document.querySelector(".toolbar").style.display = semToolbar ? "none" : "";
  $("#empresasSel").style.display = ehAdmin ? "none" : "";   // filtro de empresas vale também no orcado
  $("#btnExportar").style.display = semToolbar ? "none" : "";
  $("#btnImprimir").style.display = ehAdmin ? "none" : "";
  aplicarContexto();
  if (ehAdmin) { $("#chipsAtivos").innerHTML = ""; return renderAdmin(); }
  if (v === "orcado") { $("#chipsAtivos").innerHTML = ""; return renderOrcado(); }
  desenharChipsAtivos();
  if (v === "dashboard") return renderDashboard();
  if (v === "dre") return renderDre();
  if (v === "titulos") return renderTitulos();
  if (v === "fluxo") return renderFluxo();
  return renderAgrupado(v);   // categoria | conta | cliente
}
function erro(e) { $(REL_ALVO).innerHTML = `<div class="erro-box">⚠ ${esc(e.message || e)}</div>`; }
function vazioBloco(msg) { return `<div class="vazio"><div class="ic">${ic("inbox")}</div><div>${esc(msg)}</div></div>`; }
function skeleton(tipo) {
  if (tipo === "dash") return `<div class="grid cols-4">${"<div class='skel skel-kpi'></div>".repeat(4)}</div>
    <div class="grid cols-3" style="margin-top:16px"><div class="skel skel-chart span-2"></div><div class="skel skel-chart"></div></div>`;
  return `<div class="skel skel-row"></div>`.repeat(10);
}

// ===================================================== gráficos
function sparkline(vals, cor) {
  if (!vals || vals.length < 2) return "";
  const w = 116, h = 40, p = 3;
  const max = Math.max(...vals), min = Math.min(...vals, 0), rng = (max - min) || 1;
  const X = (i) => p + i * (w - 2 * p) / (vals.length - 1);
  const Y = (v) => h - p - ((v - min) / rng) * (h - 2 * p);
  const pts = vals.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  const area = `${X(0)},${h} ${pts} ${X(vals.length - 1)},${h}`;
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polygon points="${area}" fill="${cor}" opacity=".08"/><polyline points="${pts}" fill="none" stroke="${cor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

function graficoCombo(meses, { altura = 320, maxLabels = 16 } = {}) {
  if (!meses.length) return vazioBloco("Sem lançamentos no período selecionado.");
  const n = meses.length;
  const padL = 56, padR = 16, padT = 16, padB = 38;
  const grupoW = Math.max(26, Math.min(72, 820 / n));
  const W = padL + padR + n * grupoW, H = altura, plotH = H - padT - padB;
  const maxV = Math.max(1, ...meses.map((m) => Math.max(m.soma_receber, m.soma_pagar)));
  let acc = 0; const accs = meses.map((m) => (acc += m.saldo));
  const accMin = Math.min(0, ...accs), accMax = Math.max(0, ...accs), accRng = (accMax - accMin) || 1;
  const yBar = (v) => padT + plotH - (v / maxV) * plotH;
  const yAcc = (v) => padT + plotH - ((v - accMin) / accRng) * plotH;
  const cx = (i) => padL + i * grupoW + grupoW / 2;
  let grid = "";
  for (let k = 0; k <= 4; k++) { const val = maxV * k / 4, yy = yBar(val); grid += `<line class="grid-line" x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}"/><text class="axis-lbl" x="${padL - 8}" y="${yy + 3}" text-anchor="end">${moedaCurta(val)}</text>`; }
  const bw = Math.max(4, Math.min(13, (grupoW - 9) / 2));
  let bars = "", hits = "", labels = "";
  const step = Math.ceil(n / maxLabels);
  meses.forEach((m, i) => {
    const c = cx(i), xr = c - bw - 1, xp = c + 1;
    bars += `<rect class="bar bar-r" x="${xr.toFixed(1)}" y="${yBar(m.soma_receber).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0, plotH - (yBar(m.soma_receber) - padT)).toFixed(1)}" rx="2"/>`;
    bars += `<rect class="bar bar-p" x="${xp.toFixed(1)}" y="${yBar(m.soma_pagar).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0, plotH - (yBar(m.soma_pagar) - padT)).toFixed(1)}" rx="2"/>`;
    if (i % step === 0) labels += `<text class="axis-lbl" x="${c.toFixed(1)}" y="${H - padB + 16}" text-anchor="middle">${mesBR(m.chave)}</text>`;
    const id = tip(`<div class="tt-tit">${mesBR(m.chave)}</div>
      <div class="tt-row"><span class="k">Entradas</span><span>${moeda(m.soma_receber)}</span></div>
      <div class="tt-row"><span class="k">Saídas</span><span>${moeda(m.soma_pagar)}</span></div>
      <div class="tt-row"><span class="k">Saldo</span><span>${moeda(m.saldo)}</span></div>
      <div class="tt-row"><span class="k">Acumulado</span><span>${moeda(accs[i])}</span></div>`);
    hits += `<rect class="hit" data-tip="${id}" x="${(padL + i * grupoW).toFixed(1)}" y="${padT}" width="${grupoW.toFixed(1)}" height="${plotH}"/>`;
  });
  const linePts = accs.map((v, i) => `${cx(i).toFixed(1)},${yAcc(v).toFixed(1)}`).join(" ");
  const pts = accs.map((v, i) => `<circle class="pt-acc" cx="${cx(i).toFixed(1)}" cy="${yAcc(v).toFixed(1)}" r="2.6"/>`).join("");
  return `<div style="overflow-x:auto"><svg class="chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" preserveAspectRatio="xMinYMid meet">${grid}${bars}<polyline class="linha-acc" points="${linePts}"/>${pts}${hits}${labels}</svg></div>`;
}

function graficoDonut(segs) {
  segs = segs.filter((s) => s.valor > 0);
  const tot = segs.reduce((s, x) => s + x.valor, 0);
  const r = 62, cx = 80, cy = 80, C = 2 * Math.PI * r, sw = 22;
  let off = 0, arcs = "";
  if (tot > 0) segs.forEach((s) => { const len = s.valor / tot * C; arcs += `<circle r="${r}" cx="${cx}" cy="${cy}" fill="none" stroke="${s.cor}" stroke-width="${sw}" stroke-dasharray="${len.toFixed(2)} ${(C - len).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"/>`; off += len; });
  else arcs = `<circle r="${r}" cx="${cx}" cy="${cy}" fill="none" stroke="var(--surface-3)" stroke-width="${sw}"/>`;
  const svg = `<svg class="chart" width="160" height="160" viewBox="0 0 160 160">${arcs}<g class="donut-centro" text-anchor="middle"><text class="big" x="${cx}" y="${cy - 1}">${moedaCurta(tot)}</text><text class="sm" x="${cx}" y="${cy + 14}">total</text></g></svg>`;
  const leg = `<div class="legenda">` + segs.map((s) => `<div class="li"><span class="sw" style="background:${s.cor}"></span><span>${esc(s.label)}</span><span class="pct">${tot > 0 ? (s.valor / tot * 100).toFixed(0) : 0}%</span><span class="v">${moedaCurta(s.valor)}</span></div>`).join("") + `</div>`;
  return `<div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap"><div>${svg}</div><div style="flex:1;min-width:170px">${leg}</div></div>`;
}

function barrasH(itens, limite = 8) {
  if (!itens.length) return vazioBloco("Sem dados no período.");
  const top = itens.slice(0, limite);
  const max = Math.max(1, ...top.map((g) => g.soma_receber + g.soma_pagar));
  return top.map((g, i) => {
    const id = tip(`<div class="tt-tit">${esc(g.label || "—")}</div>
      <div class="tt-row"><span class="k">A receber</span><span>${moeda(g.soma_receber)}</span></div>
      <div class="tt-row"><span class="k">A pagar</span><span>${moeda(g.soma_pagar)}</span></div>
      <div class="tt-row"><span class="k">Saldo</span><span>${moeda(g.saldo)}</span></div>
      <div class="tt-row"><span class="k">Títulos</span><span>${g.n}</span></div>`);
    return `<div class="hbar-item" data-tip="${id}">
      <div class="hbar-topo"><span class="row-rank">${i + 1}</span><span class="hbar-nome">${esc(g.label || "—")}</span></div>
      <span class="hbar-val ${classeValor(g.saldo)}">${moeda(g.saldo)}</span>
      <div class="hbar-track"><div class="hbar-fill r" style="width:${(g.soma_receber / max * 100).toFixed(1)}%"></div><div class="hbar-fill p" style="width:${(g.soma_pagar / max * 100).toFixed(1)}%"></div></div>
      <div class="hbar-sub"><span class="pos">▲ ${moedaCurta(g.soma_receber)}</span><span class="neg">▼ ${moedaCurta(g.soma_pagar)}</span></div>
    </div>`;
  }).join("");
}

// ===================================================== KPI helpers
function animarMoeda(el, alvo) {
  const [f, s] = unidade(alvo), dur = 750, t0 = performance.now();
  const fmt = (v) => f === 1 ? fmtBRL.format(v) : "R$ " + (v / f).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + s;
  function passo(t) { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); el.textContent = fmt(alvo * e); if (k < 1) requestAnimationFrame(passo); }
  requestAnimationFrame(passo);
}
function janela12(meses, temPeriodo) {
  const ord = [...meses].sort((a, b) => String(a.chave).localeCompare(String(b.chave)));
  if (temPeriodo || ord.length <= 18) return ord;
  const now = new Date(), fim = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const d = new Date(now.getFullYear(), now.getMonth() - 11, 1);
  const ini = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  const jan = ord.filter((m) => m.chave >= ini && m.chave <= fim);
  return jan.length ? jan : ord.slice(-12);
}

// ===================================================== VISÃO GERAL
async function renderDashboard() {
  $(REL_ALVO).innerHTML = skeleton("dash");
  try {
    const j = await api("/api/dashboard");
    const r = j.resumo;
    let recAberto = 0, pagAberto = 0, atrasado = 0, recOk = 0, pagOk = 0, realizado = 0, abertoGeral = 0;
    for (const s of r.por_status) {
      const up = (s.status || "").toUpperCase(), ok = STATUS_OK.has(up), atr = up.includes("ATRAS") || up.includes("VENCID");
      if (s.tipo === "receber") { ok ? (recOk += s.soma) : (recAberto += s.soma); } else { ok ? (pagOk += s.soma) : (pagAberto += s.soma); }
      if (atr) atrasado += s.soma; else if (ok) realizado += s.soma; else abertoGeral += s.soma;
    }
    const temPeriodo = !!($("#fDe").value || $("#fAte").value);
    const meses = janela12(j.por_mes, temPeriodo);
    const sRec = meses.map((m) => m.soma_receber), sPag = meses.map((m) => m.soma_pagar);
    let a = 0; const sAcc = meses.map((m) => (a += m.saldo));

    const kpi = (id, rotulo, icone, cls, valor, nota, spark) => `
      <div class="kpi">
        <div class="topo"><span class="rotulo">${rotulo}</span><span class="ic ${cls}">${ic(icone)}</span></div>
        <div class="valor ${cls === "verde" ? "pos" : cls === "vermelho" ? "neg" : classeValor(valor)}" id="${id}">${moedaCurta(valor)}</div>
        <div class="nota">${nota}</div>${spark}
      </div>`;

    const cards = `<div class="grid cols-4">
      ${kpi("k1", "A Receber", "receber", "verde", r.soma_receber, `Recebido <b class="pos">${moedaCurta(recOk)}</b> · Aberto <b>${moedaCurta(recAberto)}</b>`, sparkline(sRec, "var(--green)"))}
      ${kpi("k2", "A Pagar", "pagar", "vermelho", r.soma_pagar, `Pago <b class="neg">${moedaCurta(pagOk)}</b> · Aberto <b>${moedaCurta(pagAberto)}</b>`, sparkline(sPag, "var(--red)"))}
      ${kpi("k3", "Saldo (Receber − Pagar)", "saldo", "", r.saldo, `${r.total_registros.toLocaleString("pt-BR")} títulos no filtro`, sparkline(sAcc, "var(--ink)"))}
      ${kpi("k4", "Em aberto (líquido)", "clock", "", recAberto - pagAberto, `Atrasado: <b class="neg">${moedaCurta(atrasado)}</b>`, "")}
    </div>`;

    const donut = graficoDonut([
      { label: "Realizado", valor: realizado, cor: "var(--green)" },
      { label: "Em aberto (a vencer)", valor: abertoGeral, cor: "var(--c5)" },
      { label: "Atrasado", valor: atrasado, cor: "var(--red)" },
    ]);

    const legendaFluxo = `<span class="sub">
      <span style="color:var(--green-ink)">■ Entradas</span> &nbsp;
      <span style="color:var(--red-ink)">■ Saídas</span> &nbsp;
      <span>— Saldo acumulado</span></span>`;

    $(REL_ALVO).innerHTML = cards +
      `<div class="grid cols-3" style="margin-top:16px">
        <div class="panel span-2">
          <div class="panel-head"><h3>Fluxo de Caixa</h3>${legendaFluxo}</div>
          <div class="panel-body">${graficoCombo(meses)}${!temPeriodo && j.por_mes.length > 18 ? '<div class="sub" style="margin-top:6px;color:var(--muted)">Mostrando os últimos 12 meses — use o filtro de período para ampliar.</div>' : ""}</div>
        </div>
        <div class="panel">
          <div class="panel-head"><h3>Situação dos títulos</h3></div>
          <div class="panel-body">${donut}</div>
        </div>
      </div>
      <div class="grid cols-3" style="margin-top:16px">
        <div class="panel span-2"><div class="panel-head"><h3>Top Contas Bancárias</h3><span class="sub">saldo (receber − pagar)</span></div><div class="panel-body">${barrasH(j.por_conta, 7)}</div></div>
        <div class="panel"><div class="panel-head"><h3>Top Categorias</h3></div><div class="panel-body">${barrasH(j.por_categoria, 7)}</div></div>
      </div>
      <div class="grid cols-3" style="margin-top:16px">
        <div class="panel span-2"><div class="panel-head"><h3>Por Empresa</h3><span class="sub">saldo (receber − pagar)</span></div><div class="panel-body">${barrasH(j.por_empresa, 8)}</div></div>
        <div class="panel"></div>
      </div>`;

    animarMoeda($("#k1"), r.soma_receber); animarMoeda($("#k2"), r.soma_pagar);
    animarMoeda($("#k3"), r.saldo); animarMoeda($("#k4"), recAberto - pagAberto);
  } catch (e) { erro(e); }
}

// ===================================================== TÍTULOS
async function renderTitulos() {
  $(REL_ALVO).innerHTML = skeleton();
  try {
    const t = state.titulos;
    const j = await api("/api/titulos", { pagina: t.pagina, por_pagina: t.por_pagina, ordenar: t.ordenar, dir: t.dir });
    const seta = (c) => t.ordenar === c ? `<span class="ind">${t.dir === "desc" ? "▼" : "▲"}</span>` : "";
    const cols = [["empresa", "Empresa"], ["conta", "Conta"], ["tipo", "Tipo"], ["cliente", "Cliente/Fornecedor"], ["categoria", "Categoria"], [null, "Documento"], ["vencimento", "Vencimento"], ["valor", "Valor"], ["status", "Status"]];
    const cab = cols.map(([k, nome]) => k ? `<th class="ord${k === "valor" ? " num" : ""}" data-ord="${k}">${nome}${seta(k)}</th>` : `<th>${nome}</th>`).join("");
    const corpo = j.linhas.length ? j.linhas.map((l) => `<tr>
        <td class="cinza">${esc(l.empresa_fantasia || l.empresa_razao || l.empresa_id)}</td>
        <td>${esc(l.conta_nome || "—")}</td>
        <td><span class="tag-tipo ${l.tipo}">${l.tipo}</span></td>
        <td class="forte">${esc(l.cliente_razao || l.cliente_fantasia || "—")}</td>
        <td class="cinza">${esc(l.categoria_nome || l.cod_categoria || "—")}</td>
        <td class="cinza">${esc(l.numero_documento || "")}${l.numero_parcela ? ` <small>(${esc(l.numero_parcela)})</small>` : ""}</td>
        <td>${dataBR(l.data_vencimento)}</td>
        <td class="num dinheiro ${l.tipo === "pagar" ? "neg" : "pos"}">${moeda(l.valor)}</td>
        <td>${badgeStatus(l.status)}</td></tr>`).join("") : `<tr><td colspan="9">${vazioBloco("Nenhum título encontrado com esses filtros.")}</td></tr>`;
    const r = j.resumo;
    const rodape = `<tfoot><tr>
      <td colspan="5">TOTAIS · ${r.total_registros.toLocaleString("pt-BR")} títulos</td>
      <td colspan="2" style="text-align:right">Receber <span class="pos">${moedaCurta(r.soma_receber)}</span> · Pagar <span class="neg">${moedaCurta(r.soma_pagar)}</span></td>
      <td class="num ${classeValor(r.saldo)}">${moeda(r.saldo)}</td><td></td></tr></tfoot>`;
    $(REL_ALVO).innerHTML = `<div class="tabela-wrap"><table><thead><tr>${cab}</tr></thead><tbody>${corpo}</tbody>${rodape}</table></div>
      <div class="paginacao">
        <button class="btn ghost sm" data-pg="prim" ${j.pagina <= 1 ? "disabled" : ""}>« Início</button>
        <button class="btn ghost sm" data-pg="prev" ${j.pagina <= 1 ? "disabled" : ""}>‹ Anterior</button>
        <span>Página <b>${j.pagina}</b> de <b>${j.total_paginas}</b></span>
        <button class="btn ghost sm" data-pg="next" ${j.pagina >= j.total_paginas ? "disabled" : ""}>Próxima ›</button>
        <select id="porPagina">${[50, 100, 250, 500, 1000].map((n) => `<option value="${n}" ${t.por_pagina === n ? "selected" : ""}>${n} por página</option>`).join("")}</select>
      </div>`;
    $("#porPagina").addEventListener("change", (e) => { t.por_pagina = +e.target.value; t.pagina = 1; renderTitulos(); });
  } catch (e) { erro(e); }
}

// ===================================================== FLUXO DE CAIXA
async function renderFluxo() {
  $(REL_ALVO).innerHTML = skeleton();
  try {
    const j = await api("/api/agrupado", { por: "mes" });
    const meses = (j.grupos || []).sort((a, b) => String(a.chave).localeCompare(String(b.chave)));
    if (!meses.length) { $(REL_ALVO).innerHTML = `<div class="panel"><div class="panel-body">${vazioBloco("Sem lançamentos no período.")}</div></div>`; return; }
    let acc = 0; const linhas = meses.map((m) => { acc += m.saldo; return `<tr>
        <td class="forte">${mesBR(m.chave)}</td><td class="num">${m.n.toLocaleString("pt-BR")}</td>
        <td class="num dinheiro pos">${moeda(m.soma_receber)}</td><td class="num dinheiro neg">${moeda(m.soma_pagar)}</td>
        <td class="num dinheiro ${classeValor(m.saldo)}">${moeda(m.saldo)}</td><td class="num dinheiro ${classeValor(acc)}">${moeda(acc)}</td></tr>`; }).join("");
    const totR = meses.reduce((s, m) => s + m.soma_receber, 0), totP = meses.reduce((s, m) => s + m.soma_pagar, 0);
    $(REL_ALVO).innerHTML = `
      <div class="panel"><div class="panel-head"><h3>Entradas × Saídas por mês</h3>
        <span class="sub"><span style="color:var(--green-ink)">■ Entradas</span> <span style="color:var(--red-ink)">■ Saídas</span> — Acumulado</span></div>
        <div class="panel-body">${graficoCombo(meses, { altura: 340 })}</div></div>
      <div class="tabela-wrap" style="margin-top:16px"><table>
        <thead><tr><th>Mês</th><th class="num">Qtd</th><th class="num">Entradas</th><th class="num">Saídas</th><th class="num">Saldo do mês</th><th class="num">Acumulado</th></tr></thead>
        <tbody>${linhas}</tbody>
        <tfoot><tr><td>TOTAL</td><td></td><td class="num pos">${moeda(totR)}</td><td class="num neg">${moeda(totP)}</td><td class="num ${classeValor(totR - totP)}">${moeda(totR - totP)}</td><td></td></tr></tfoot>
      </table></div>`;
  } catch (e) { erro(e); }
}

// ===================================================== AGRUPADO (categoria/conta/cliente)
async function renderAgrupado(por) {
  $(REL_ALVO).innerHTML = skeleton();
  const colNome = { categoria: "Categoria", conta: "Conta Bancária", cliente: "Cliente/Fornecedor", departamento: "Departamento" };
  try {
    const j = await api("/api/agrupado", { por });
    const grupos = j.grupos || [];
    if (!grupos.length) { $(REL_ALVO).innerHTML = `<div class="panel"><div class="panel-body">${vazioBloco("Sem dados no filtro.")}</div></div>`; return; }
    const totR = grupos.reduce((s, g) => s + g.soma_receber, 0), totP = grupos.reduce((s, g) => s + g.soma_pagar, 0), totN = grupos.reduce((s, g) => s + g.n, 0);
    const linhas = grupos.map((g, i) => `<tr>
        <td class="row-rank">${i + 1}</td><td class="forte">${esc(g.label || "—")}</td><td class="num">${g.n.toLocaleString("pt-BR")}</td>
        <td class="num dinheiro pos">${moeda(g.soma_receber)}</td><td class="num dinheiro neg">${moeda(g.soma_pagar)}</td>
        <td class="num dinheiro ${classeValor(g.saldo)}">${moeda(g.saldo)}</td></tr>`).join("");
    $(REL_ALVO).innerHTML = `
      <div class="panel"><div class="panel-head"><h3>Ranking — ${colNome[por]}</h3><span class="sub">top ${Math.min(10, grupos.length)} por movimentação</span></div>
        <div class="panel-body">${barrasH(grupos, 10)}</div></div>
      <div class="tabela-wrap" style="margin-top:16px"><table>
        <thead><tr><th>#</th><th>${colNome[por]}</th><th class="num">Qtd</th><th class="num">A Receber</th><th class="num">A Pagar</th><th class="num">Saldo</th></tr></thead>
        <tbody>${linhas}</tbody>
        <tfoot><tr><td></td><td>TOTAL · ${grupos.length} grupos</td><td class="num">${totN.toLocaleString("pt-BR")}</td>
          <td class="num pos">${moeda(totR)}</td><td class="num neg">${moeda(totP)}</td><td class="num ${classeValor(totR - totP)}">${moeda(totR - totP)}</td></tr></tfoot>
      </table></div>`;
  } catch (e) { erro(e); }
}

// ===================================================== DRE
async function renderDre() {
  $(REL_ALVO).innerHTML = skeleton();
  try {
    const extra = {}; let nota = "";
    if (!$("#fDe").value && !$("#fAte").value) {
      const a = new Date().getFullYear();
      extra.de = a + "-01-01"; extra.ate = a + "-12-31";
      nota = `<div class="sub" style="margin-bottom:10px;color:var(--muted)">Mostrando ${a} (padrão). Ajuste o filtro de <b>Período</b> para outro intervalo.</div>`;
    }
    const d = await api("/api/dre", extra);
    const meses = d.meses || [];
    if (!meses.length) { $(REL_ALVO).innerHTML = `<div class="panel"><div class="panel-body">${vazioBloco("Sem dados no período selecionado.")}</div></div>`; return; }
    const resultadoTotal = d.soma_receitas - d.soma_despesas;
    const cab = `<th class="dre-cat">Conta</th>` + meses.map((m) => `<th class="num">${mesBR(m)}</th>`).join("") + `<th class="num">Total</th>`;
    const cel = (v, cls) => `<td class="num dinheiro ${cls}">${v ? moedaCurta(v) : "–"}</td>`;
    const linha = (l, cls) => `<tr><td class="dre-cat" title="${esc(l.categoria)}">${esc(l.categoria)}</td>${meses.map((m) => cel(l.valores[m], cls)).join("")}<td class="num dinheiro ${cls}" style="font-weight:700">${moedaCurta(l.total)}</td></tr>`;
    const totalRow = (lbl, mapa, cls) => `<tr class="dre-total"><td class="dre-cat">${lbl}</td>${meses.map((m) => `<td class="num ${cls}">${moedaCurta(mapa[m] || 0)}</td>`).join("")}<td class="num ${cls}">${moedaCurta(Object.values(mapa).reduce((a, b) => a + b, 0))}</td></tr>`;
    const resRow = `<tr class="dre-resultado"><td class="dre-cat">RESULTADO</td>${meses.map((m) => { const v = d.resultado[m] || 0; return `<td class="num ${classeValor(v)}">${moedaCurta(v)}</td>`; }).join("")}<td class="num ${classeValor(resultadoTotal)}">${moedaCurta(resultadoTotal)}</td></tr>`;
    $(REL_ALVO).innerHTML = nota + `
      <div class="grid cols-3" style="margin-bottom:16px">
        <div class="kpi"><div class="rotulo">Receitas (entradas)</div><div class="valor pos" style="font-size:23px;margin-top:8px">${moeda(d.soma_receitas)}</div></div>
        <div class="kpi"><div class="rotulo">Despesas (saídas)</div><div class="valor neg" style="font-size:23px;margin-top:8px">${moeda(d.soma_despesas)}</div></div>
        <div class="kpi"><div class="rotulo">Resultado</div><div class="valor ${classeValor(resultadoTotal)}" style="font-size:23px;margin-top:8px">${moeda(resultadoTotal)}</div></div>
      </div>
      <div class="tabela-wrap"><table class="dre"><thead><tr>${cab}</tr></thead><tbody>
        <tr class="dre-sec"><td class="dre-cat">RECEITAS</td><td colspan="${meses.length + 1}"></td></tr>
        ${d.receitas.map((l) => linha(l, "pos")).join("")}
        ${totalRow("Total de Receitas", d.total_receitas, "pos")}
        <tr class="dre-sec"><td class="dre-cat">DESPESAS</td><td colspan="${meses.length + 1}"></td></tr>
        ${d.despesas.map((l) => linha(l, "neg")).join("")}
        ${totalRow("Total de Despesas", d.total_despesas, "neg")}
        ${resRow}
      </tbody></table></div>`;
  } catch (e) { erro(e); }
}

// ===================================================== PREVISTO × REALIZADO (orçamento)
const MESES_NOMES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
function somaPeriodo(arr, mes) {   // mes: 0 = ano todo, 1..12 = um mês
  if (!mes) return arr.reduce((s, v) => s + v, 0);
  return arr[mes - 1] || 0;
}
async function renderOrcado() {
  $(REL_ALVO).innerHTML = skeleton("dash");
  try {
    if (!state.orcAno) state.orcAno = new Date().getFullYear();
    if (state.orcMes == null) state.orcMes = 0;
    const j = await api("/api/orcado", { ano: state.orcAno });
    const anoAtual = new Date().getFullYear();
    const anos = [...new Set([...(j.anos || []), anoAtual - 1, anoAtual])].sort();
    const mes = state.orcMes;
    const rotPeriodo = mes ? `${MESES_NOMES[mes - 1]}/${state.orcAno}` : `Ano de ${state.orcAno}`;

    const controles = `<div class="apagar-head" style="margin-bottom:16px;display:flex;gap:12px;flex-wrap:wrap;align-items:center">
      <div class="segmented">${anos.map((a) => `<button data-oano="${a}" class="${a === state.orcAno ? "ativa" : ""}">${a}</button>`).join("")}</div>
      <div class="segmented">${["Ano"].concat(MESES_NOMES).map((n, i) => `<button data-omes="${i}" class="${i === mes ? "ativa" : ""}">${n}</button>`).join("")}</div>
    </div>`;

    const secoes = [["Receitas", j.receitas || [], true], ["Despesas", j.despesas || [], false]];
    const tot = {};
    for (const [nome, itens] of secoes.map((s) => [s[0], s[1]])) {
      tot[nome] = {
        p: itens.reduce((s, i) => s + somaPeriodo(i.previsto, mes), 0),
        r: itens.reduce((s, i) => s + somaPeriodo(i.realizado, mes), 0),
      };
    }
    const pct = (r, p) => p > 0 ? (r / p * 100) : null;
    const pctTxt = (r, p) => { const x = pct(r, p); return x == null ? "—" : x.toFixed(0) + "%"; };

    const kpis = `<div class="grid cols-3" style="margin-bottom:16px">
      <div class="kpi"><div class="topo"><span class="rotulo">Receitas — Previsto</span><span class="ic verde">${ic("receber")}</span></div>
        <div class="valor pos">${moedaCurta(tot.Receitas.p)}</div>
        <div class="nota">Realizado <b class="pos">${moedaCurta(tot.Receitas.r)}</b> · atingido <b>${pctTxt(tot.Receitas.r, tot.Receitas.p)}</b></div></div>
      <div class="kpi"><div class="topo"><span class="rotulo">Despesas — Previsto</span><span class="ic vermelho">${ic("pagar")}</span></div>
        <div class="valor neg">${moedaCurta(tot.Despesas.p)}</div>
        <div class="nota">Realizado <b class="neg">${moedaCurta(tot.Despesas.r)}</b> · consumido <b>${pctTxt(tot.Despesas.r, tot.Despesas.p)}</b></div></div>
      <div class="kpi"><div class="topo"><span class="rotulo">Resultado (${esc(rotPeriodo)})</span><span class="ic">${ic("saldo")}</span></div>
        <div class="valor ${classeValor(tot.Receitas.p - tot.Despesas.p)}">${moedaCurta(tot.Receitas.p - tot.Despesas.p)}</div>
        <div class="nota">Realizado <b class="${classeValor(tot.Receitas.r - tot.Despesas.r)}">${moedaCurta(tot.Receitas.r - tot.Despesas.r)}</b></div></div>
    </div>`;

    const tabela = (nome, itens, ehReceita) => {
      const linhas = itens.map((i) => ({ cat: i.categoria, p: somaPeriodo(i.previsto, mes), r: somaPeriodo(i.realizado, mes) }))
        .filter((l) => l.p || l.r);
      if (!linhas.length) return `<div class="panel" style="margin-bottom:16px"><div class="panel-head"><h3>${nome}</h3></div>
        <div class="panel-body">${vazioBloco("Sem orçamento nem lançamentos em " + rotPeriodo + ".")}</div></div>`;
      const corpo = linhas.map((l) => {
        const delta = l.r - l.p;
        const favoravel = ehReceita ? l.r >= l.p : l.r <= l.p;
        const x = pct(l.r, l.p);
        const barra = `<div class="hbar-track" style="min-width:90px"><div class="hbar-fill ${favoravel ? "r" : "p"}" style="width:${x == null ? (l.r ? 100 : 0) : Math.min(100, x).toFixed(0)}%"></div></div>`;
        return `<tr>
          <td class="forte">${esc(l.cat)}</td>
          <td class="num dinheiro">${moeda(l.p)}</td>
          <td class="num dinheiro ${ehReceita ? "pos" : "neg"}">${moeda(l.r)}</td>
          <td class="num dinheiro ${favoravel ? "pos" : "neg"}">${(delta >= 0 ? "+" : "") + moedaCurta(delta)}</td>
          <td class="num">${x == null ? "—" : x.toFixed(0) + "%"}</td>
          <td>${barra}</td></tr>`;
      }).join("");
      const t = { p: linhas.reduce((s, l) => s + l.p, 0), r: linhas.reduce((s, l) => s + l.r, 0) };
      return `<div class="panel" style="margin-bottom:16px"><div class="panel-head"><h3>${nome}</h3><span class="sub">${rotPeriodo} · ${linhas.length} categoria(s)</span></div>
        <div class="panel-body"><div class="tabela-wrap"><table>
          <thead><tr><th>Categoria</th><th class="num">Previsto</th><th class="num">Realizado</th><th class="num">Δ</th><th class="num">%</th><th style="width:110px">Progresso</th></tr></thead>
          <tbody>${corpo}</tbody>
          <tfoot><tr><td>TOTAL</td><td class="num">${moeda(t.p)}</td><td class="num ${ehReceita ? "pos" : "neg"}">${moeda(t.r)}</td>
            <td class="num">${moedaCurta(t.r - t.p)}</td><td class="num">${pctTxt(t.r, t.p)}</td><td></td></tr></tfoot>
        </table></div></div></div>`;
    };

    const temAlgo = (j.receitas || []).length || (j.despesas || []).length;
    const aviso = temAlgo ? "" : `<div class="panel"><div class="panel-body">${vazioBloco(
      "Nenhum orçamento encontrado para " + state.orcAno + ". Cadastre o Orçamento de Caixa no OMIE (Finanças → Orçamento) e clique em Sincronizar.")}</div></div>`;

    $(REL_ALVO).innerHTML = controles + kpis + tabela("Receitas", j.receitas || [], true) + tabela("Despesas", j.despesas || [], false) + aviso;
    $$("[data-oano]").forEach((b) => b.addEventListener("click", () => { state.orcAno = +b.dataset.oano; renderOrcado(); }));
    $$("[data-omes]").forEach((b) => b.addEventListener("click", () => { state.orcMes = +b.dataset.omes; renderOrcado(); }));
  } catch (e) { erro(e); }
}

// ===================================================== ADMINISTRAÇÃO
async function renderAdmin() {
  $(REL_ALVO).innerHTML = skeleton();
  try {
    const r = await fetch("/api/admin/dados");
    const d = await r.json();
    if (!r.ok || d.erro) throw new Error(d.erro || "Sem acesso");
    state.admin = d;
    desenharAdmin();
  } catch (e) { erro(e); }
}
function nomeEmpresa(eid) {
  const e = state.empresas.find((x) => x.empresa_id === eid);
  return e ? (e.razao_social || e.nome || eid) : eid;
}
function desenharAdmin() {
  const d = state.admin;
  const linhasE = d.empresas.map((e) => `<tr>
      <td class="forte">${esc(e.nome)}</td><td class="cinza">${esc(e.empresa_id)}</td>
      <td class="cinza">${esc(e.app_key)}</td><td class="cinza">${esc(e.razao_social || "—")}</td>
      <td class="cinza">${esc(e.ultimo_sync || "nunca")}</td><td class="num">${(e.qtd_titulos || 0).toLocaleString("pt-BR")}</td>
      <td style="white-space:nowrap"><button class="btn ghost sm" data-ede="${esc(e.empresa_id)}">Editar</button> <button class="btn ghost sm" data-exe="${esc(e.empresa_id)}">Excluir</button></td>
    </tr>`).join("") || `<tr><td colspan="7">${vazioBloco("Nenhuma conta OMIE cadastrada. Clique em “Nova conta OMIE”.")}</td></tr>`;
  const rotEmp = (u) => {
    if (u.papel === "admin") return "todas (admin)";
    const emp = u.empresas || [];
    if (!emp.length) return "todas";
    return emp.length <= 3 ? emp.map(nomeEmpresa).map(esc).join(", ") : emp.length + " empresas";
  };
  const linhasU = d.usuarios.map((u) => `<tr>
      <td class="forte">${esc(u.nome || "")}</td><td class="cinza">${esc(u.login)}</td>
      <td><span class="badge ${u.papel === "admin" ? "ok" : "aberto"}">${u.papel === "admin" ? "admin" : "usuário"}</span></td>
      <td class="cinza">${rotEmp(u)}</td>
      <td>${u.ativo ? '<span class="badge ok">ativo</span>' : '<span class="badge alerta">inativo</span>'}</td>
      <td class="cinza">${esc(u.ultimo_acesso || "—")}</td>
      <td style="white-space:nowrap"><button class="btn ghost sm" data-edu="${u.id}">Editar</button> <button class="btn ghost sm" data-exu="${u.id}">Excluir</button></td>
    </tr>`).join("");
  $(REL_ALVO).innerHTML = `
    <div class="panel" style="margin-bottom:16px">
      <div class="panel-head"><h3>Contas OMIE (credenciais)</h3><button class="btn sm" id="novaEmp">+ Nova conta OMIE</button></div>
      <div class="panel-body"><div id="formEmp"></div>
        <div class="tabela-wrap"><table><thead><tr><th>Nome</th><th>Identificador</th><th>App Key</th><th>Razão social</th><th>Última sync</th><th class="num">Títulos</th><th></th></tr></thead><tbody>${linhasE}</tbody></table></div></div>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>Usuários</h3><button class="btn sm" id="novoUser">+ Novo usuário</button></div>
      <div class="panel-body"><div id="formUser"></div>
        <div class="tabela-wrap"><table><thead><tr><th>Nome</th><th>Login</th><th>Papel</th><th>Empresas</th><th>Status</th><th>Último acesso</th><th></th></tr></thead><tbody>${linhasU}</tbody></table></div></div>
    </div>`;
  $("#novoUser").addEventListener("click", () => formUsuario(null));
  $("#novaEmp").addEventListener("click", () => formEmpresa(null));
  $$("[data-edu]").forEach((b) => b.addEventListener("click", () => formUsuario(d.usuarios.find((u) => String(u.id) === b.dataset.edu))));
  $$("[data-exu]").forEach((b) => b.addEventListener("click", () => excluirUsuario(b.dataset.exu)));
  $$("[data-ede]").forEach((b) => b.addEventListener("click", () => formEmpresa(d.empresas.find((e) => e.empresa_id === b.dataset.ede))));
  $$("[data-exe]").forEach((b) => b.addEventListener("click", () => excluirEmpresa(b.dataset.exe)));
}
function formUsuario(u) {
  const marcadas = new Set(u && u.empresas ? u.empresas : []);
  const fontes = (state.admin && state.admin.empresas_relatorio) || state.empresas.map((e) => e.empresa_id);
  const chk = (eid) => `<label class="chk"><input type="checkbox" class="uemp" value="${esc(eid)}" ${marcadas.has(eid) ? "checked" : ""}> ${esc(nomeEmpresa(eid))}</label>`;
  $("#formUser").innerHTML = `<div class="form-card">
    <div class="form-grid">
      <div class="campo"><label>Nome</label><input id="uNome" type="text" value="${u ? esc(u.nome || "") : ""}"></div>
      <div class="campo"><label>Login</label><input id="uLogin" type="text" value="${u ? esc(u.login) : ""}" ${u ? "disabled" : ""}></div>
      <div class="campo"><label>Senha ${u ? "(em branco = manter)" : ""}</label><input id="uSenha" type="password" placeholder="${u ? "••••••" : "mínimo 6 caracteres"}"></div>
      <div class="campo"><label>Papel</label><select id="uPapel">
        <option value="user">Usuário (vê relatórios)</option>
        <option value="admin">Admin (gerencia tudo)</option></select></div>
      <div class="campo"><label>Status</label><select id="uAtivo"><option value="1">Ativo</option><option value="0">Inativo</option></select></div>
    </div>
    <div id="uAccWrap"><label class="lbl">Empresas visíveis (nenhuma marcada = todas)</label>
      <div class="chks" style="max-height:180px;overflow:auto">${fontes.map(chk).join("")}</div></div>
    <div class="form-acoes"><button class="btn" id="uSalvar">Salvar</button><button class="btn ghost" id="uCancelar">Cancelar</button><span class="erro-inline" id="uMsg"></span></div>
  </div>`;
  if (u) { $("#uPapel").value = u.papel === "admin" ? "admin" : "user"; $("#uAtivo").value = u.ativo ? "1" : "0"; }
  const toggle = () => { $("#uAccWrap").style.display = $("#uPapel").value === "admin" ? "none" : ""; };
  toggle(); $("#uPapel").addEventListener("change", toggle);
  $("#uCancelar").addEventListener("click", () => { $("#formUser").innerHTML = ""; });
  $("#uSalvar").addEventListener("click", async () => {
    const payload = { id: u ? u.id : undefined, nome: $("#uNome").value.trim(), login: u ? u.login : $("#uLogin").value.trim(),
      senha: $("#uSenha").value, papel: $("#uPapel").value, ativo: +$("#uAtivo").value,
      empresas: $$("#uAccWrap input:checked").map((i) => i.value) };
    const j = await postJSON("/api/admin/usuario/salvar", payload, "#uMsg");
    if (j) { renderAdmin(); }
  });
}
function formEmpresa(e) {
  $("#formEmp").innerHTML = `<div class="form-card">
    <div class="form-grid">
      <div class="campo"><label>Identificador (sem espaços)</label><input id="eId" value="${e ? esc(e.empresa_id) : ""}" ${e ? "disabled" : ""} placeholder="ex.: holding"></div>
      <div class="campo"><label>Nome da empresa</label><input id="eNome" value="${e ? esc(e.nome) : ""}" placeholder="Nome amigável"></div>
      <div class="campo"><label>App Key (OMIE)</label><input id="eKey" value="${e ? esc(e.app_key) : ""}"></div>
      <div class="campo"><label>App Secret (OMIE) ${e ? "(em branco = manter)" : ""}</label><input id="eSecret" type="password" placeholder="${e ? "•••••• (mantém o atual)" : "app_secret"}"></div>
    </div>
    <div class="form-acoes"><button class="btn" id="eSalvar">Salvar</button><button class="btn ghost" id="eCancelar">Cancelar</button><span class="erro-inline" id="eMsg"></span></div>
  </div>`;
  $("#eCancelar").addEventListener("click", () => { $("#formEmp").innerHTML = ""; });
  $("#eSalvar").addEventListener("click", async () => {
    const payload = { id: e ? e.empresa_id : $("#eId").value.trim(), nome: $("#eNome").value.trim(), app_key: $("#eKey").value.trim(), app_secret: $("#eSecret").value };
    const j = await postJSON("/api/admin/empresa/salvar", payload, "#eMsg");
    if (j) { await carregarEmpresas(); renderAdmin(); }
  });
}
async function excluirUsuario(id) {
  if (!confirm("Excluir este usuário? Esta ação não pode ser desfeita.")) return;
  const j = await postJSON("/api/admin/usuario/excluir", { id: +id });
  if (j) renderAdmin();
}
async function excluirEmpresa(id) {
  if (!confirm("Excluir esta conta OMIE? Os relatórios dela deixarão de ser atualizados.")) return;
  const j = await postJSON("/api/admin/empresa/excluir", { id });
  if (j) { await carregarEmpresas(); renderAdmin(); }
}

// ===================================================== empresas / nav / sync
async function carregarEmpresas() {
  const j = await api("/api/empresas");
  const conhecidas = new Map();
  for (const c of j.config || []) conhecidas.set(c.id, { empresa_id: c.id, nome: c.nome, razao_social: c.nome });
  for (const e of j.empresas || []) conhecidas.set(e.empresa_id, { ...conhecidas.get(e.empresa_id), ...e });
  state.empresas = [...conhecidas.values()].sort((a, b) => (a.razao_social || a.nome || "").localeCompare(b.razao_social || b.nome || ""));
  if (mEmp) mEmp.setOptions(state.empresas.map((e) => ({ value: e.empresa_id, label: e.razao_social || e.nome || e.empresa_id })));
  atualizarSyncCard();
}
function iniciais(nome) { return (nome || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase(); }
async function carregarFiltros() {
  try {
    const j = await api("/api/filtros", { empresas: mEmp ? mEmp.getSelected().join(",") : "" });
    mC.setOptions((j.contas || []).map((c) => ({ value: c.ncodcc, label: c.descricao || `Conta ${c.ncodcc}` })));
    mS.setOptions((j.status || []).map((s) => ({ value: s, label: s })));
    mCat.setOptions((j.categorias || []).map((c) => ({ value: c.codigo, label: `${c.codigo} — ${c.descricao || ""}` })));
  } catch (e) { /* sem dados ainda */ }
}
function desenharNav() {
  const btn = (v) => `<button data-view="${v.id}" class="${v.id === state.view ? "ativa" : ""}">${ic(v.ico)}<span>${v.nome}</span></button>`;
  let html = VIEWS.map(btn).join("");
  if (state.usuario.papel === "admin") html += `<div class="grupo-label">Gestão</div>` + btn({ id: "admin", nome: "Administração", ico: "shield" });
  $("#nav").innerHTML = html;
  $$("#nav button").forEach((b) => b.addEventListener("click", () => { state.view = b.dataset.view; state.titulos.pagina = 1; $("#sidebar").classList.remove("aberta"); render(); }));
}
function desenharUsuario() {
  const foot = document.querySelector(".side-foot");
  let bloco = $("#usuarioBloco");
  if (!bloco) { bloco = document.createElement("div"); bloco.id = "usuarioBloco"; foot.prepend(bloco); }
  const u = state.usuario || {};
  bloco.innerHTML = `<div class="user-row">
    <div class="user-av">${esc(iniciais(u.nome || u.login))}</div>
    <div class="user-meta"><div class="user-nome">${esc(u.nome || u.login)}</div><div class="user-papel">${u.papel === "admin" ? "Administrador" : "Usuário"}</div></div>
    <button class="icon-btn" id="btnLogout" title="Sair">${ic("logout")}</button></div>`;
  $("#btnLogout").addEventListener("click", sair);
}
async function sair() { try { await fetch("/api/logout", { method: "POST" }); } catch (e) {} window.location = "/login"; }
function atualizarSyncCard() {
  const comSync = state.empresas.filter((e) => e.ultimo_sync);
  if (!comSync.length) { $("#syncCard").innerHTML = "Dados não sincronizados.<br>Clique em <b>Sincronizar</b>."; return; }
  const ult = comSync.map((e) => e.ultimo_sync).sort().pop();
  const tot = state.empresas.reduce((s, e) => s + (e.qtd_titulos || 0), 0);
  $("#syncCard").innerHTML = `<span class="dot"></span><b>Sincronizado</b><br>${esc(ult)}<br>${tot.toLocaleString("pt-BR")} títulos · ${comSync.length} empresa(s)`;
}
async function dispararSync() {
  const r = await fetch("/api/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
  const j = await r.json();
  if (!j.ok && r.status === 409) { alert(j.mensagem); return; }
  $("#btnSync").disabled = true; pollSync();
}
function pollSync() {
  clearTimeout(state.pollTimer);
  const tick = async () => {
    let s; try { s = await (await fetch("/api/sync/status")).json(); } catch { state.pollTimer = setTimeout(tick, 2000); return; }
    const barra = $("#barraSync");
    if (s.rodando) {
      barra.classList.add("ativo");
      $("#syncMsg").textContent = `${s.empresa_atual || ""} — ${s.mensagem || "sincronizando…"}`;
      const pct = s.total_empresas ? Math.min(96, (s.concluidas.length / s.total_empresas) * 100 + 10) : 35;
      $("#syncProg").style.width = pct + "%"; $("#syncPct").textContent = Math.round(pct) + "%";
      state.pollTimer = setTimeout(tick, 1200);
    } else {
      $("#syncProg").style.width = "100%"; $("#syncPct").textContent = "100%";
      setTimeout(() => barra.classList.remove("ativo"), 700);
      $("#btnSync").disabled = false;
      if (s.erro) { const d = document.createElement("div"); d.className = "erro-box"; d.textContent = "⚠ " + s.erro; $(REL_ALVO).prepend(d); }
      await carregarEmpresas(); await carregarFiltros(); render();
    }
  };
  tick();
}

// ===================================================== eventos do conteúdo (tooltip + tabela)
function bindConteudo() {
  const cont = $("#conteudo");
  cont.addEventListener("mouseover", (e) => { const el = e.target.closest("[data-tip]"); if (el && tipMap[el.dataset.tip]) { tipEl().innerHTML = tipMap[el.dataset.tip]; tipEl().classList.add("show"); } });
  cont.addEventListener("mousemove", (e) => { if (tipEl().classList.contains("show")) posTip(e.clientX, e.clientY); });
  cont.addEventListener("mouseout", (e) => { if (e.target.closest("[data-tip]")) tipEl().classList.remove("show"); });
  cont.addEventListener("click", (e) => {
    const th = e.target.closest("th.ord");
    if (th) { const c = th.dataset.ord, t = state.titulos; if (t.ordenar === c) t.dir = t.dir === "desc" ? "asc" : "desc"; else { t.ordenar = c; t.dir = "desc"; } t.pagina = 1; return renderTitulos(); }
    const pg = e.target.closest("[data-pg]");
    if (pg) { const t = state.titulos; if (pg.dataset.pg === "prim") t.pagina = 1; else if (pg.dataset.pg === "prev") t.pagina = Math.max(1, t.pagina - 1); else t.pagina += 1; renderTitulos(); }
  });
}

// ===================================================== inicialização
function bindGlobais() {
  mC = criarMulti($("#mContas"), "Todas as contas");
  mS = criarMulti($("#mStatus"), "Todos os status");
  mCat = criarMulti($("#mCategorias"), "Todas as categorias");
  mEmp = criarMulti($("#empresasSel"), "Todas as empresas");
  mEmp.onChange(async () => { await carregarFiltros(); aplicar(); });
  const re = () => aplicar();
  mC.onChange(re); mS.onChange(re); mCat.onChange(re);
  ["#fTipo", "#fCampoData", "#fDe", "#fAte"].forEach((s) => $(s).addEventListener("change", aplicar));
  $$("#segPeriodo button").forEach((b) => b.addEventListener("click", () => setPeriodo(b.dataset.p)));
  let deb; $("#fBusca").addEventListener("input", () => { clearTimeout(deb); deb = setTimeout(aplicar, 400); });
  $("#btnSync").innerHTML = ic("sync") + " Sincronizar";
  $("#btnSync").addEventListener("click", dispararSync);
  $("#btnImprimir").innerHTML = ic("print"); $("#btnImprimir").addEventListener("click", () => window.print());
  $("#btnExportar").innerHTML = ic("download");
  $("#btnExportar").addEventListener("click", () => { const qs = new URLSearchParams(); for (const [k, v] of Object.entries(coletarFiltros())) if (v) qs.set(k, v); window.location = "/api/export.csv?" + qs.toString(); });
  $("#menuToggle").innerHTML = ic("menu"); $("#menuToggle").addEventListener("click", () => $("#sidebar").classList.toggle("aberta"));
  bindConteudo();
}

async function init() {
  // porta de entrada: precisa estar logado
  let me;
  try { const r = await fetch("/api/me"); if (r.status === 401) { window.location = "/login"; return; } me = await r.json(); }
  catch (e) { window.location = "/login"; return; }
  state.usuario = me.usuario;
  state.view = "dashboard";

  bindGlobais(); desenharNav(); desenharUsuario();
  setPeriodo("", false);
  await carregarEmpresas(); await carregarFiltros();
  try { const s = await (await fetch("/api/sync/status")).json(); if (s.rodando) { $("#btnSync").disabled = true; pollSync(); } } catch (e) {}
  render();
}
init();
