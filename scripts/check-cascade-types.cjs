// Run positive declarations and verify that every negative contract is rejected.
const { spawnSync } = require("node:child_process");
const { readFileSync } = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const cli = require.resolve("pyright/index.js");
const run = (args, options = {}) => spawnSync(process.execPath, [cli, ...args], {
  cwd: root, encoding: "utf8", ...options,
});
const positive = run(["-p", "pyrightconfig.cascade.json"], { stdio: "inherit" });
if (positive.status !== 0) process.exit(positive.status || 1);

const fixture = "backend/tests/typing/cascade_fields_invalid.py";
const expected = readFileSync(path.join(root, fixture), "utf8").split(/\r?\n/)
  .flatMap((line, index) => {
    const match = line.match(/# expect: (\w+)/);
    return match ? [`${index}:${match[1]}`] : [];
  }).sort();
const negative = run(["-p", "backend/tests/typing/pyrightconfig.invalid.json", "--outputjson"]);
if (negative.error || negative.status !== 1) {
  console.error("Negative type check did not return the expected diagnostics", negative);
  process.exit(1);
}
const diagnostics = JSON.parse(negative.stdout).generalDiagnostics;
const actual = diagnostics.map(d => {
  if (d.severity !== "error" || path.resolve(d.file).toLowerCase() !== path.join(root, fixture).toLowerCase()) {
    console.error("Unexpected diagnostic", d);
    process.exit(1);
  }
  return `${d.range.start.line}:${d.rule}`;
}).sort();
if (!expected.length || JSON.stringify(actual) !== JSON.stringify(expected)) {
  console.error("Expected", expected, "but received", actual, diagnostics);
  process.exit(1);
}
console.log(`Negative contracts: ${expected.length} expected errors verified.`);
