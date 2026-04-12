#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

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
          innerHTML: ''
        });
      }
      return elementCache.get(id);
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

const loadingReport = sandbox.renderDecisionReport({
  id: 7,
  status: 'pending',
  decision_breakdown: {
    combined_score: 0.76,
    combined_score_pct: 76,
    threshold: 0.8,
    proposed_decision: 'discard'
  },
  decision_explanation: null
}, { status: 'running', current_experiment: 7 });

assertIncludes('loading report', loadingReport, 'Rationale pending');
assertIncludes('loading report', loadingReport, 'explanation-state-loading');
assertIncludes('loading report', loadingReport, 'Auto-refresh will replace this placeholder');

const missingReport = sandbox.renderDecisionReport({
  id: 3,
  status: 'discard',
  decision_breakdown: {
    combined_score: 0.79,
    combined_score_pct: 79,
    threshold: 0.8,
    proposed_decision: 'discard'
  },
  decision_explanation: null
}, { status: 'complete', current_experiment: 7 });

assertIncludes('missing report', missingReport, 'Stored rationale missing');
assertIncludes('missing report', missingReport, 'explanation-state-missing');
assertIncludes('missing report', missingReport, 'Stored rationale is unavailable, so this summary falls back to the aggregation math');

const fallbackReport = sandbox.renderDecisionReport({
  id: 4,
  status: 'keep',
  decision_breakdown: {
    combined_score: 0.91,
    combined_score_pct: 91,
    threshold: 0.8,
    proposed_decision: 'keep'
  },
  decision_explanation: 'corrupt-payload'
}, { status: 'complete', current_experiment: 7 });

assertIncludes('fallback report', fallbackReport, 'Fallback summary');
assertIncludes('fallback report', fallbackReport, 'explanation-state-fallback');
assertIncludes('fallback report', fallbackReport, 'The stored rationale could not be read');

const finalDecisionCard = sandbox.renderFinalDecisionSection({
  id: 5,
  status: 'discard',
  decision_breakdown: {
    combined_score: 0.74,
    combined_score_pct: 74,
    threshold: 0.8,
    proposed_decision: 'discard'
  },
  decision_explanation: null
}, sandbox.buildDecisionExplanationState({
  decisionExplanation: null,
  decisionBreakdown: {
    combined_score: 0.74,
    combined_score_pct: 74,
    threshold: 0.8,
    proposed_decision: 'discard'
  },
  finalDecision: 'discard'
}));

assertIncludes('final decision card', finalDecisionCard, 'Stored rationale missing');

const validationDetails = sandbox.renderExperimentDetails({
  id: 4,
  validation_results: [
    {
      eval: 'E2',
      status: 'APPROVED',
      aggregated_tpr_tnr_summary: {
        dev: { tpr_mean: 0.92, tnr_mean: 0.86 },
        test: { tpr: 0.89, tnr: 0.84 }
      },
      confusion_matrix: { tp: 12, tn: 5, fp: 1, fn: 2 },
      confusion_examples: {
        false_positives: [{ fixture_reference: 'phase4-dev-I09', judge_reason: 'judge passed a bad output' }],
        false_negatives: [{ fixture_reference: 'phase4-dev-I12', judge_reason: 'judge failed a good output' }]
      }
    }
  ]
});

assertIncludes('validation details', validationDetails, 'Judge Validation: E2');
assertIncludes('validation details', validationDetails, 'Aggregate Confusion Matrix');
assertIncludes('validation details', validationDetails, 'False Positives');
assertIncludes('validation details', validationDetails, 'False Negatives');

const holdoutReport = sandbox.renderSessionCloseHoldout({
  final_only_evaluation: {
    status: 'completed',
    evaluated_experiment_ids: [0, 4],
    variant_results_ref: 'runs/run_123/session_close_holdout/variant_results.json'
  },
  session_close_holdout: {
    selected_variant_version: 'v2',
    selected_experiment_id: 4,
    selected_candidate_summary: {
      version: 'v2',
      experiment_id: 4,
      holdout_score: 0.857
    },
    trust_gate: {
      outcome: 'review_required',
      holdout_assessment: {
        holdout_n: 7,
        interpretation_mode: 'directional_only',
        holdout_gap_status: 'moderate_gap'
      },
      calibration_assessment: {
        false_pass_rate: 0.29,
        false_fail_rate: 0.17,
        status: 'review_required'
      },
      hard_blockers: [
        { code: 'holdout_below_baseline_plus_noise', triggered: false }
      ],
      advisory_flags: [
        { code: 'directional_only_holdout', triggered: true }
      ]
    },
    optimization_metrics: {
      label: 'Non-authoritative optimization/tuning metrics',
      note: 'Intermediate tuning metrics are directional only.',
      selected_candidate: {
        dev_score: 0.923,
        holdout_gap: -0.066
      }
    },
    variant_results: [
      {
        version: 'v2',
        experiment_id: 4,
        input_ids: ['phase4-adversarial_holdout-I01'],
        eval_results: [{ eval: 'E1' }],
        decision_breakdown: {
          combined_score_pct: 85.7,
          proposed_decision: 'keep'
        },
        decision_explanation: {
          final_decision: 'keep',
          summary: 'Directional holdout result remains acceptable.'
        },
        evaluation_metadata_validation: {
          status: 'valid'
        }
      }
    ]
  }
});

assertIncludes('holdout report', holdoutReport, 'Trust Gate');
assertIncludes('holdout report', holdoutReport, 'Review Required');
assertIncludes('holdout report', holdoutReport, 'Directional Only');
assertIncludes('holdout report', holdoutReport, 'Advisory Flags');
assertIncludes('holdout report', holdoutReport, 'False Pass Rate');

console.log('dashboard explanation states: ok');
NODE
