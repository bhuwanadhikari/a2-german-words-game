const MAIN_CSV = "final_words_translated.csv";
const STORAGE_KNOWN = "german_a2_known";
const STORAGE_UNKNOWN = "german_a2_unknown";

const screenSelect = document.getElementById("screenSelect");
const screenPlay = document.getElementById("screenPlay");
const endGameBtn = document.getElementById("endGameBtn");

const countMain = document.getElementById("countMain");
const countKnown = document.getElementById("countKnown");
const countUnknown = document.getElementById("countUnknown");

const bagLabel = document.getElementById("bagLabel");
const wordText = document.getElementById("wordText");
const meaningBox = document.getElementById("meaningBox");
const meaningEnglish = document.getElementById("meaningEnglish");
const meaningExample = document.getElementById("meaningExample");
const meaningInfo = document.getElementById("meaningInfo");
const btnKnown = document.getElementById("btnKnown");
const btnUnknown = document.getElementById("btnUnknown");
const btnNext = document.getElementById("btnNext");
const emptyState = document.getElementById("emptyState");
const actions = document.querySelector(".actions");

const downloadKnown = document.getElementById("downloadKnown");
const downloadUnknown = document.getElementById("downloadUnknown");

let words = [];
let wordById = new Map();
let knownIds = new Set();
let unknownIds = new Set();
let currentBag = "main";
let currentWord = null;
const seenIdsByBag = {
  main: new Set(),
  known: new Set(),
  unknown: new Set(),
};

function parseCSVLine(line) {
  const out = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === "\"") {
      const next = line[i + 1];
      if (inQuotes && next === "\"") {
        field += "\"";
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === "," && !inQuotes) {
      out.push(field);
      field = "";
    } else {
      field += ch;
    }
  }
  out.push(field);
  return out;
}

function loadCSV(text) {
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length === 0) return [];
  const header = parseCSVLine(lines[0]).map((h) => h.trim());
  const idx = {
    sn: header.indexOf("sn"),
    german: header.indexOf("german"),
    english: header.indexOf("english"),
    example: header.indexOf("example_de"),
    info: header.indexOf("info"),
  };
  const list = [];
  for (let i = 1; i < lines.length; i += 1) {
    const cols = parseCSVLine(lines[i]);
    const sn = cols[idx.sn] || String(i);
    const item = {
      sn: sn.trim(),
      german: (cols[idx.german] || "").trim(),
      english: (cols[idx.english] || "").trim(),
      example: (cols[idx.example] || "").trim(),
      info: (cols[idx.info] || "").trim(),
    };
    if (item.german) list.push(item);
  }
  return list;
}

function readSet(key) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function saveSets() {
  localStorage.setItem(STORAGE_KNOWN, JSON.stringify(Array.from(knownIds)));
  localStorage.setItem(STORAGE_UNKNOWN, JSON.stringify(Array.from(unknownIds)));
}

function normalizeSets() {
  const validIds = new Set(words.map((w) => w.sn));
  knownIds = new Set(Array.from(knownIds).filter((id) => validIds.has(id)));
  unknownIds = new Set(Array.from(unknownIds).filter((id) => validIds.has(id)));
  for (const id of Array.from(knownIds)) {
    if (unknownIds.has(id)) {
      unknownIds.delete(id);
    }
  }
}

function updateCounts() {
  countMain.textContent = words.length;
  countKnown.textContent = knownIds.size;
  countUnknown.textContent = unknownIds.size;
}

function setScreen(screen) {
  if (screen === "play") {
    screenSelect.classList.remove("active");
    screenPlay.classList.add("active");
    endGameBtn.hidden = false;
  } else {
    screenPlay.classList.remove("active");
    screenSelect.classList.add("active");
    endGameBtn.hidden = true;
  }
}

function getBagIds(bag) {
  if (bag === "known") return Array.from(knownIds);
  if (bag === "unknown") return Array.from(unknownIds);
  return words.map((w) => w.sn);
}

function getUnseenBagIds(bag) {
  const ids = getBagIds(bag);
  const validIds = new Set(ids);
  const seenIds = seenIdsByBag[bag];

  for (const id of Array.from(seenIds)) {
    if (!validIds.has(id)) {
      seenIds.delete(id);
    }
  }

  let unseenIds = ids.filter((id) => !seenIds.has(id));
  if (unseenIds.length === 0 && ids.length > 0) {
    seenIds.clear();
    unseenIds = ids;
  }

  return unseenIds;
}

