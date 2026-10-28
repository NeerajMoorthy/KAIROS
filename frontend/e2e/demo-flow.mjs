/**
 * KAIROS browser walk-through — the README demo, driven in a real Chromium.
 *
 * It clicks through the product the way a user would and checks what the
 * screen shows at each step:
 *   Settings  → load example data, set daily availability, see save status
 *   Knowledge → find the demo folder, search, add a folder, rescan after a
 *               file is deleted on disk, remove the folder
 *   Dashboard → start the recommended focus session
 *   Focus     → pause, resume, finish with a progress value
 *   Plan / Progress → see the recalculated plan and progress
 *   Reload    → data is still there, and the snapshot on disk already has it
 *
 * Safety: it refuses to run unless the backend workspace is EMPTY, so it can
 * never alter real tasks. Start the backend with a throwaway snapshot path:
 *
 *   # terminal 1 (backend folder, PowerShell)
 *   $env:KAIROS_SNAPSHOT_PATH = "$env:TEMP\kairos_e2e.json"; Remove-Item $env:KAIROS_SNAPSHOT_PATH -ErrorAction Ignore
 *   python -m uvicorn app.main:app --port 8000
 *   # terminal 2 (frontend folder)
 *   npm run dev
 *   # terminal 3 (frontend folder) — one-time setup, then run
 *   npm install --no-save playwright
 *   npx playwright install chromium
 *   node e2e/demo-flow.mjs
 *
 * The backend must run on the same machine, because the script creates and
 * deletes files in a temporary folder that the backend then indexes.
 *
 * Environment: KAIROS_URL (default http://localhost:5173),
 *              SCREENSHOT_DIR (default e2e/screenshots), HEADED=1 to watch.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { chromium } from "playwright";

const BASE = process.env.KAIROS_URL ?? "http://localhost:5173";
const SHOTS = process.env.SCREENSHOT_DIR ?? path.join("e2e", "screenshots");
const TIMEOUT = 15_000;

const steps = [];
function step(name) {
  steps.push(name);
  console.log(`• ${name}`);
}

async function api(pathname, init) {
  const res = await fetch(`${BASE}${pathname}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${pathname} → HTTP ${res.status}`);
  return res.json();
}

function expect(condition, message) {
  if (!condition) throw new Error(`Expectation failed: ${message}`);
}

async function main() {
  const health = await api("/api/health").catch((err) => {
    throw new Error(`Cannot reach ${BASE}/api/health — is the backend and dev server running? (${err.message})`);
  });
  if (health.tasks !== 0 || health.resources !== 0) {
    throw new Error(
      `Refusing to run: the workspace already has ${health.tasks} tasks and ${health.resources} resources. ` +
      "Start the backend with KAIROS_SNAPSHOT_PATH pointing to a new, empty file.",
    );
  }

  fs.mkdirSync(SHOTS, { recursive: true });
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "kairos-e2e-"));
  const fieldNotes = path.join(scratch, "Field_Notes.md");
  fs.writeFileSync(fieldNotes, "# Field notes\n\nQuokka habitat survey notes and observations.\n");
  fs.writeFileSync(path.join(scratch, "Survey_Plan.md"), "# Survey plan\n\nSampling schedule and methods.\n");
  const folderLabel = path.basename(scratch);

  const browser = await chromium.launch({ headless: !process.env.HEADED });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  page.setDefaultTimeout(TIMEOUT);
  const consoleErrors = [];
  page.on("console", (msg) => msg.type() === "error" && consoleErrors.push(msg.text()));
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  const nav = (label) =>
    page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: label }).click();
  const status = page.getByRole("status");
  const shot = (name) => page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });

  try {
    await page.goto(BASE);
    step("App loads with an empty dashboard");
    await page.getByText("Start with one task").waitFor();

    // ------------------------------------------------------------ settings
    step("Settings: load example data");
    await nav("Settings");
    await page.getByRole("button", { name: "Load example data" }).click();
    await page.getByText(/Added \d+ example tasks/).waitFor();

    step("Settings: set 1.5 hours per day and see that it was saved");
    await page.locator("#availability").fill("1.5");
    await page.getByRole("button", { name: "Save availability" }).click();
    await page.getByText("Availability saved.").waitFor();
    const storage = page.getByTestId("storage-status");
    await storage.getByText("Every change is saved automatically").waitFor();
    await storage.getByText(/Last saved/).waitFor();
    await shot("01-settings");

    // ------------------------------------------------------------ knowledge
    step("Knowledge: the demo folder is listed as a managed folder");
    await nav("Knowledge");
    const demoRow = page.getByTestId("library-folder").filter({ hasText: "demo" });
    await demoRow.getByText(/\d+ files? · includes subfolders/).waitFor();

    step("Knowledge: search finds the project report guide and explains why");
    const search = page.getByPlaceholder("project report, citations, topic…");
    await search.fill("project report");
    await search.press("Enter");
    await page.getByText("Project_Report_Guide.md").first().waitFor();
    await page.getByText(/Why it matched:/).first().waitFor();

    step("Knowledge: add a new folder");
    await page.locator("#folder").fill(scratch);
    await page.getByRole("button", { name: "Add folder" }).click();
    await status.getByText(/added 2/).waitFor();
    const newRow = page.getByTestId("library-folder").filter({ hasText: folderLabel });
    await newRow.getByText("2 files").waitFor();
    await search.fill("quokka");
    await search.press("Enter");
    await page.getByText("Field_Notes.md", { exact: true }).waitFor();
    await shot("02-knowledge-library");

    step("Knowledge: a file deleted on disk is removed on rescan");
    fs.rmSync(fieldNotes);
    await newRow.getByRole("button", { name: "Rescan" }).click();
    await status.getByText(/removed 1/).waitFor();
    await newRow.getByText("1 file ·").waitFor();
    await search.fill("quokka");
    await search.press("Enter");
    await page.getByText("No matching material yet.").waitFor();

    step("Knowledge: remove the folder from the library (files stay on disk)");
    await newRow.getByRole("button", { name: "Remove" }).click();
    await newRow.getByText("Files on disk are not changed.").waitFor();
    await newRow.getByRole("button", { name: "Remove" }).click();
    await status.getByText(/Removed .* from your library \(1 entry\)/).waitFor();
    await newRow.waitFor({ state: "detached" });
    expect(fs.existsSync(path.join(scratch, "Survey_Plan.md")), "removing a folder must not delete files");

    // ------------------------------------------------------------ focus
    step("Dashboard: start the recommended focus session");
    await nav("Dashboard");
    await page.getByText("Recommended next action").waitFor();
    const recommendedId = (await api("/api/dashboard")).recommended_action?.task?.id;
    expect(recommendedId, "the dashboard has a recommended task");
    await shot("03-dashboard");
    await page.getByRole("button", { name: "Start focus session" }).click();

    step("Focus: the recommended task is preselected; start the session");
    await page.getByText("Focus on one task").waitFor();
    expect(
      (await page.locator("#focus-task").inputValue()) === recommendedId,
      "the Focus page preselects the recommended task",
    );
    await page.getByRole("button", { name: "Start focus session" }).click();

    step("Focus: pause, resume, and finish with 40% progress");
    await page.getByText("active", { exact: true }).waitFor();
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: "Pause" }).click();
    await page.getByText("paused", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Resume" }).click();
    await page.getByText("active", { exact: true }).waitFor();
    await shot("04-focus");
    await page.locator("#progress-after").fill("40");
    await page.getByRole("button", { name: "Finish session" }).click();
    await page.getByRole("button", { name: "Pause" }).waitFor({ state: "detached" });

    const sessions = await api("/api/focus/sessions");
    const finished = sessions.sessions.find((s) => s.status === "completed");
    expect(finished, "a completed focus session is recorded");
    const { task } = await api(`/api/tasks/${finished.task_id}`);
    expect(task.progress === 40, `task progress is 40 (got ${task.progress})`);
    expect(task.actual_hours > 0, "focused time was added to actual hours");
    expect(task.id === recommendedId, "the session was for the recommended task");

    // ------------------------------------------------------------ plan + progress
    step("Plan: build the week plan");
    await nav("Plan");
    await page.getByRole("button", { name: "Build plan" }).click();
    await page.getByText("Day-by-day plan").waitFor();
    await shot("05-plan");

    step("Progress: the focused task shows 40%");
    await nav("Progress");
    await page.getByText("Task progress").first().waitFor();
    await page.getByText(task.title).first().waitFor();

    // ------------------------------------------------------------ durability
    step("Reload: tasks are still there and the snapshot on disk has the change");
    await page.reload();
    await nav("Tasks");
    await page.getByText(task.title).first().waitFor();
    const snap = await api("/api/snapshot/status");
    expect(snap.exists && snap.autosave.enabled && !snap.autosave.last_error, "autosave is on and healthy");
    const onDisk = JSON.parse(fs.readFileSync(snap.path, "utf8"));
    const savedTask = onDisk.tasks.find((t) => t.id === task.id);
    expect(savedTask && savedTask.progress === 40, "the snapshot file already contains the 40% progress");
    expect(onDisk.settings.available_hours_per_day === 1.5, "the snapshot file contains the availability change");

    expect(consoleErrors.length === 0, `no browser console errors (got: ${consoleErrors.join(" | ")})`);
    console.log(`\nPASS — ${steps.length} steps. Screenshots in ${SHOTS}`);
  } catch (err) {
    await shot("failure").catch(() => {});
    console.error(`\nFAIL at step ${steps.length}: ${steps[steps.length - 1]}`);
    throw err;
  } finally {
    await browser.close();
    fs.rmSync(scratch, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err.message ?? err);
  process.exit(1);
});
