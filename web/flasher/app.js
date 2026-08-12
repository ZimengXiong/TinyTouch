import { ESPLoader, Transport } from "./vendor/esptool-js.js";

const images = [
  ["Bootloader", "./firmware/bootloader.bin", 0x0, "e0d0bd59a704ca41492582cd997fac0a9e4eb3fd7efbc1583a4658842905c978"],
  ["Partition table", "./firmware/partition-table.bin", 0x8000, "7f00b6c042a89b15b0cac534f82ed988caf29278ff5700b0c511eb1b5bb7c820"],
  ["Unified firmware", "./firmware/tiny_touch_smartcard.bin", 0x10000, "d110f8b0e3d4d652b94ae78dbe19111ebec813be15e711eb8cfbc1e50da6bf2c"],
];
const totalBytes = 414032;
const button = document.querySelector("#flash");
const message = document.querySelector("#message");
const browserNote = document.querySelector("#browser-note");
const progressWrap = document.querySelector("#progress-wrap");
const progress = document.querySelector("#progress");
const percent = document.querySelector("#percent");
const stage = document.querySelector("#stage");
const log = document.querySelector("#log");

if (!("serial" in navigator)) {
  button.disabled = true;
  browserNote.textContent = "Open this page in Google Chrome or Microsoft Edge.";
}

function writeLog(value) {
  const line = value.trim();
  if (!line) return;
  log.textContent = log.textContent === "No device activity yet." ? line : `${log.textContent}\n${line}`;
  log.scrollTop = log.scrollHeight;
}

function show(text, kind = "") {
  message.textContent = text;
  message.className = `message ${kind}`.trim();
}

async function sha256(data) {
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function loadFirmware() {
  const loaded = [];
  for (const [name, url, address, expected] of images) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${name} could not be downloaded.`);
    const buffer = await response.arrayBuffer();
    if (await sha256(buffer) !== expected) throw new Error(`${name} failed its integrity check.`);
    loaded.push({ data: new Uint8Array(buffer), address });
  }
  return loaded;
}

function friendlyError(error) {
  const text = error instanceof Error ? error.message : String(error);
  if (/notfound|no port selected|chooser/i.test(text)) return "No board was selected. Nothing was flashed.";
  if (/securityerror|permission denied|access denied/i.test(text)) return "Chrome does not have permission to use this serial port. Reload the page, select the board again, and approve access.";
  if (/already open|busy|networkerror/i.test(text)) return "The serial port is busy or was disconnected. Close serial monitors and other flashing tabs, reconnect the board, then try again.";
  if (/connect|serial data|timeout|sync|bootloader/i.test(text)) return "The ESP32-S3 did not enter download mode. Hold BOOT, tap RESET, release BOOT, then try again.";
  if (/could not be downloaded/i.test(text)) return `${text} Check your internet connection, reload the page, and try again.`;
  if (/integrity check/i.test(text)) return `${text} Reload the page before trying again; do not flash a file that failed verification.`;
  return text || "Flashing stopped. Nothing else was changed.";
}

button.addEventListener("click", async () => {
  let transport;
  button.disabled = true;
  progressWrap.hidden = false;
  progress.value = 0;
  percent.textContent = "0%";
  log.textContent = "No device activity yet.";
  show("Choose the ESP32-S3 serial port in the browser window.");
  try {
    const port = await navigator.serial.requestPort();
    transport = new Transport(port, false);
    const terminal = { clean(){ log.textContent = ""; }, write:writeLog, writeLine:writeLog };
    const loader = new ESPLoader({ transport, baudrate:460800, terminal, debugLogging:false });
    show("Connecting to ESP32-S3…");
    const chip = await loader.main();
    if (!/ESP32-S3/i.test(chip)) throw new Error(`This is ${chip}, not an ESP32-S3.`);

    stage.textContent = "Checking firmware";
    const fileArray = await loadFirmware();
    stage.textContent = "Writing firmware";
    const written = [0, 0, 0];
    await loader.writeFlash({
      fileArray, flashMode:"dio", flashFreq:"80m", flashSize:"4MB", eraseAll:false, compress:true,
      reportProgress(index, amount) {
        written[index] = amount;
        const value = Math.min(100, Math.round(written.reduce((sum, item) => sum + item, 0) / totalBytes * 100));
        progress.value = value;
        percent.textContent = `${value}%`;
      },
    });
    progress.value = 100;
    percent.textContent = "100%";
    await loader.after("hard_reset");
    await transport.disconnect();
    transport = undefined;
    show("Flash complete. Unplug the board and reconnect it once.", "success");
    button.textContent = "Flash another board";
  } catch (error) {
    show(friendlyError(error), "error");
    try { await transport?.disconnect(); } catch {}
  } finally {
    button.disabled = false;
  }
});