function showEmptyState() {
  emptyState.hidden = false;
  btnKnown.disabled = true;
  btnUnknown.disabled = true;
  btnNext.hidden = true;
  actions.hidden = true;
  meaningBox.hidden = true;
  meaningEnglish.textContent = "";
  meaningExample.textContent = "";
  meaningInfo.textContent = "";
  wordText.textContent = "—";
}

function showWord(word) {
  currentWord = word;
  wordText.textContent = word.german;
  meaningBox.hidden = true;
  meaningEnglish.textContent = "";
  meaningExample.textContent = "";
  meaningInfo.textContent = "";
  btnNext.hidden = true;
  emptyState.hidden = true;
  actions.hidden = false;
  btnKnown.disabled = false;
  btnUnknown.disabled = false;
}

function pickRandomWord(bag) {
  const ids = getUnseenBagIds(bag);
  if (ids.length === 0) {
    showEmptyState();
    return;
  }
  const randomId = ids[Math.floor(Math.random() * ids.length)];
  const word = wordById.get(randomId);
  if (!word) {
    showEmptyState();
    return;
  }
  seenIdsByBag[bag].add(randomId);
  showWord(word);
}

function revealMeaning() {
  if (!currentWord) return;
  meaningEnglish.textContent = currentWord.english || "—";
  meaningExample.textContent = currentWord.example || "—";
  meaningInfo.textContent = currentWord.info || "—";
  meaningBox.hidden = false;
  actions.hidden = true;
  btnNext.hidden = false;
}

function handleAnswer(choice) {
  if (!currentWord) return;
  const id = currentWord.sn;

  if (currentBag === "main") {
    if (choice === "known") {
      knownIds.add(id);
      unknownIds.delete(id);
    } else {
      unknownIds.add(id);
      knownIds.delete(id);
    }
  } else if (currentBag === "known") {
    if (choice === "unknown") {
      knownIds.delete(id);
      unknownIds.add(id);
    } else {
      knownIds.add(id);
    }
  } else if (currentBag === "unknown") {
    if (choice === "known") {
      unknownIds.delete(id);
      knownIds.add(id);
    } else {
      unknownIds.add(id);
    }
  }

  saveSets();
  updateCounts();
  revealMeaning();
}

function csvEscape(value) {
  const v = String(value ?? "");
  if (v.includes("\"") || v.includes(",") || v.includes("\n") || v.includes("\r")) {
    return `"${v.replace(/\"/g, "\"\"")}"`;
  }
  return v;
}

function exportCSV(ids, filename) {
  const list = Array.from(ids)
    .map((id) => wordById.get(id))
    .filter(Boolean)
    .sort((a, b) => Number(a.sn) - Number(b.sn));

  const lines = [
    ["sn", "german", "english", "example_de", "info"]
      .map(csvEscape)
      .join(","),
  ];
  for (const w of list) {
    lines.push(
      [w.sn, w.german, w.english, w.example, w.info].map(csvEscape).join(",")
    );
  }
  const blob = new Blob([lines.join("\n") + "\n"], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

document.querySelectorAll(".bag").forEach((btn) => {
  btn.addEventListener("click", () => {
    currentBag = btn.dataset.bag;
    bagLabel.textContent = currentBag.toUpperCase();
    setScreen("play");
    pickRandomWord(currentBag);
  });
});

btnKnown.addEventListener("click", () => handleAnswer("known"));
btnUnknown.addEventListener("click", () => handleAnswer("unknown"));
btnNext.addEventListener("click", () => pickRandomWord(currentBag));
endGameBtn.addEventListener("click", () => {
  updateCounts();
  setScreen("select");
});

downloadKnown.addEventListener("click", () =>
  exportCSV(knownIds, "known_texts.csv")
);
downloadUnknown.addEventListener("click", () =>
  exportCSV(unknownIds, "unknown_texts.csv")
);

async function init() {
  const res = await fetch(MAIN_CSV);
  const text = await res.text();
  words = loadCSV(text);
  wordById = new Map(words.map((w) => [w.sn, w]));

  knownIds = readSet(STORAGE_KNOWN);
  unknownIds = readSet(STORAGE_UNKNOWN);
  normalizeSets();
  saveSets();
  updateCounts();
}

init();
