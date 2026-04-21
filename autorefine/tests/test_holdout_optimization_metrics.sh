#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

node <<'NODE'
const fs = require('fs');
const vm = require('vm');

function extractDashboardScript(html) {
  const match = html.match(/<script>([\s\S]*)<\/script>\s*<\/body>/);
  if (!match) {
    throw new Error('Dashboard script block not found');
  }
  return match[1];
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function assertIncludes(label, haystack, needle) {
  if (!haystack.includes(needle)) {
    throw new Error(`${label} missing expected text: ${needle}`);
  }
}

const html = fs.readFileSync('dashboard.html', 'utf8');
const script = extractDashboardScript(html);
const elementCache = new Map();

const sandbox = {
  console,
  fetch: async () => ({
    json: async () => ({
      status: 'complete',
      current_experiment: 0,
      baseline_score: null,
      best_score: null,
      experiments: [],
      eval_breakdown: [],
      version_comparison: null
    })
  }),
  document: {
    getElementById(id) {
      if (!elementCache.has(id)) {
        elementCache.set(id, {
          id,
          textContent: '',
          className: '',
          innerHTML: '',
          style: {},
          appendChild() {},
          addEventListener() {}
        });
      }
      return elementCache.get(id);
    },
    createElement() {
      return {
        textContent: '',
        className: '',
        innerHTML: '',
        style: {},
        appendChild() {},
        addEventListener() {}
      };
    }
  },
  Chart: function ChartStub() {
    return { destroy() {} };
  },
  setInterval: () => 0,
  clearInterval: () => undefined
};

vm.createContext(sandbox);
vm.runInContext(script, sandbox);

const payload = sandbox.serializeResultsPayload({
  status: 'complete',
  experiments: [],
  eval_breakdown: [],
  version_comparison: null,
  schema_version: 1,
  artifact_type: 'final_holdout_results',
  stage_id: 'session_close_holdout_validation',
  run_path: 'runs/run_2026-04-03T14-30-00/',
  source_results_ref: 'results.json',
  evaluated_experiment_ids: [0, 4],
  selected_variant_version: 'v2',
  selected_experiment_id: 4,
  selected_candidate_summary: {
    version: 'v2',
    experiment_id: 4,
    dev_score: 0.923,
    holdout_score: 0.857,
    holdout_gap: -0.066
  },
  variant_results: [
    {
      version: 'v2',
      experiment_id: 4,
      input_ids: ['phase4-adversarial_holdout-91ab77ce-I01'],
      evaluation_metadata_validation: { status: 'valid', issues: [] },
      eval_results: [],
      decision_breakdown: {
        combined_score: 0.857,
        combined_score_pct: 85.7,
        threshold: 0.8,
        proposed_decision: 'keep'
      },
      decision_explanation: {
        summary: 'Holdout stayed above threshold, so the selected candidate remains keep.'
      }
    }
  ]
});

const holdout = payload.session_close_holdout;
assert(holdout, 'serialized payload did not expose session_close_holdout');
assert(holdout.selected_candidate_summary, 'selected_candidate_summary missing');
assert(holdout.selected_candidate_summary.holdout_score === 0.857, 'holdout_score missing from authoritative summary');
assert(!Object.prototype.hasOwnProperty.call(holdout.selected_candidate_summary, 'dev_score'), 'dev_score should not remain in selected_candidate_summary');
assert(!Object.prototype.hasOwnProperty.call(holdout.selected_candidate_summary, 'holdout_gap'), 'holdout_gap should not remain in selected_candidate_summary');

assert(holdout.optimization_metrics, 'optimization_metrics missing');
assert(holdout.optimization_metrics.authoritative === false, 'optimization_metrics should be explicitly non-authoritative');
assert(holdout.optimization_metrics.selected_candidate.dev_score === 0.923, 'dev_score missing from optimization_metrics.selected_candidate');
assert(holdout.optimization_metrics.selected_candidate.holdout_gap === -0.066, 'holdout_gap missing from optimization_metrics.selected_candidate');

const rendered = sandbox.renderSessionCloseHoldout({
  session_close_holdout: holdout,
  final_only_evaluation: null
});

assertIncludes('rendered holdout panel', rendered, 'Selected Final Candidate');
assertIncludes('rendered holdout panel', rendered, 'Holdout Score');
assertIncludes('rendered holdout panel', rendered, 'Optimization Metrics');
assertIncludes('rendered holdout panel', rendered, 'Non-authoritative optimization/tuning metrics');
assertIncludes('rendered holdout panel', rendered, 'Dev Score');
assertIncludes('rendered holdout panel', rendered, 'Holdout Gap');

console.log('holdout optimization metrics: ok');
NODE
