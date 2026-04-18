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
    ok: true,
    json: async () => ({})
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
          children: [],
          appendChild(child) {
            this.children.push(child);
          }
        });
      }
      return elementCache.get(id);
    },
    createElement(tag) {
      return {
        tagName: tag,
        innerHTML: '',
        children: [],
        appendChild(child) {
          this.children.push(child);
        }
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

const state = {
  contract_status: 'confirmed',
  selected_adapter_id: 'search_retrieval_v1'
};

const results = sandbox.serializeResultsPayload({
  status: 'complete',
  experiments: [
    {
      id: 4,
      status: 'keep',
      evaluation_metadata: {
        dataset: { split_metadata: { split_id: 'dev' } }
      },
      decision_breakdown: {
        combined_score: 0.88,
        combined_score_pct: 88,
        threshold: 0.8,
        proposed_decision: 'keep',
        components: [
          {
            eval_id: 'domain-metric',
            category: 'domain-metric',
            pass_fail: 'pass',
            weight: 2,
            evidence: [
              { source: 'domain_eval_aggregate', metric: 0.72 }
            ]
          },
          {
            eval_id: 'explanation-quality',
            category: 'quality',
            pass_fail: 'pass',
            weight: 1
          }
        ]
      }
    }
  ],
  eval_breakdown: [],
  version_comparison: null,
  contract_effectiveness: {
    exact_match: {
      success_examples_pass: 3,
      success_examples_total: 3,
      failure_examples_caught: 2,
      failure_examples_total: 3,
      trigger_correct_fires: 3,
      trigger_total_fires: 3,
      trigger_correct_declines: 3,
      trigger_total_declines: 3
    },
    paraphrased: {
      success_examples_pass: 5,
      success_examples_total: 6,
      failure_examples_caught: 4,
      failure_examples_total: 6,
      trigger_correct_fires: 5,
      trigger_total_fires: 6,
      trigger_correct_declines: 6,
      trigger_total_declines: 6
    },
    overfit_analysis: {
      status: 'overfit_none',
      overfit_ratio: 0.08,
      overfit_threshold: 0.20
    },
    domain_metric: {
      name: 'NDCG@5',
      continuous_score: 0.72
    },
    efficiency_trend: {
      baseline_tokens: 1200,
      final_tokens: 900,
      baseline_tool_calls: 6,
      final_tool_calls: 4
    },
    leakage_audit: {
      status: 'clean',
      test_split_matches: 0,
      holdout_split_matches: 0
    }
  },
  session_close_holdout: {
    status: 'completed',
    trust_gate: {
      outcome: 'promote'
    },
    selected_candidate_summary: {
      version: 'v2',
      experiment_id: 4,
      holdout_score: 0.83
    },
    variant_results: [
      {
        version: 'v2',
        experiment_id: 4,
        input_ids: ['holdout-1'],
        evaluation_metadata_validation: { status: 'valid', issues: [] },
        eval_results: [],
        decision_breakdown: {
          combined_score: 0.83,
          combined_score_pct: 83,
          threshold: 0.8,
          proposed_decision: 'keep',
          components: [
            {
              eval_id: 'domain-metric',
              category: 'domain-metric',
              pass_fail: 'pass',
              weight: 2,
              evidence: [
                { source: 'domain_eval_aggregate', metric: 0.72 }
              ]
            },
            {
              eval_id: 'explanation-quality',
              category: 'quality',
              pass_fail: 'pass',
              weight: 1
            }
          ]
        },
        decision_explanation: {
          summary: 'Holdout stayed above threshold.'
        }
      }
    ]
  }
});

sandbox.renderContract(state, results);
sandbox.renderAdapterEvaluation(state, results);

const contractSummary = sandbox.document.getElementById('contract-summary').innerHTML;
assertIncludes('contract summary', contractSummary, 'Exact match success');
assertIncludes('contract summary', contractSummary, 'Paraphrased success');
assertIncludes('contract summary', contractSummary, 'NDCG@5');

const adapterSummary = sandbox.document.getElementById('adapter-summary').innerHTML;
assertIncludes('adapter summary', adapterSummary, 'Search Retrieval v1');
assertIncludes('adapter summary', adapterSummary, 'Ranking metrics on stable doc_id order');
assertIncludes('adapter summary', adapterSummary, 'Promote');

const adapterRows = sandbox.document.getElementById('adapter-details').children.map(row => row.innerHTML).join('\n');
assertIncludes('adapter table', adapterRows, 'Primary component');
assertIncludes('adapter table', adapterRows, 'Primary continuous score');
assertIncludes('adapter table', adapterRows, 'Secondary diagnostics');

console.log('dashboard adapter render: ok');
NODE
