import type { CSSProperties } from 'react'

import type { ResearchFollowUp, RiskPrediction, RiskScenarioResponse } from '../api/client'
import { TechnicalDetails } from './UiPrimitives'
import { displayFeatureValue, featureLabels } from './researchRiskPresentation'

export function PredictionStage({
  followUp,
  prediction,
  scenarios,
  onEdit,
}: {
  followUp: ResearchFollowUp
  prediction: RiskPrediction
  scenarios: RiskScenarioResponse | null
  onEdit: () => void
}) {
  return <section className="prediction-region" aria-labelledby="prediction-stage-title">
    <div className="compact-section-heading">
      <div><h2 id="prediction-stage-title">Dropout estimate</h2><p>Based on information through day {followUp.cutoff_day}.</p></div>
      <button className="secondary-button" type="button" onClick={onEdit}>Edit inputs</button>
    </div>
    <PredictionResult prediction={prediction} scenarios={scenarios} />
  </section>
}

function factorDirection(direction: RiskPrediction['top_contributions'][number]['direction']) {
  return direction === 'higher' ? 'Raised estimate' : 'Lowered estimate'
}

function ScenarioChart({ scenarios }: { scenarios: RiskScenarioResponse }) {
  const x = [42, 270, 498]
  const y = (probability: number) => 142 - probability * 110
  const points = scenarios.points.map((point, index) => `${x[index]},${y(point.probability)}`).join(' ')
  const thresholdY = y(scenarios.threshold)

  return <section className="scenario-panel" aria-labelledby="scenario-title">
    <div><h3 id="scenario-title">If more doses are missed</h3><p>Exact model results with every other value unchanged.</p></div>
    <svg className="scenario-chart" viewBox="0 0 540 174" role="img" aria-label={scenarios.points.map((point) => `${point.additional_missed_doses ? `plus ${point.additional_missed_doses}` : 'current'}: ${(point.probability * 100).toFixed(1)} percent`).join(', ')}>
      <line className="scenario-axis" x1="42" y1="142" x2="498" y2="142" />
      <line className="scenario-threshold" x1="42" y1={thresholdY} x2="498" y2={thresholdY} />
      <text className="scenario-threshold-label" x="496" y={Math.max(14, thresholdY - 6)} textAnchor="end">review marker {(scenarios.threshold * 100).toFixed(1)}%</text>
      <polyline className="scenario-line" points={points} />
      {scenarios.points.map((point, index) => <g key={point.additional_missed_doses}>
        <circle className="scenario-point" cx={x[index]} cy={y(point.probability)} r="5" />
        <text className="scenario-value" x={x[index]} y={Math.max(17, y(point.probability) - 11)} textAnchor="middle">{(point.probability * 100).toFixed(1)}%</text>
        <text className="scenario-label" x={x[index]} y="164" textAnchor="middle">{index === 0 ? 'Current' : `+${index} missed`}</text>
      </g>)}
    </svg>
    <div className="scenario-values">
      {scenarios.points.map((point) => <span key={point.additional_missed_doses}><strong>{point.missed_doses}/{point.scheduled_doses}</strong> doses missed</span>)}
    </div>
  </section>
}

function PredictionResult({ prediction, scenarios }: { prediction: RiskPrediction; scenarios: RiskScenarioResponse | null }) {
  const probability = prediction.probability * 100
  const threshold = prediction.threshold * 100
  return <div className="prediction-result">
    <div className="prediction-summary-row">
      <div className="risk-gauge" style={{ '--risk-probability': `${probability}%`, '--risk-threshold': `${threshold}%` } as CSSProperties}>
        <div aria-label={`Estimated probability ${probability.toFixed(1)} percent; review marker ${threshold.toFixed(1)} percent`}><span style={{ left: `${Math.min(100, threshold)}%` }} /></div>
        <strong>{probability.toFixed(1)}%</strong>
        <small>estimated probability by day {prediction.horizon_day}</small>
        <p>Review marker {threshold.toFixed(1)}% · <b>{prediction.research_label.replaceAll('_', ' ')}</b></p>
      </div>
      <div className="contribution-panel">
        <h3>Main factors</h3>
        <ol>{prediction.top_contributions.slice(0, 4).map((item) => <li key={item.feature}><span><strong>{featureLabels[item.feature] ?? item.feature.replaceAll('_', ' ')}</strong><small>{displayFeatureValue(item.value)}</small></span><span className={`factor-direction contribution-${item.direction}`}>{factorDirection(item.direction)}</span></li>)}</ol>
      </div>
    </div>
    {scenarios ? <ScenarioChart scenarios={scenarios} /> : null}
    <TechnicalDetails>
      <dl className="technical-details-list">
        <div><dt>Model</dt><dd>{prediction.model.name}:{prediction.model.version}</dd></div>
        <div><dt>Runtime candidate</dt><dd>{prediction.model.candidate_id}</dd></div>
        <div><dt>Observation cutoff</dt><dd>Day {prediction.observation_cutoff_day}</dd></div>
        <div><dt>Prediction horizon</dt><dd>Day {prediction.horizon_day}</dd></div>
      </dl>
      <div className="technical-contributions"><h5>Contribution values</h5>{prediction.top_contributions.map((item) => <p key={item.feature}><span>{featureLabels[item.feature] ?? item.feature}</span><strong>{item.shap_value > 0 ? '+' : ''}{item.shap_value.toFixed(3)}</strong></p>)}</div>
    </TechnicalDetails>
  </div>
}
