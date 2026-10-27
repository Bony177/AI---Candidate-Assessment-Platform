import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let server;
let AnalysisCoverage;

before(async () => {
  server = await createServer({
    configFile: "./vite.config.js",
    server: { middlewareMode: true },
    appType: "custom",
  });
  ({ AnalysisCoverage } = await server.ssrLoadModule(
    "/src/pages/Analysis.jsx",
  ));
});

after(async () => {
  await server?.close();
});

test("partial coverage renders returned values, warning, and file reason", () => {
  const markup = renderToStaticMarkup(
    React.createElement(AnalysisCoverage, {
      coverage: {
        supported_files_discovered: 3,
        files_analyzed: 2,
        files_skipped: 0,
        files_failed: 1,
        coverage_percentage: 66.7,
        status: "partial",
        file_details: [{
          path: "src/broken.py",
          language: "Python",
          status: "failed",
          stage: "python_ast",
          reason: "Python parsing failed.",
        }],
      },
    }),
  );

  assert.match(markup, /66\.7%/);
  assert.match(markup, /aria-valuenow="66\.7"/);
  assert.match(markup, /Analysis is incomplete\./);
  assert.match(markup, /src\/broken\.py/);
  assert.match(markup, /Python parsing failed\./);
});

test("zero supported files displays an unavailable percentage and empty state", () => {
  const markup = renderToStaticMarkup(
    React.createElement(AnalysisCoverage, {
      coverage: {
        supported_files_discovered: 0,
        files_analyzed: 0,
        files_skipped: 0,
        files_failed: 0,
        coverage_percentage: null,
        status: "no_supported_files",
        file_details: [],
      },
    }),
  );

  assert.match(markup, /No supported source files were discovered/);
  assert.match(markup, /Coverage percentage: unavailable/);
  assert.doesNotMatch(markup, /100\.0%/);
});
