import fs from "node:fs";
import path from "node:path";

test("manifest exposes required fields", () => {
  const m = JSON.parse(
    fs.readFileSync(path.join(process.cwd(), "public", "manifest.webmanifest"), "utf-8")
  );
  expect(m.name).toBe("你的机票发现与出行陪伴 Agent");
  expect(m.start_url).toBe("/");
  expect(m.display).toBe("standalone");
  expect(m.icons.length).toBeGreaterThanOrEqual(1);
});

test("service worker exists", () => {
  expect(fs.existsSync(path.join(process.cwd(), "public", "sw.js"))).toBe(true);
});
